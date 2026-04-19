import os
import json
from flask import jsonify


class StreamManager:
    def __init__(self):
        self.cameras = {}
    
    def add_camera(self, camera_id, name, webrtc_url):
        self.cameras[camera_id] = {
            'id': camera_id,
            'name': name,
            'webrtc_url': webrtc_url
        }
    
    def remove_camera(self, camera_id):
        if camera_id in self.cameras:
            del self.cameras[camera_id]
    
    def get_camera(self, camera_id):
        return self.cameras.get(camera_id)
    
    def camera_exists(self, camera_id):
        return camera_id in self.cameras
    
    def get_all_cameras(self):
        return list(self.cameras.values())
    
    def load_from_config(self, config_path):
        """从配置文件加载摄像头"""
        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            cameras = config.get('cameras', [])
            print(f"从配置文件加载到 {len(cameras)} 个摄像头")
            
            for camera in cameras:
                camera_id = camera.get('id')
                name = camera.get('name', camera_id)
                webrtc_url = camera.get('webrtc_url')
                
                if camera_id and webrtc_url:
                    self.add_camera(camera_id, name, webrtc_url)
                    print(f"成功加载摄像头: {camera_id} - {name}")
                        
        except Exception as e:
            print(f"读取配置文件失败: {str(e)}")


stream_manager = StreamManager()


# def init_cameras(config_path=None):
#     """初始化摄像头，从配置文件加载"""
#     if config_path is None:
#         config_path = os.path.join(
#             os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
#             'cameras.json'
#         )
#     # print(f"[DEBUG] Loading cameras from: {config_path}")
#     stream_manager.load_from_config(config_path)


# def get_camera_info(camera_id):
#     """获取摄像头信息"""
#     camera = stream_manager.get_camera(camera_id)
#     if camera:
#         return jsonify({
#             'id': camera['id'],
#             'name': camera['name'],
#             'webrtc_url': camera['webrtc_url']
#         }), 200
#     return jsonify({'error': 'Camera not found'}), 404


def list_cameras():
    """列出所有摄像头 (同时包含静态配置和动态发现)"""
    from blueprints.mqtt_manager import mqtt_manager
    
    all_cameras = []
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for cam in config.get('cameras', []):
                    all_cameras.append({
                        'id': str(cam['id']),
                        'name': cam.get('location', f"静态源 {cam['id']}"),
                        'webrtc_url': 'static_source',
                        'is_dynamic': False,
                        'is_static': True
                    })
        except Exception as e:
            print(f"[Stream] 加载静态配置失败: {e}")

    mqtt_connected = False
    if mqtt_manager and mqtt_manager.connected:
        mqtt_connected = True
        active_info = mqtt_manager.get_active_cameras()
        
        existing_ids = {c['id'] for c in all_cameras}
        
        for cam in active_info:
            cam_id = str(cam['id'])
            if cam_id not in existing_ids:
                all_cameras.append({
                    'id': cam_id,
                    'name': cam.get('location', f"动态摄像头 {cam_id}"),
                    'webrtc_url': cam.get('http_url'),
                    'is_dynamic': True,
                    'is_static': False
                })
            else:
                for c in all_cameras:
                    if c['id'] == cam_id:
                        c['is_dynamic'] = True
                        c['webrtc_url'] = cam.get('http_url')
    
    return jsonify({
        'cameras': all_cameras,
        'mqtt_connected': mqtt_connected
    }), 200
