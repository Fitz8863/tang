import os
import json
from flask_login import login_required, current_user
from flask import Blueprint, render_template, request, jsonify, make_response, abort
from . import db, login_manager
from .models import MqttConfig
from .auth import admin_required

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'system_config.json')

def load_system_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'allow_registration': True}

def save_system_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

@settings_bp.before_request
def before_request():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    # 视频/音频流接口允许所有登录用户访问
    if request.path.startswith('/settings/api/video/stream/') or request.path.startswith('/settings/api/audio/stream/'):
        return
    if not current_user.is_admin:
        abort(403)

@settings_bp.route('/api/system/config', methods=['GET'])
def get_system_config():
    config = load_system_config()
    return jsonify(config), 200

@settings_bp.route('/api/system/config', methods=['POST'])
def update_system_config():
    data = request.json
    config = load_system_config()
    
    if 'allow_registration' in data:
        config['allow_registration'] = bool(data['allow_registration'])
    
    save_system_config(config)
    return jsonify({'message': '配置已更新', 'config': config}), 200

@settings_bp.route('/')
def index():
    """系统设置页面"""
    return render_template('settings.html')

@settings_bp.route('/api/mqtt/status', methods=['GET'])
def get_mqtt_status():
    """获取MQTT连接状态"""
    try:
        from blueprints.mqtt_manager import mqtt_manager
        if mqtt_manager and mqtt_manager.broker:
            return jsonify({
                'connected': mqtt_manager.connected,
                'broker': mqtt_manager.broker,
                'port': mqtt_manager.port
            }), 200
        return jsonify({'connected': False}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/mqtt/connect', methods=['POST'])
def mqtt_connect():
    data = request.json
    broker = data.get('broker')
    port = data.get('port', 1883)
    username = data.get('username', '')
    password = data.get('password', '')
    save = data.get('save', False)
    
    if not broker:
        return jsonify({'error': '请输入服务器地址'}), 400
    
    try:
        from blueprints.mqtt_manager import MQTTManager
        import blueprints.mqtt_manager as mqtt_module
        
        if mqtt_module.mqtt_manager and mqtt_module.mqtt_manager.client:
            mqtt_module.mqtt_manager.disconnect()
        
        mqtt_module.mqtt_manager = MQTTManager(
            broker=broker,
            port=port,
            username=username,
            password=password,
            topic_prefix='jetson/camera'
        )
        
        success = mqtt_module.mqtt_manager.connect()
        
        if success:
            if save:
                MqttConfig.query.update({'is_active': False})
                
                new_config = MqttConfig(
                    broker=broker,
                    port=port,
                    username=username,
                    password=password,
                    is_active=True
                )
                db.session.add(new_config)
                db.session.commit()
            
            return jsonify({
                'connected': True,
                'broker': broker,
                'port': port
            }), 200
        else:
            return jsonify({'connected': False, 'error': '连接失败'}), 500
            
    except Exception as e:
        return jsonify({'connected': False, 'error': str(e)}), 500

@settings_bp.route('/api/mqtt/disconnect', methods=['POST'])
def mqtt_disconnect():
    try:
        import blueprints.mqtt_manager as mqtt_module
        if mqtt_module.mqtt_manager and mqtt_module.mqtt_manager.client:
            mqtt_module.mqtt_manager.disconnect()
        
        response = make_response(jsonify({'message': '已断开连接'}), 200)
        response.set_cookie('mqtt_auto_connect', 'false', max_age=30*24*60*60)
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/mqtt/configs', methods=['GET'])
def get_mqtt_configs():
    """获取所有保存的MQTT配置（按broker去重）"""
    # 按broker分组，只取最新的记录
    configs = db.session.query(MqttConfig).order_by(MqttConfig.broker, MqttConfig.created_at.desc()).all()
    
    # 去重，保留每个broker最新的记录
    seen = set()
    unique_configs = []
    for c in configs:
        if c.broker not in seen:
            seen.add(c.broker)
            unique_configs.append(c)
    
    return jsonify({
        'configs': [{
            'id': c.id,
            'broker': c.broker,
            'port': c.port,
            'username': c.username or '',
            'is_active': c.is_active
        } for c in unique_configs]
    }), 200

@settings_bp.route('/apijetson/info', methods=['GET'])
def get_jetson_info():
    """获取最新的Jetson设备信息"""
    try:
        import time
        from blueprints.mqtt_manager import mqtt_manager
        if not mqtt_manager or not mqtt_manager.connected:
            return jsonify({'error': 'MQTT未连接'}), 400
            
        if not mqtt_manager.latest_jetson_info:
            return jsonify({'message': '等待数据中...', 'data': None}), 200
            
        # 检查是否超时 (10秒未收到心跳包视为断开)
        is_online = (time.time() - mqtt_manager.last_info_time) < 10
        
        return jsonify({
            'message': 'success',
            'data': mqtt_manager.latest_jetson_info,
            'is_online': is_online
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/api/mqtt/camera-stats', methods=['GET'])
def get_camera_stats():
    """获取摄像头实时状态（分辨率、帧率等）"""
    try:
        from blueprints.mqtt_manager import mqtt_manager
        if not mqtt_manager or not mqtt_manager.connected:
            return jsonify({'cameras': []}), 200
            
        if not mqtt_manager.latest_jetson_info:
            return jsonify({'cameras': []}), 200
        
        cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
        cameras = []
        for cam in cameras_data:
            res = cam.get('resolution', {})
            cameras.append({
                'id': cam.get('id', ''),
                'resolution': f"{res.get('width', 0)}x{res.get('height', 0)}@{res.get('fps', 0)}fps"
            })
        
        return jsonify({'cameras': cameras}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/video/stream/<camera_id>')
def video_stream(camera_id):
    """YOLO推理视频流接口"""
    try:
        from blueprints.mqtt_manager import mqtt_manager
        from blueprints.video_inference import video_inference
        
        stream_url = None
        
        if mqtt_manager and mqtt_manager.connected and mqtt_manager.latest_jetson_info:
            cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
            for cam in cameras_data:
                if str(cam.get('id', '')) == str(camera_id):
                    stream_url = cam.get('rtsp_url') or cam.get('http_url', '')
                    break
        
        if not stream_url:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        for cam in config.get('cameras', []):
                            if str(cam.get('id', '')) == str(camera_id):
                                stream_url = cam.get('source')
                                break
                except Exception:
                    pass
        
        if not stream_url:
            return f"无法定位摄像头 {camera_id} 的有效视频源", 404
        
        video_inference.get_or_create_capture(camera_id, stream_url)
        
        def generate():
            import time
            last_frame = None
            while True:
                frame_data = video_inference.get_frame(camera_id)
                if frame_data:
                    if frame_data != last_frame:
                        last_frame = frame_data
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                    time.sleep(1.0 / 30.0)
                else:
                    time.sleep(1.0 / 30.0)
        
        response = make_response(generate())
        response.headers['Content-Type'] = 'multipart/x-mixed-replace; boundary=frame'
        return response
        
    except Exception as e:
        return str(e), 500


@settings_bp.route('/api/vlm/status/<camera_id>', methods=['GET'])
def get_vlm_status(camera_id):
    """获取特定摄像头的最新 VLM 分析结果"""
    try:
        from blueprints.video_inference import video_inference
        with video_inference.lock:
            c_data = video_inference.captures.get(camera_id)
        
        if not c_data:
            return jsonify({'active': False}), 200
        
        with c_data['lock']:
            vlm_result = c_data.get('vlm_result')
            last_vlm_time = c_data.get('last_vlm_time', 0)
        
        if not vlm_result or last_vlm_time == 0:
            return jsonify({'active': False}), 200
        
        import time
        elapsed = time.time() - last_vlm_time
        
        return jsonify({
            'active': True,
            'result': vlm_result,
            'timestamp': last_vlm_time,
            'elapsed': round(elapsed, 1)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 通过 VideoInference 统一全局管理音频进程，防止双重启动
@settings_bp.route('/api/audio/control/<camera_id>', methods=['POST'])
def audio_control(camera_id):
    """前端音频控制接口：只改变后台静音状态标志位，绝不自己启动进程"""
    try:
        from blueprints.video_inference import video_inference
        data = request.get_json() or {}
        action = data.get('action')
        
        if action == 'status':
            is_playing = video_inference.is_audio_playing(camera_id)
            return jsonify({"playing": is_playing}), 200

        elif action == 'stop':
            video_inference.set_audio_muted(camera_id, True)
            return jsonify({"status": "stopped"}), 200

        elif action == 'play':
            video_inference.set_audio_muted(camera_id, False)
            return jsonify({"status": "play_requested"}), 200

        return jsonify({"error": "无效的 action"}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500




