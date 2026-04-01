from flask import Flask, render_template
from flask_bcrypt import Bcrypt
import config
import os

from exts import socketio

app = Flask(__name__,
template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
static_folder=os.path.join(os.path.dirname(__file__), 'static'))

app.config.from_object(config)

bcrypt = Bcrypt(app)
socketio.init_app(app)

from blueprints import init_db
from blueprints.mqtt_manager import init_mqtt
init_db(app)
init_mqtt(app)


from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.capture import capture_bp
from blueprints.settings import settings_bp
from blueprints.user_management import user_mgmt_bp
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(capture_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(user_mgmt_bp)

# 在系统启动时强制唤醒后台 AI 守护进程，接管所有边缘设备的自动拉流
# 核心修复：通过检查 WERKZEUG_RUN_MAIN 环境变量，确保在开启 Reloader 的情况下也只运行一次 AI 实例化
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.config.get('DEBUG'):
    try:
        from blueprints.video_inference import video_inference
        video_inference.app = app
        print("[System] 后台视频监控/推理守护进程已成功唤醒（主进程单例）。")
    except Exception as e:
        print(f"[System] 警告：后台视频守护进程启动失败: {e}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
