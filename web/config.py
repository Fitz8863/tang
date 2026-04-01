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
YOLO_CONF_THRESHOLD = 0.65
YOLO_IOU_THRESHOLD = 0.45
YOLO_DEVICE = 'cpu'
YOLO_IMG_SIZE = 640
YOLO_QUEUE_SIZE = 4  # 推理队列深度，1为极致实时，增加可提高流畅度但会增加延迟

# 多模态大模型 (VLM) 暴力行为分析配置
VLM_ENABLED = True  # 默认为 False，你可以手动改为 True 开启大模型联动分析
VLM_BACKEND = 'openai'  # 可选: 'ollama' 或 'openai' (后者兼容几乎所有商用云端 API)
VLM_API_BASE = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'  # api地址
VLM_API_KEY = 'sk-41fd6c7956c1414ba4c1662cb07ad846'  # OpenAI 等云端大模型需要的 API Key，Ollama 本地部署可留空
VLM_MODEL_NAME = 'qwen2.5-vl-72b-instruct'
# VLM_MODEL_NAME = 'llama3.2-vision:11b'  # 模型名称，如 ollama 的 'llava', 'qwen2-vl'，或 openai 的 'gpt-4o'
VLM_FRAME_SKIP = 30  # 抽帧间隔：每处理多少帧才评估一次是否交给大模型(约等于1-2秒)，过滤闪现残影
VLM_ANALYZE_INTERVAL = 4.0  # 分析冷却时间(秒)。为防止API被请求淹没，只有画面中检测到人且超过冷却时间才分析一次
VLM_PROMPT = """你是一个专业的校园安防监控行为分析专家，专门负责识别潜在暴力事件。
请仔细观察图片中的人物动作、姿势、物体和相互关系，重点关注以下情况：
- 打架斗殴：推搡、拳打脚踢、拉扯、摔倒、群体围殴等明显攻击性动作（注意区分与普通玩闹的区别）
- 持械/持刀：手中明显持有刀具、棍棒、锐器或其他可作为武器物品
- 其他异常：多人快速聚集、追逐、举手作势攻击等

请严格按照以下 JSON 格式返回结果，不要输出任何额外的思考过程、解释、Markdown 或 JSON 之外的内容：

{
  "is_violent": true/false,
  "threat_level": "low/medium/high",
  "behavior_type": "fighting/holding_weapon/pushing/gathering/chasing/normal/other",
  "description": "用中文简洁描述主要人物的动作、位置和关键视觉证据，例如：'画面左侧两名学生互相拳击，一人手持疑似刀具'",
  "num_people_involved": 整数,
  "evidence": "列出支持判断的关键视觉线索，用简短中文描述"
}
"""
