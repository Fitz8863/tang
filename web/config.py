SECRET_KEY='asdmmnkdnlamdl;awwd'

# 数据库基本信息
HOSTNAME='127.0.0.1'
PORT=3306
USERNAME='root'
PASSWORD='heweijie'
DATABASE = 'campus_security'
DB_URI = 'mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8'.format(USERNAME,PASSWORD,HOSTNAME,PORT,DATABASE)
SQLALCHEMY_DATABASE_URI = DB_URI

# 邮箱配置
# qvqnpnqkirdldgbb
MAIL_SERVER='smtp.qq.com'
MAIL_USE_SSL=True
MAIL_PORT=465
MAIL_USERNAME='3189801930@qq.com'
MAIL_PASSWORD='efcupjqhgltfddaj'
MAIL_DEFAULT_SENDER='3189801930@qq.com'

# MQTT配置
MQTT_BROKER='127.0.0.1'
MQTT_PORT=1883
MQTT_USERNAME=''
MQTT_PASSWORD=''

# 登记设备
# 只有在以下列表中的 device_id 才会被后端系统允许拉流和执行 AI 推理
REGISTERED_DEVICES = [
    'RK3588'
]

# YOLO 推理配置
YOLO_MODEL_PATH = 'model/yolo26n.onnx'
YOLO_CONF_THRESHOLD = 0.50
YOLO_IOU_THRESHOLD = 0.45
YOLO_DEVICE = 'cpu'
YOLO_IMG_SIZE = 640
YOLO_QUEUE_SIZE = 4  # 推理队列深度，1为极致实时，增加可提高流畅度但会增加延迟

