import cv2
import threading
import numpy as np
import time
import os
import sys
import subprocess
import requests
import base64
import json
import uuid
from datetime import datetime
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
        YOLO_QUEUE_SIZE,
        FRAME_DIFF_PERCENT,
        FRAME_CHECK_INTERVAL,
        VLM_ENABLED,
        VLM_BACKEND,
        VLM_API_BASE,
        VLM_API_KEY,
        VLM_MODEL_NAME,
        VLM_FRAME_SKIP,
        VLM_ANALYZE_INTERVAL,
        VLM_PROMPT
    )
except ImportError:
    YOLO_MODEL_PATH = 'model/yolo26n_openvino_model/'
    YOLO_CONF_THRESHOLD = 0.25
    YOLO_IOU_THRESHOLD = 0.45
    YOLO_DEVICE = 'cpu'
    YOLO_IMG_SIZE = 640
    YOLO_QUEUE_SIZE = 1
    FRAME_DIFF_PERCENT = 0.05
    FRAME_CHECK_INTERVAL = 3
    VLM_ENABLED = False
    VLM_BACKEND = 'ollama'
    VLM_API_BASE = 'http://localhost:11434/api/chat'
    VLM_API_KEY = ''
    VLM_MODEL_NAME = 'llava'
    VLM_FRAME_SKIP = 30
    VLM_ANALYZE_INTERVAL = 5.0
    VLM_PROMPT = ""

third_party_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '3rdparty'
)
if third_party_path not in sys.path:
    sys.path.insert(0, third_party_path)

from ultralytics import YOLO

class VideoInference:
    def __init__(self, model_path=YOLO_MODEL_PATH):
        self.pid = os.getpid()
        print(f"[VideoInference] 正在实例化守护进程，当前 PID: {self.pid}")
        
        self.app = None
        self.model = None
        self.model_path = model_path
        self.model_type = 'pytorch'
        self.captures = {}
        self.audio_processes = {}
        self.muted_cameras = set()
        self.lock = threading.Lock()
        self.audio_start_lock = threading.Lock()
        self.vlm_active_threads = 0
        self.vlm_thread_lock = threading.Lock()
        self.fps_stats = defaultdict(lambda: {"count": 0, "start_time": time.time(), "display": 0})
        self.camera_locations = {}
        
        self.running = True
        daemon_thread = threading.Thread(target=self._daemon_sync_loop, daemon=True)
        daemon_thread.name = f"DaemonSyncThread-{self.pid}"
        daemon_thread.start()
        
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
                
                # 1. 自动为所有在线设备建连并拉流
                for cam in active_cameras:
                    cam_id = str(cam.get('id', ''))
                    if not cam_id: continue
                    active_ids.add(cam_id)
                    
                    loc = cam.get('location', '未知位置')
                    if self.camera_locations.get(cam_id) != loc:
                        self.camera_locations[cam_id] = loc
                    
                    # --- 视频拉流自动启动 ---
                    video_url = cam.get('rtsp_url') or cam.get('http_url')
                    if video_url:
                        self.get_or_create_capture(cam_id, video_url)
                        
                    # --- 音频拉流自动启动 ---
                    audio_url = cam.get('voice_rtsp_url')
                    if audio_url and cam_id not in self.muted_cameras:
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
        # 使用专用锁防止瞬间并发启动两个进程
        with self.audio_start_lock:
            if camera_id in self.audio_processes:
                proc = self.audio_processes[camera_id]['proc']
                url = self.audio_processes[camera_id]['url']
                
                # 如果进程还活着且 URL 没变，保持运行
                if proc.poll() is None and url == stream_url:
                    return
                # 否则杀掉旧的，准备重建
                self.stop_audio(camera_id, locked=True)
                
            print(f"[PID:{self.pid}] [Audio] 检测到设备上线，启动 ffplay 后台拉流: {camera_id}")
            cmd = [
                'ffplay', '-nodisp', '-rtsp_transport', 'tcp', 
                '-fflags', 'nobuffer', '-flags', 'low_delay', 
                '-framedrop', '-strict', 'experimental', 
                '-sync', 'ext', '-af', 'aresample=async=1', 
                '-probesize', '32', '-analyzeduration', '0',
                '-i', stream_url
            ]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # 必须立即存入字典，防止下一轮循环误判
                self.audio_processes[camera_id] = {
                    'proc': proc,
                    'url': stream_url
                }
            except Exception as e:
                print(f"[Audio] 启动进程失败: {e}")

            
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
                
    def set_audio_muted(self, camera_id, muted):
        """响应前端操作，将特定摄像头加入或移出静音集合，并同步停止进程"""
        with self.lock:
            if muted:
                self.muted_cameras.add(camera_id)
                self.stop_audio(camera_id, locked=True)
            else:
                self.muted_cameras.discard(camera_id)
                # 移出后，下一次 _daemon_sync_loop 会自动将其重启拉流
                
    def is_audio_playing(self, camera_id):
        """查询后台 ffplay 是否正在运行"""
        with self.audio_start_lock:
            if camera_id in self.audio_processes:
                proc = self.audio_processes[camera_id]['proc']
                return proc.poll() is None
            return False

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
                    'latest_jpeg': None,
                    'last_vlm_time': 0,
                    'vlm_result': None,
                    'vlm_frame_counter': 0,
                    'prev_frame_gray': None,
                    'frame_count': 0,
                    'person_detected': False,
                    'person_lost_time': None,
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
        
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|probesize;32|analyzeduration;0|framedrop;1"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(YOLO_IMG_SIZE))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(YOLO_IMG_SIZE * 0.75))
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
            
            try:
                while c_data['raw_queue'].full():
                    c_data['raw_queue'].get_nowait()
                c_data['raw_queue'].put_nowait(frame)
            except Exception:
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
                
                current_time = time.time()
                should_run_yolo = False
                
                if c_data.get('person_detected'):
                    c_data['person_lost_time'] = None
                    should_run_yolo = True
                elif c_data.get('person_lost_time') and (current_time - c_data['person_lost_time'] < 3.0):
                    should_run_yolo = True
                else:
                    c_data['frame_count'] += 1
                    if c_data['frame_count'] % int(FRAME_CHECK_INTERVAL) == 0:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        if c_data['prev_frame_gray'] is not None:
                            diff = cv2.absdiff(gray, c_data['prev_frame_gray'])
                            diff_pixels = cv2.countNonZero(diff)
                            total_pixels = gray.shape[0] * gray.shape[1]
                            if diff_pixels / total_pixels < float(FRAME_DIFF_PERCENT):
                                ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                                if ret:
                                    with c_data['lock']:
                                        c_data['latest_jpeg'] = jpeg.tobytes()
                                continue
                        c_data['prev_frame_gray'] = gray.copy()
                    should_run_yolo = True
                
                if not should_run_yolo:
                    ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if ret:
                        with c_data['lock']:
                            c_data['latest_jpeg'] = jpeg.tobytes()
                    continue
                
                # 核心优化 2：对齐 predict.py 的轻量级调用
                # 根据模型类型动态调整参数
                infer_args = {
                    'source': frame,
                    'conf': float(YOLO_CONF_THRESHOLD),
                    'iou': float(YOLO_IOU_THRESHOLD),
                    'classes': [0], # 仅识别 0 号类别 (通常是 person 人)
                    'verbose': False
                }
                
                # 如果是 PyTorch 模型，允许显式指定 device
                if self.model_type == 'pytorch':
                    infer_args['device'] = YOLO_DEVICE
                
                results = self.model.predict(**infer_args)
                
                has_person = len(results[0].boxes) > 0
                if has_person:
                    c_data['person_detected'] = True
                    c_data['person_lost_time'] = None
                else:
                    c_data['person_detected'] = False
                    if c_data.get('person_lost_time') is None:
                        c_data['person_lost_time'] = time.time()
                
                annotated_frame = results[0].plot()
                
                stats = self.fps_stats[camera_id]
                stats["count"] += 1
                elapsed = time.time() - stats["start_time"]
                if elapsed >= 1.0:
                    stats["display"] = stats["count"] / elapsed
                    stats["count"] = 0
                    stats["start_time"] = time.time()
                
                cv2.putText(annotated_frame, f"FPS: {stats['display']:.1f}", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # ==========================================
                # VLM 多模态大模型异步联动分析逻辑
                # ==========================================
                if VLM_ENABLED and len(results[0].boxes) > 0:
                    current_time = time.time()
                    with c_data['lock']:
                        c_data['vlm_frame_counter'] += 1
                        frame_count = c_data['vlm_frame_counter']
                        last_vlm_time = c_data.get('last_vlm_time', 0)
                        
                    # 只有达到抽帧间隔且超过冷却时间才触发
                    if frame_count >= int(VLM_FRAME_SKIP) and (current_time - last_vlm_time > float(VLM_ANALYZE_INTERVAL)):
                        with self.vlm_thread_lock:
                            if self.vlm_active_threads >= 3:
                                print(f"[VLM] 并发线程数已达上限(3)，跳过本次分析")
                            else:
                                self.vlm_active_threads += 1
                                with c_data['lock']:
                                    c_data['last_vlm_time'] = current_time
                                    c_data['vlm_frame_counter'] = 0
                                
                                threading.Thread(
                                    target=self._run_vlm_analysis, 
                                    args=(camera_id, frame.copy()), 
                                    daemon=True
                                ).start()
                
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
            for t in c_data.get('threads', []):
                t.join(timeout=3.0)

    def stop_all(self):
        with self.lock:
            for camera_id in list(self.captures.keys()):
                self.stop_capture(camera_id)

    def _run_vlm_analysis(self, camera_id, frame):
        """专门负责与 Ollama / OpenAI API 交互的后台大模型推理子线程"""
        try:
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret: return
            
            b64_image = base64.b64encode(buffer).decode('utf-8')
            
            payload = {}
            if VLM_BACKEND.lower() == 'ollama':
                payload = {
                    "model": VLM_MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": VLM_PROMPT,
                            "images": [b64_image]
                        }
                    ],
                    "stream": False,
                    "format": "json"
                }
                headers = {'Content-Type': 'application/json'}
            elif VLM_BACKEND.lower() == 'openai':
                payload = {
                    "model": VLM_MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": VLM_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_image}",
                                        "detail": "low"
                                    }
                                }
                            ]
                        }
                    ],
                    "response_format": { "type": "json_object" }
                }
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {VLM_API_KEY}'
                }
            else:
                print(f"[VLM] 未知的 VLM 后端: {VLM_BACKEND}")
                return

            print(f"[VLM] 正在向 {VLM_BACKEND} 引擎发送行为分析请求...")
            start_time = time.time()
            
            # 使用较长超时时间（大模型处理图片通常需要 2-10 秒）
            response = requests.post(VLM_API_BASE, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                resp_json = response.json()
                content = ""
                
                # 兼容 Ollama 和 OpenAI 的返回结构
                if VLM_BACKEND.lower() == 'ollama':
                    content = resp_json.get('message', {}).get('content', '{}')
                else:
                    content = resp_json['choices'][0]['message']['content']
                
                # 尝试解析大模型返回的严格 JSON
                try:
                    result_dict = json.loads(content)
                    print(f"[VLM] 分析完成 (耗时: {time.time() - start_time:.1f}s), 结果: {result_dict}")
                    
                    with self.lock:
                        c_data = self.captures.get(camera_id)
                        if c_data:
                            with c_data['lock']:
                                c_data['vlm_result'] = result_dict
                    if result_dict.get('is_violent', False):
                        self._handle_violent_capture(camera_id, frame, result_dict)
                        
                except json.JSONDecodeError:
                    print(f"[VLM] 解析大模型返回的 JSON 失败, 原文: {content}")
            else:
                print(f"[VLM] 请求失败，状态码: {response.status_code}, {response.text}")
                
        except Exception as e:
            print(f"[VLM] 大模型请求异常: {e}")
        finally:
            with self.vlm_thread_lock:
                self.vlm_active_threads -= 1

    def _handle_violent_capture(self, camera_id, frame, vlm_result):
        """当 VLM 检测到暴力行为时，自动抓拍图片、保存数据库、并推送 SocketIO 警报"""
        try:
            upload_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'static', 'captures'
            )
            os.makedirs(upload_path, exist_ok=True)
            
            filename = f"violent_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join(upload_path, filename)
            cv2.imwrite(filepath, frame)
            
            location = self.camera_locations.get(str(camera_id), '未知位置')
            if location == '未知位置':
                try:
                    from blueprints.mqtt_manager import mqtt_manager
                    if mqtt_manager and mqtt_manager.latest_jetson_info:
                        for cam in mqtt_manager.latest_jetson_info.get('cameras', []):
                            if str(cam.get('id', '')) == str(camera_id):
                                loc = cam.get('location', '未知位置')
                                self.camera_locations[str(camera_id)] = loc
                                location = loc
                                break
                except Exception:
                    pass
            
            threat_level = vlm_result.get('threat_level', 'low')
            behavior_type = vlm_result.get('behavior_type', 'normal')
            num_people = vlm_result.get('num_people_involved', 0)
            evidence = vlm_result.get('evidence', '')
            description = vlm_result.get('description', '')
            
            try:
                from blueprints.models import Capture
                from blueprints import db
                
                if not self.app:
                    print("[VLM 抓拍] 警告: Flask 应用实例未注入，跳过数据库写入")
                else:
                    with self.app.app_context():
                        capture = Capture(
                            camera_id=camera_id,
                            location=location,
                            image_path=f"captures/{filename}",
                            thumbnail_path=f"captures/{filename}",
                            violation_type=f"{behavior_type}({threat_level})",
                            threat_level=threat_level,
                            num_people_involved=num_people,
                            evidence=evidence,
                            capture_time=datetime.now()
                        )
                        db.session.add(capture)
                        db.session.commit()
                        print(f"[VLM 抓拍] 图片已保存: {filename}, 违规类型: {behavior_type}, 威胁等级: {threat_level}")
            except Exception as e:
                print(f"[VLM 抓拍] 数据库写入失败: {e}")
                try:
                    db.session.rollback()
                except Exception:
                    pass
            
            try:
                from exts import socketio
                socketio.emit('violent_alert', {
                    'camera_id': camera_id,
                    'location': location,
                    'threat_level': threat_level,
                    'behavior_type': behavior_type,
                    'num_people_involved': num_people,
                    'description': description,
                    'evidence': evidence,
                    'image_path': f"/static/captures/{filename}",
                    'capture_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, namespace='/')
                print(f"[VLM 警报] 已推送暴力行为告警: 摄像头 {camera_id} @ {location} [{threat_level}]")
            except Exception as e:
                print(f"[VLM 警报] SocketIO 推送失败: {e}")
                
        except Exception as e:
            print(f"[VLM 抓拍] 自动抓拍处理异常: {e}")


video_inference = VideoInference()

