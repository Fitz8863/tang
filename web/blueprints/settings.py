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
        
        if not mqtt_manager or not mqtt_manager.connected:
            return "MQTT未连接", 400
            
        if not mqtt_manager.latest_jetson_info:
            return "等待摄像头数据...", 400
        
        # 优先从心跳数据中查找对应camera_id的RTSP流地址，如果没有则退而求其次使用http流
        cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
        stream_url = None
        for cam in cameras_data:
            if str(cam.get('id', '')) == str(camera_id):
                stream_url = cam.get('rtsp_url') or cam.get('http_url', '')
                break
        
        if not stream_url:
            return f"未找到摄像头 {camera_id} 的流地址", 404
        
        # 获取或创建视频捕获
        video_inference.get_or_create_capture(camera_id, stream_url)
        
        def generate():
            while True:
                frame = video_inference.get_frame(camera_id)
                if frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                else:
                    import time
                    time.sleep(0.03)  # ~30fps
        
        response = make_response(generate())
        response.headers['Content-Type'] = 'multipart/x-mixed-replace; boundary=frame'
        return response
        
    except Exception as e:
        return str(e), 500


# 全局管理后台音频进程的字典和锁
import threading
import subprocess
audio_processes = {}
audio_lock = threading.Lock()

@settings_bp.route('/api/audio/control/<camera_id>', methods=['POST'])
def audio_control(camera_id):
    """音频控制接口：直接在服务器后台调用 ffplay 播放 RTSP 音频"""
    try:
        data = request.get_json() or {}
        action = data.get('action')
        
        with audio_lock:
            # 状态查询
            if action == 'status':
                is_playing = camera_id in audio_processes
                if is_playing:
                    # 检查进程是否意外死亡
                    proc = audio_processes[camera_id]
                    if proc.poll() is not None:
                        del audio_processes[camera_id]
                        is_playing = False
                return jsonify({"playing": is_playing}), 200

            # 停止播放
            if action == 'stop':
                proc = audio_processes.pop(camera_id, None)
                if proc:
                    proc.kill()
                    proc.wait()
                return jsonify({"status": "stopped"}), 200

            # 开启播放
            if action == 'play':
                if camera_id in audio_processes:
                    proc = audio_processes[camera_id]
                    if proc.poll() is None:
                        return jsonify({"status": "already playing"}), 200
                    else:
                        del audio_processes[camera_id]

                from blueprints.mqtt_manager import mqtt_manager
                if not mqtt_manager or not mqtt_manager.connected:
                    return jsonify({"error": "MQTT未连接"}), 400
                    
                cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
                stream_url = None
                for cam in cameras_data:
                    if str(cam.get('id', '')) == str(camera_id):
                        stream_url = cam.get('voice_rtsp_url')
                        break
                
                if not stream_url:
                    return jsonify({"error": "未找到声音流地址 (voice_rtsp_url缺失)"}), 404
                
                # 核心：使用用户提供的极致低延迟参数，在后台启动 ffplay 进程
                cmd = [
                    'ffplay', '-nodisp', '-rtsp_transport', 'tcp', 
                    '-fflags', 'nobuffer', '-flags', 'low_delay', 
                    '-framedrop', '-strict', 'experimental', '-i', stream_url
                ]
                # 丢弃 stdout/stderr 防止阻塞或刷屏控制台
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                audio_processes[camera_id] = proc
                return jsonify({"status": "started"}), 200

        return jsonify({"error": "无效的 action"}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@settings_bp.route('/api/audio/stream/<camera_id>')
def audio_stream(camera_id):
    """音频流代理接口：将 RTSP 实时转码为 MP3 流发给前端"""
    try:
        import subprocess
        from blueprints.mqtt_manager import mqtt_manager
        
        if not mqtt_manager or not mqtt_manager.connected:
            return "MQTT未连接", 400
            
        cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
        stream_url = None
        for cam in cameras_data:
            if str(cam.get('id', '')) == str(camera_id):
                stream_url = cam.get('voice_rtsp_url')
                break
        
        if not stream_url:
            return "未找到声音流地址 (voice_rtsp_url缺失)", 404
        
        def generate_audio():
            # 极致低延迟音频代理参数：
            # 1. 采用跟 ffplay 相同的输入端无缓冲策略
            # 2. 弃用高延迟的 MP3 编码，改用无压缩的 PCM (WAV) 格式直接传输
            # 3. 降低采样率到 16000Hz (足够清晰的人声)，极大减少数据传输量
            cmd = [
                'ffmpeg', 
                '-rtsp_transport', 'tcp', 
                '-fflags', 'nobuffer', 
                '-flags', 'low_delay', 
                '-i', stream_url,
                '-vn', 
                '-c:a', 'pcm_s16le', 
                '-ar', '16000', 
                '-ac', '1', 
                '-f', 'wav', 
                '-'
            ]
            # 忽略 stderr 日志输出，防止刷屏
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            
            try:
                while True:
                    # 极限微切片：从 4096 降到 512 字节，只要 ffmpeg 吐出一点点声音就立刻塞给浏览器
                    data = process.stdout.read(512)
                    if not data:
                        break
                    yield data
            except GeneratorExit:
                pass
            finally:
                process.kill()
                process.wait()

        # 返回无压缩 WAV 音频流响应
        from flask import Response
        return Response(generate_audio(), mimetype='audio/wav')
        
    except Exception as e:
        return str(e), 500
