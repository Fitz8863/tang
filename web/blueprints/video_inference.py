import cv2
import threading
import numpy as np
import time
import os
from ultralytics import YOLO

class VideoInference:
    def __init__(self, model_path='model/yolov8n.pt'):
        self.model = None
        self.model_path = model_path
        self.captures = {}
        self.lock = threading.Lock()
        self.running = True
        
    def load_model(self):
        if self.model is None:
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                self.model_path
            )
            
            # 检查模型文件状态
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"模型文件不存在: {full_path}")
            
            size_mb = os.path.getsize(full_path) / (1024 * 1024)
            print(f"[VideoInference] 正在从 CPU 加载模型: {full_path} (大小: {size_mb:.2f} MB)")
            
            if size_mb < 0.1:
                raise ValueError(f"模型文件异常太小 ({size_mb:.2f} MB)，可能已损坏或仅为 LFS 指针")
                
            try:
                # 显式使用 CPU 加载
                self.model = YOLO(full_path)
                self.model.to('cpu')
                print(f"[VideoInference] YOLO模型已成功加载到 CPU")
            except Exception as e:
                print(f"[VideoInference] YOLO 初始化失败: {e}")
                raise e
    
    def get_or_create_capture(self, camera_id, stream_url):
        with self.lock:
            if camera_id not in self.captures:
                self.captures[camera_id] = {
                    'url': stream_url,
                    'thread': None,
                    'frame': None,
                    'lock': threading.Lock(),
                    'stop_event': threading.Event()
                }
                thread = threading.Thread(target=self._capture_loop_rtsp, args=(camera_id,), daemon=True)
                self.captures[camera_id]['thread'] = thread
                thread.start()
            elif self.captures[camera_id]['url'] != stream_url:
                self.stop_capture(camera_id)
                return self.get_or_create_capture(camera_id, stream_url)
            return self.captures[camera_id]
    
    def _capture_loop_rtsp(self, camera_id):
        cap_data = self.captures[camera_id]
        url = cap_data['url']
        print(f"[VideoInference] 启动RTSP读取线程: {camera_id}, URL: {url}")
        
        # 强制使用 TCP 传输，并设置更小的缓冲区防止延迟累积
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        fail_count = 0
        while not cap_data['stop_event'].is_set():
            ret, frame = cap.read()
            if not ret:
                fail_count += 1
                if fail_count % 30 == 0:
                    print(f"[VideoInference] RTSP读取失败 {camera_id}, 尝试重连...")
                    cap.release()
                    time.sleep(2)
                    cap = cv2.VideoCapture(url)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                continue
            
            fail_count = 0
            processed_frame = self._process_frame(frame)
            with cap_data['lock']:
                cap_data['frame'] = processed_frame
        
        cap.release()
        print(f"[VideoInference] 停止RTSP线程: {camera_id}")

    def _process_frame(self, frame):
        if self.model is None:
            try:
                self.load_model()
            except Exception as e:
                print(f"[VideoInference] 模型加载失败: {e}")
                return frame
        
        try:
            results = self.model(frame, verbose=False)
            for result in results:
                return result.plot()
        except Exception as e:
            if not hasattr(self, '_last_error_time') or (time.time() - self._last_error_time > 5):
                print(f"[VideoInference] 推理错误: {e}")
                self._last_error_time = time.time()
        
        return frame
    
    def get_frame(self, camera_id):
        with self.lock:
            if camera_id not in self.captures:
                return None
            
            cap_data = self.captures[camera_id]
            with cap_data['lock']:
                if cap_data['frame'] is None:
                    return None
                
                ret, jpeg = cv2.imencode('.jpg', cap_data['frame'])
                if ret:
                    return jpeg.tobytes()
                return None
    
    def stop_capture(self, camera_id):
        with self.lock:
            if camera_id in self.captures:
                self.captures[camera_id]['stop_event'].set()
                del self.captures[camera_id]

    def stop_all(self):
        with self.lock:
            for camera_id in list(self.captures.keys()):
                self.stop_capture(camera_id)

video_inference = VideoInference()
