# 校园安防智能监测系统 - Web 管理端

基于 **Flask 3.1** 的校园安防实时监测 Web 管理平台，支持多路视频流监控、AI 违规行为检测、抓拍告警管理、MQTT 远程设备控制与多模态大模型行为深度分析。

> **配套组件**：本系统需搭配 [`rk3588/`](../rk3588) 边缘端程序使用。RK3588 负责摄像头视频采集与 RTSP 推流，本 Web 端负责管理、AI 推理与数据展示。

---

## 🌟 功能特性

- **🔒 用户认证与 RBAC 权限** — 完整的登录/注册/会话管理，支持 `admin`（超级管理员）、`assistant`（助理）、`user`（普通用户）三级角色
- **📹 实时视频监控** — 多摄像头 WebRTC / RTSP 视频流并发播放，支持音频流联动
- **🤖 YOLO AI 推理引擎** — 内置后台守护进程（VideoInference），支持 YOLOv12/YOLO26n 模型（ONNX / OpenVINO / PyTorch），具备帧差检测静默跳过、推理队列管理、FPS 实时监控
- **🧠 多模态大模型 (VLM) 行为分析** — 接入通义千问 Qwen VL 等视觉大模型，对疑似违规画面进行深度语义分析，自动生成行为描述、威胁等级评估（low/medium/high）、涉案人数统计
- **⚠️ 告警抓拍管理** — 抓拍记录时间流展示、图片预览、按时间/地点/类型筛选、数据大屏统计
- **📡 MQTT 物联网集成** — 设备注册管理、MQTT Broker 连接维护、配置参数远程下发（置信度/IoU 阈值、缩放比例）、摄像头状态实时推送
- **👥 用户管理** — 管理员可在 Web 界面管理用户列表、修改角色、删除账号
- **📱 响应式设计** — Bootstrap 5 深色主题，兼容桌面与移动端
- **🔔 实时通信** — Flask-SocketIO 实现前后端实时数据推送

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| **核心框架** | Flask 3.1+ (Blueprint 模块化架构) |
| **数据库** | MySQL 5.7+ / SQLAlchemy 2.0 ORM |
| **身份认证** | Flask-Login 0.6.3 + Flask-Bcrypt 1.0.1 |
| **AI 推理** | Ultralytics YOLO + OpenCV + NumPy |
| **多模态大模型** | 通义千问 Qwen VL (DashScope OpenAI 兼容 API) |
| **消息队列** | MQTT (paho-mqtt 2.1) |
| **实时通信** | Flask-SocketIO |
| **前端** | HTML5 + Jinja2 + Bootstrap 5.3 + Font Awesome 6 + ES6 JavaScript |
| **流媒体** | MediaMTX (RTSP/WebRTC) |
| **Python 版本** | 3.10+ |

---

## 📁 项目结构

```
web/
├── app.py                      # 应用入口（自动初始化数据库、MQTT、AI 守护进程）
├── config.py                   # 全局配置（数据库/MQTT/YOLO/VLM）
├── exts.py                     # Flask 扩展实例（db, socketio, login_manager）
├── requirements.txt            # Python 依赖
├── cameras.json                # 摄像头默认静态配置
├── system_config.json          # 系统级配置
│
├── blueprints/                 # 功能蓝图（MVC 控制器层）
│   ├── __init__.py             # 数据库初始化 + LoginManager 配置
│   ├── models.py               # SQLAlchemy 数据模型（User, Capture, MqttConfig）
│   ├── main.py                 # 首页仪表盘路由
│   ├── auth.py                 # 用户认证（登录/注册/注销）
│   ├── user_management.py      # 用户管理（admin 专属）
│   ├── capture.py              # 告警抓拍上传与查询 API
│   ├── video_stream.py         # 视频流读取与摄像头状态管理
│   ├── video_inference.py      # YOLO 推理 + VLM 行为分析后台守护进程
│   ├── mqtt_manager.py         # MQTT 客户端（连接/发布/订阅/重连）
│   └── settings.py             # MQTT 配置与远程参数下发
│
├── model/                      # AI 模型文件（yolo26n.onnx）
├── 3rdparty/                   # 第三方库（ultralytics 等）
├── templates/                  # Jinja2 模板页面
│   ├── base.html               # 全局基础布局（导航栏/Flash 提示/页脚）
│   ├── index.html              # 首页仪表盘
│   ├── login.html              # 登录页
│   ├── register.html           # 注册页
│   ├── monitor.html            # 实时视频监控面板
│   ├── alerts.html             # 抓拍告警记录流
│   └── settings.html           # 统一设置中心
│
├── static/                     # 静态资源
│   ├── css/style.css           # 全局自定义深色主题 CSS
│   ├── bootstrap/              # Bootstrap 框架本地文件
│   ├── img/                    # UI 图片资源
│   └── captures/               # 【动态目录】存储违规抓拍图片
│
├── datasets/                   # 数据集文件（训练/测试用）
└── test_upload_capture.py      # 抓拍上传接口测试脚本
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 创建并激活 Conda 环境
conda create -n bishe python=3.10
conda activate bishe
```

### 2. 安装依赖

方式一：安装 requirements.txt 中的全部依赖（包含 ROS 2 等系统级依赖，适用于完整开发环境）：
```bash
pip install -r requirements.txt
```

方式二：仅安装核心功能最小依赖集：
```bash
pip install Flask==3.1.3 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 \
            Flask-Bcrypt==1.0.1 Flask-SocketIO PyMySQL==1.1.2 SQLAlchemy==2.0.48 \
            paho-mqtt==2.1.0 opencv-python-headless numpy bcrypt Werkzeug
```

### 3. 配置数据库

启动 MySQL 并创建数据库：
```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS campus_security DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;"
```

修改 `config.py` 中的数据库连接参数：
```python
USERNAME = 'root'
PASSWORD = 'your_password'  # ← 替换为你的 MySQL 密码
```

### 4. 启动服务

```bash
python app.py
```

服务将在 `http://0.0.0.0:5000` 启动。浏览器访问即可进入系统（首次使用需注册账号）。数据库表会在应用首次启动时通过 `db.create_all()` 自动创建。

---

## 📡 边缘端接入 API

### 抓拍图片上传接口

当边缘设备（如 Jetson Nano、RK3588 等运行目标检测模型的设备）检测到违规行为时，调用此接口上传图片和违规信息。

- **接口**: `POST /capture/upload`
- **Content-Type**: `multipart/form-data`
- **参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | ✅ | 抓拍的违规图片文件 |
| `camera_id` | String | ✅ | 摄像头编号（如："001"） |
| `location` | String | ✅ | 抓拍地点（如："西门围栏"） |
| `violation_type` | String | ✅ | 违规类型（如："攀爬围栏"、"打架斗殴"） |

**调用示例 (Python)**:
```python
import requests

url = "http://192.168.1.100:5000/capture/upload"
files = {'file': open('alert.jpg', 'rb')}
data = {
    'camera_id': '001',
    'location': '西门围栏',
    'violation_type': '攀爬围栏'
}
response = requests.post(url, files=files, data=data)
```

### MQTT 配置指令下发

边缘设备需订阅特定主题，接收来自本 Web 系统的配置更改指令：

- **主题规则**: `{topic_prefix}/{camera_id}/command`（默认: `jetson/camera/{camera_id}/command`）
- **Payload 示例**:

```json
{
  "type": "parameters",
  "value": {
    "confidence_threshold": 0.7,
    "iou_threshold": 0.5,
    "scale_ratio": 1.0
  }
}
```

---

## ⚙️ 核心配置说明

### YOLO 推理参数 (`config.py`)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `YOLO_MODEL_PATH` | `'model/yolo26n.onnx'` | 模型文件路径 |
| `YOLO_CONF_THRESHOLD` | 0.65 | 目标检测置信度阈值 |
| `YOLO_IOU_THRESHOLD` | 0.45 | NMS IoU 阈值 |
| `YOLO_DEVICE` | `'cpu'` | 推理设备（`'cpu'` / `'cuda'` / `'openvino'`） |
| `YOLO_IMG_SIZE` | 640 | 推理输入分辨率 |
| `YOLO_QUEUE_SIZE` | 1 | 推理队列深度（1 = 极致实时，增大可提高流畅度但增加延迟） |

### 帧差检测优化

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FRAME_DIFF_PERCENT` | 0.10 | 静默阈值：差异像素占比低于此值视为画面静止，跳过推理以节省算力 |
| `FRAME_CHECK_INTERVAL` | 2 | 帧差检测频率：每处理 N 帧做一次帧差对比 |

### VLM 多模态大模型分析

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VLM_ENABLED` | `True` | 是否启用大模型联动分析 |
| `VLM_BACKEND` | `'openai'` | 后端类型：`'openai'`（兼容 DashScope 等 OpenAI 兼容 API）或 `'ollama'` |
| `VLM_API_BASE` | DashScope URL | API 地址 |
| `VLM_API_KEY` | — | API Key（Ollama 本地部署可留空） |
| `VLM_MODEL_NAME` | `'qwen2.5-vl-72b-instruct'` | 模型名称 |
| `VLM_FRAME_SKIP` | 10 | 抽帧间隔（约 1-2 秒），过滤闪现残影 |
| `VLM_ANALYZE_INTERVAL` | 3.0 | 分析冷却时间（秒），防止 API 被请求淹没 |

### 设备注册管理

`config.py` 中的 `REGISTERED_DEVICES` 列表定义了允许接入系统执行 AI 推理的边缘设备。只有在此列表中的 `device_id` 才会被后端允许拉流和执行推理。

---

## 🗄️ 数据库模型

| 模型 | 说明 |
|------|------|
| **User** | 用户表（id, username, password_hash, role） |
| **Capture** | 抓拍告警表（camera_id, location, image_path, violation_type, threat_level, num_people_involved, evidence, capture_time） |
| **MqttConfig** | MQTT 配置表（broker, port, username, password, topic_prefix, mediamtx_whip_port, mediamtx_rtsp_port, is_active） |

---

## ❓ 常见问题

**Q: 监控页面看不到视频画面？**  
A: 确保 `cameras.json` 中的 `webrtc_url` 可访问。非 localhost 环境下 WebRTC 需 HTTPS 支持。同时确认 MediaMTX 服务已正常运行。

**Q: 数据库表没有自动创建？**  
A: 检查 `config.py` 中的数据库密码是否正确，并确认已执行 `CREATE DATABASE` 语句。应用启动时会通过 `db.create_all()` 自动建表。

**Q: 如何修改 MQTT Broker 地址？**  
A: 修改 `config.py` 中的 `MQTT_BROKER` 和 `MQTT_PORT`，或在系统设置页面进行配置（配置会持久化到数据库）。

**Q: VLM 大模型分析不生效？**  
A: 确认 `config.py` 中 `VLM_ENABLED = True`，`VLM_API_KEY` 已正确填写，且网络可以访问对应 API 地址。系统会按 `VLM_ANALYZE_INTERVAL` 冷却时间进行节流。

**Q: AI 推理占用 CPU 过高？**  
A: 可适当调高 `FRAME_DIFF_PERCENT`（画面静止时跳过推理），或增大 `YOLO_QUEUE_SIZE` 降低推理频率。

---

## 💻 开发指南

- 新增模块需在 `blueprints/` 目录下创建，遵循 Blueprint 蓝图分离模式。
- 数据库模型变更需在 `models.py` 内实现。由于未引入 Alembic/Flask-Migrate，若修改模型字段，需手动更新数据库或清空数据库后重启应用。
- 代码规范详见 [AGENTS.md](AGENTS.md)。

---

## 📄 许可证

本项目仅供学习与研究使用。
