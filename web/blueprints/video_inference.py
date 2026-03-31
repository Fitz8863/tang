import cv2
import threading
import numpy as np
import time
import os
import sys
import subprocess
from collections import defaultdict
from queue import Queue, Empty, Full

# 引入项目配置
try:
    from config import (
        YOLO_MODEL_PATH, 
        YOLO_CONF_THRESHOLD, 
        YOLO_IOU_THRESHOLD, 
        YOLO_DEVICE, 
        YOLO_IMG_SIZE,
        YOLO_QUEUE_SIZE
    )
except ImportError:
    YOLO_MODEL_PATH = 'model/yolo26n_openvino_model/'
    YOLO_CONF_THRESHOLD = 0.25
    YOLO_IOU_THRESHOLD = 0.45
    YOLO_DEVICE = 'cpu'
    YOLO_IMG_SIZE = 640
    YOLO_QUEUE_SIZE = 1

third_party_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '3rdparty'
)
if third_party_path not in sys.path:
    sys.path.insert(0, third_party_path)

from ultralytics import YOLO

class VideoInference:
    def __init__(self, model_path=YOLO_MODEL_PATH):
        self.model = None
        self.model_path = model_path
        self.captures = {}
        # 管理全局 ffmpeg 音频进程
        self.audio_processes = {}
        self.lock = threading.Lock()
        self.fps_stats = defaultdict(lambda: {"count": 0, "start_time": time.time(), "display": 0})
        
        self.running = True
        threading.Thread(target=self._daemon_sync_loop, daemon=True).start()
        
    def _daemon_sync_loop(self):
        """全天候同步守护进程：根据 MQTT 心跳自动维持所有在线设备的拉流(视频+音频)和推理"""
        while self.running:
            time.sleep(3.0)
            try:
                from blueprints.mqtt_manager import mqtt_manager
                if not mqtt_manager or not mqtt_manager.connected or not mqtt_manager.latest_jetson_info:
                    continue
                    
                active_cameras = mqtt_manager.latest_jetson_info.get('cameras', [])
                active_ids = set()
                
                # 1. 自动为所有在线设备建连并拉流（如果已连接且URL没变，get_or_create会忽略）
                for cam in active_cameras:
                    cam_id = str(cam.get('id', ''))
                    if not cam_id: continue
                    active_ids.add(cam_id)
                    
                    # --- 视频拉流自动启动 ---
                    video_url = cam.get('rtsp_url') or cam.get('http_url')
                    if video_url:
                        self.get_or_create_capture(cam_id, video_url)
                        
                    # --- 音频拉流自动启动 ---
                    audio_url = cam.get('voice_rtsp_url')
                    if audio_url:
                        self.get_or_create_audio(cam_id, audio_url)
                        
                # 2. 清理已经离线（不在心跳包中）的设备资源
                with self.lock:
                    cameras_to_stop = [cid for cid in self.captures.keys() if cid not in active_ids]
                    # 还需要检查音频进程是否有多余的
                    audio_to_stop = [cid for cid in self.audio_processes.keys() if cid not in active_ids]
                    
                for cid in cameras_to_stop:
                    print(f"[VideoInference] 摄像头 {cid} 心跳丢失，自动停止视频推理资源")
                    self.stop_capture(cid)
                    
                for cid in audio_to_stop:
                    print(f"[AudioInference] 摄像头 {cid} 心跳丢失，自动停止音频资源")
                    self.stop_audio(cid)
                    
            except Exception as e:
                print(f"[VideoInference] Daemon 同步异常: {e}")

    def get_or_create_audio(self, camera_id, stream_url):
        """确保音频进程存在且在运行。如果在运行，不干预；如果死亡，尝试重启。"""
        with self.lock:
            if camera_id in self.audio_processes:
                proc = self.audio_processes[camera_id]['proc']
                url = self.audio_processes[camera_id]['url']
                
                # 如果进程还活着且 URL 没变，保持运行
                if proc.poll() is None and url == stream_url:
                    return
                # 否则杀掉旧的，准备重建
                self.stop_audio(camera_id, locked=True)
                
            print(f"[Audio] 检测到设备上线，自动在后台拉取音频流: {camera_id}")
            cmd = [
                'ffplay', '-nodisp', 
                '-rtsp_transport', 'tcp', 
                '-fflags', 'nobuffer', 
                '-flags', 'low_delay', 
                '-framedrop', '-strict', 'experimental', 
                # 终极抗延迟核心参数：
                '-sync', 'ext',                 # 强制与系统真实时间同步，迟到的音频包直接丢弃
                '-af', 'aresample=async=1',     # 启用异步重采样，动态拉伸声音消耗掉积压的缓冲
                '-probesize', '32',             # 极限压缩格式探测时间
                '-analyzeduration', '0',
                '-i', stream_url
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.audio_processes[camera_id] = {
                'proc': proc,
                'url': stream_url
            }
            
    def stop_audio(self, camera_id, locked=False):
        """停止特定摄像头的音频拉流"""
        def _kill():
            c_data = self.audio_processes.pop(camera_id, None)
            if c_data and c_data['proc']:
                c_data['proc'].kill()
                c_data['proc'].wait()
        
        if locked:
            _kill()
        else:
            with self.lock:
                _kill()
                
    # ------ 以下是原有的模型加载和视频线程方法 ------
    def load_model(self):
        if self.model is None:
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                self.model_path
            )
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"找不到模型路径: {full_path}")
            
            # 模型类型智能识别
            self.model_type = 'pytorch'
            if os.path.isdir(full_path) or 'openvino' in full_path.lower():
                self.model_type = 'openvino'
            elif full_path.lower().endswith('.onnx'):
                self.model_type = 'onnx'
            
            print(f"[VideoInference] 正在初始化 {self.model_type.upper()} 推理引擎: {full_path}")
            
            try:
                # OpenVINO 和 ONNX 模型加载时建议指定 task='detect'
                if self.model_type in ['openvino', 'onnx']:
                    self.model = YOLO(full_path, task='detect')
                else:
                    # PyTorch 原生模型 (.pt)
                    self.model = YOLO(full_path)
                    if YOLO_DEVICE != 'cpu':
                        self.model.to(YOLO_DEVICE)
                
                print(f"[VideoInference] {self.model_type.upper()} 模型就绪，运行设备: {YOLO_DEVICE}")
            except Exception as e:
                print(f"[VideoInference] 模型加载失败: {e}")
                raise e
    
    def get_or_create_capture(self, camera_id, stream_url):
        with self.lock:
            if camera_id not in self.captures:
                # 初始化三级流水线队列 (从 config 读取深度)
                self.captures[camera_id] = {
                    'url': stream_url,
                    'raw_queue': Queue(maxsize=int(YOLO_QUEUE_SIZE)),
                    'latest_jpeg': None,  # 缓存压缩后的 JPEG 数据，实现单次编码多路分发
                    'lock': threading.Lock(),
                    'stop_event': threading.Event(),
                    'threads': []
                }
                
                # 启动三级并行线程
                c_data = self.captures[camera_id]
                
                # 1. 拉流线程
                t_cap = threading.Thread(target=self._thread_capture, args=(camera_id,), daemon=True)
                # 2. 推理线程
                t_inf = threading.Thread(target=self._thread_inference, args=(camera_id,), daemon=True)
                
                c_data['threads'] = [t_cap, t_inf]
                for t in c_data['threads']: t.start()
                
            elif self.captures[camera_id]['url'] != stream_url:
                self.stop_capture(camera_id)
                return self.get_or_create_capture(camera_id, stream_url)
            
            return self.captures[camera_id]

    def _thread_capture(self, camera_id):
        """第一级：原始流抓取线程 (Producer)"""
        c_data = self.captures[camera_id]
        url = c_data['url']
        print(f"[Capture] 启动拉流线程: {camera_id}")
        
        # 精简参数：仅保留 tcp 和 nobuffer，去掉重排序等消耗 CPU 的指令
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        
        # 核心优化 1：源头降分辨率解码。强制底层解码器输出小图，极大减轻 FFMPEG 的 CPU 压力
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(YOLO_IMG_SIZE))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(YOLO_IMG_SIZE * 0.75)) # 假设 4:3，或者就让它自适应
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        while not c_data['stop_event'].is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                if not cap.isOpened():
                    cap.release()
                    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(YOLO_IMG_SIZE))
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(YOLO_IMG_SIZE * 0.75))
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                continue
            
            # 将新帧丢入队列
            try:
                while c_data['raw_queue'].full():
                    c_data['raw_queue'].get_nowait()
                c_data['raw_queue'].put_nowait(frame)
            except:
                pass
        
        cap.release()
        print(f"[Capture] 停止拉流线程: {camera_id}")

    def _thread_inference(self, camera_id):
        """第二级：YOLO 推理线程 (Consumer)"""
        c_data = self.captures[camera_id]
        print(f"[Inference] 启动推理线程: {camera_id}")
        
        if self.model is None: self.load_model()
        
        while not c_data['stop_event'].is_set():
            try:
                frame = c_data['raw_queue'].get(timeout=1.0)
                
                # 核心优化 2：对齐 predict.py 的轻量级调用
                # 根据模型类型动态调整参数
                infer_args = {
                    'source': frame,
                    'conf': float(YOLO_CONF_THRESHOLD),
                    'iou': float(YOLO_IOU_THRESHOLD),
                    'verbose': False
                }
                
                # 如果是 PyTorch 模型，允许显式指定 device
                if self.model_type == 'pytorch':
                    infer_args['device'] = YOLO_DEVICE
                
                results = self.model.predict(**infer_args)
                
                annotated_frame = results[0].plot()
                
                # 计算 FPS 并叠加
                stats = self.fps_stats[camera_id]
                stats["count"] += 1
                elapsed = time.time() - stats["start_time"]
                if elapsed >= 1.0:
                    stats["display"] = stats["count"] / elapsed
                    stats["count"] = 0
                    stats["start_time"] = time.time()
                
                cv2.putText(annotated_frame, f"PIPELINE FPS: {stats['display']:.1f}", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # 核心优化 3：降低 JPEG 压缩质量以换取极速编码
                ret, jpeg = cv2.imencode('.jpg', annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                if ret:
                    with c_data['lock']:
                        c_data['latest_jpeg'] = jpeg.tobytes()
                    
            except Empty:
                continue
            except Exception as e:
                print(f"[Inference] 推理运行报错: {e}")
        
        print(f"[Inference] 停止推理线程: {camera_id}")


    def get_frame(self, camera_id):
        """供接口调用的输出端 (Output)，只做读取，无繁重计算"""
        with self.lock:
            c_data = self.captures.get(camera_id)
            
        if not c_data: return None
        
        with c_data['lock']:
            return c_data['latest_jpeg']
    
    def stop_capture(self, camera_id):
        with self.lock:
            c_data = self.captures.pop(camera_id, None)
            
        if c_data:
            c_data['stop_event'].set()

    def stop_all(self):
        with self.lock:
            for camera_id in list(self.captures.keys()):
                self.stop_capture(camera_id)

video_inference = VideoInference()

