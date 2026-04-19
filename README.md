# 校园安防智能监测系统 (Campus Security Intelligent Monitoring System)

基于 **Flask (Python)** + **OpenCV/GStreamer (C++)** 的端到端校园安防实时监测解决方案。系统采用**云边协同架构**：边缘端（RK3588）负责视频采集与 AI 推理，Web 端负责数据管理、告警展示与 MQTT 远程设备控制。

## 🌟 系统架构

```
┌──────────────────────────────────────────────────────┐
│                    Web 管理端 (Flask)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ 用户认证  │ │ 仪表盘   │ │ 告警管理  │ │ 设备设置  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │  YOLO 推理引擎 + 多模态大模型(VLM) 行为分析       │ │
│  └──────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │  MQTT Broker 通信 (设备注册 / 配置下发 / 告警推送) │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────┘
                           │ MQTT / HTTP API
┌──────────────────────────▼───────────────────────────┐
│                边缘端 (RK3588 开发板)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐  │
│  │ V4L2 摄像 │ │ GStreamer│ │ RK MPP H.264 硬件编码 │  │
│  │ 头采集    │ │ 推流     │ │ + RTSP 推流           │  │
│  └──────────┘ └──────────┘ └──────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## 📦 功能特性

### Web 管理端 (`web/`)
- **🔒 用户认证与 RBAC 权限**：注册/登录/会话管理，支持 `admin` / `assistant` / `user` 三级角色
- **📹 实时视频监控**：多路摄像头 WebRTC/RTSP 流并发播放
- **🤖 AI 智能检测**：内置 YOLO 目标检测（yolo26n），支持校园违规行为实时推理
- **🧠 多模态大模型联动**：接入千问/Qwen VL 等大模型，对疑似违规画面进行深度语义分析，自动生成行为描述与威胁等级评估
- **⚠️ 行为告警管理**：抓拍记录流展示、图片预览、按时间/地点/类型筛选、数据大屏统计
- **📡 MQTT 物联网集成**：设备注册与管理、MQTT 配置持久化、远程参数下发（置信度/IoU 阈值、缩放比例等）
- **📱 响应式设计**：Bootstrap 5 深色主题，兼容桌面与移动端

### 边缘端 (`rk3588/`)
- **📷 多路摄像头采集**：基于 V4L2 的 MJPEG 格式视频捕获，支持多摄像头并发
- **🎬 GStreamer 硬编码推流**：利用 RK3588 MPP 硬件 H.264 编码器，通过 `rtspclientsink` 推送至 MediaMTX 服务器
- **📡 MQTT 状态上报**：周期性向 Broker 发布设备与摄像头状态信息

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **Web 后端** | Flask 3.1+, Blueprint 模块化架构 |
| **数据库** | MySQL 5.7+ / SQLAlchemy 2.0 ORM |
| **身份认证** | Flask-Login + Flask-Bcrypt |
| **AI 推理** | ONNX Runtime, OpenCV, NumPy |
| **多模态大模型** | 通义千问 Qwen VL (DashScope API) |
| **消息队列** | MQTT (paho-mqtt) |
| **实时通信** | Flask-SocketIO |
| **前端** | HTML5 + Jinja2 + Bootstrap 5 + Font Awesome |
| **边缘采集** | OpenCV + V4L2 (Linux) |
| **边缘推流** | GStreamer + MPP H.264 (RK3588 硬件加速) |
| **流媒体服务** | MediaMTX (RTSP/WebRTC) |
| **构建工具** | CMake 3.4.1+ |

---

## 📁 项目结构

```
tang/
├── web/                        # Flask Web 管理端
│   ├── app.py                  # 应用入口 (自动初始化数据库、MQTT、AI 守护进程)
│   ├── config.py               # 全局配置 (数据库/MQTT/YOLO/VLM 参数)
│   ├── exts.py                 # Flask 扩展实例 (db, socketio, login_manager)
│   ├── requirements.txt        # Python 依赖
│   ├── cameras.json            # 摄像头默认配置
│   ├── system_config.json      # 系统配置
│   │
│   ├── blueprints/             # 功能蓝图 (MVC 控制器层)
│   │   ├── __init__.py         # 数据库初始化 + LoginManager 配置
│   │   ├── models.py           # 数据模型 (User, Capture, MqttConfig)
│   │   ├── main.py             # 首页仪表盘
│   │   ├── auth.py             # 用户认证 (登录/注册/注销)
│   │   ├── user_management.py  # 用户管理 (仅 admin)
│   │   ├── capture.py          # 告警抓拍上传与查询 API
│   │   ├── video_stream.py     # 视频流读取与摄像头状态管理
│   │   ├── video_inference.py  # YOLO 推理 + VLM 行为分析后台守护进程
│   │   ├── mqtt_manager.py     # MQTT 客户端 (连接管理/消息发布/订阅)
│   │   └── settings.py         # MQTT 配置与远程参数下发
│   │
│   ├── model/                  # AI 模型文件 (yolo26n.onnx)
│   ├── templates/              # Jinja2 模板页面
│   ├── static/                 # 静态资源 (CSS/JS/抓图文件)
│   └── tests/                  # 单元测试
│
├── rk3588/                     # C++ 边缘端推流程序 (RK3588)
│   ├── CMakeLists.txt          # CMake 构建配置
│   ├── config.yaml             # 设备与摄像头 YAML 配置
│   └── src/
│       ├── main.cc             # 主程序 (摄像头管理 + MQTT 状态发布)
│       └── before.cc           # (备用测试代码)
│
├── .vscode/                    # VSCode 开发配置 (C++ lint/编译参数)
└── AGENTS.md                   # AI Agent 开发规范指南
```

---

## 🚀 快速开始

### Web 管理端

#### 1. 环境准备

```bash
# 使用 Conda 创建并激活环境
conda create -n bishe python=3.10
conda activate bishe
```

#### 2. 安装依赖

```bash
cd web
pip install -r requirements.txt
```

> **注意**: `requirements.txt` 中包含了 ROS 2 等大量系统级依赖。如果仅需运行 Web 端核心功能，可手动安装最小依赖集：
> ```bash
> pip install Flask==3.1.3 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 \
>             Flask-Bcrypt==1.0.1 Flask-SocketIO PyMySQL==1.1.2 SQLAlchemy==2.0.48 \
>             paho-mqtt==2.1.0 opencv-python-headless numpy bcrypt Werkzeug
> ```

#### 3. 配置数据库

启动 MySQL 并创建数据库：
```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS campus_security DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;"
```

修改 `web/config.py` 中的数据库连接参数：
```python
USERNAME = 'root'
PASSWORD = 'your_password'  # ← 替换为你的密码
```

#### 4. 启动服务

```bash
cd web
python app.py
```

访问 `http://0.0.0.0:5000`，首次使用需注册账号。数据库表会自动创建。

---

### 边缘端 (RK3588)

#### 1. 编译

```bash
cd rk3588/build
cmake ..
make
```

#### 2. 运行

```bash
./build/main
```

#### 3. 配置

编辑 `rk3588/config.yaml`，配置 MQTT 服务器地址、摄像头设备路径、视频参数等。

---

## 📡 API 文档（边缘端接入）

### 抓拍图片上传

当边缘设备检测到违规行为时，调用此接口上传图片和告警信息。

- **接口**: `POST /capture/upload`
- **Content-Type**: `multipart/form-data`
- **参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | ✅ | 抓拍图片 |
| `camera_id` | String | ✅ | 摄像头编号 |
| `location` | String | ✅ | 抓拍地点 |
| `violation_type` | String | ✅ | 违规类型 (如：攀爬围栏、打架斗殴) |

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
requests.post(url, files=files, data=data)
```

### MQTT 配置指令下发

边缘设备订阅特定主题以接收配置更改指令：

- **主题规则**: `{topic_prefix}/{camera_id}/command` (默认: `jetson/camera/{camera_id}/command`)
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

## ⚙️ 配置说明

### YOLO 推理参数 (`config.py`)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `YOLO_CONF_THRESHOLD` | 0.65 | 目标检测置信度阈值 |
| `YOLO_IOU_THRESHOLD` | 0.45 | NMS IoU 阈值 |
| `YOLO_IMG_SIZE` | 640 | 推理输入分辨率 |
| `YOLO_DEVICE` | 'cpu' | 推理设备 ('cpu' / 'cuda') |
| `FRAME_DIFF_PERCENT` | 0.10 | 帧差静默阈值（画面静止时跳过推理） |
| `FRAME_CHECK_INTERVAL` | 2 | 帧差检测频率 |

### VLM 多模态大模型 (`config.py`)

| 参数 | 说明 |
|------|------|
| `VLM_ENABLED` | 是否启用大模型联动分析 |
| `VLM_BACKEND` | 后端类型: `'openai'` (兼容 DashScope 等) 或 `'ollama'` |
| `VLM_API_BASE` | API 地址 |
| `VLM_API_KEY` | API Key（Ollama 可留空） |
| `VLM_MODEL_NAME` | 模型名称 (如 `qwen2.5-vl-72b-instruct`) |

### 设备注册管理

`REGISTERED_DEVICES` 列表中定义允许接入系统执行 AI 推理的边缘设备。
只有在此列表中的 `device_id` 才会被后端允许拉流和推理。

---

## ❓ 常见问题

**Q: 监控页面看不到视频画面？**  
A: 确保 `cameras.json` 中的 `webrtc_url` 可访问。非 localhost 环境下 WebRTC 需 HTTPS 支持。同时确认 MediaMTX 服务已正常运行。

**Q: 数据库表没有自动创建？**  
A: 检查 `config.py` 中的数据库密码是否正确，并确认已执行 `CREATE DATABASE` 语句。应用启动时会通过 `db.create_all()` 自动建表。

**Q: 如何修改 MQTT Broker 地址？**  
A: 修改 `config.py` 中的 `MQTT_BROKER` 和 `MQTT_PORT`，或在系统设置页面进行配置（配置会持久化到数据库）。

**Q: VLM 大模型分析不生效？**  
A: 确认 `VLM_ENABLED = True`，`VLM_API_KEY` 已正确填写，且网络可以访问对应的 API 地址。系统会按 `VLM_ANALYZE_INTERVAL` 冷却时间进行节流。

---

## 📄 许可证

本项目仅供学习与研究使用。
