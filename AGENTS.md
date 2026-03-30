# AGENTS.md - 代码规范与开发指南

## 全局规则

- **必须始终使用中文回答所有问题**
- 本项目是双仓库结构：`web/` (Flask) 和 `rk3588/` (C++)

---

## 1. 项目结构

```
tang/
├── web/                    # Flask Web 应用 (Python 3.10+)
│   ├── app.py              # 应用入口
│   ├── config.py           # 配置
│   ├── exts.py             # Flask 扩展实例
│   ├── blueprints/         # 蓝图模块
│   ├── templates/          # Jinja2 模板
│   └── static/             # 静态资源
├── rk3588/                 # C++ RTSP 推流程序
│   ├── CMakeLists.txt      # CMake 构建配置
│   ├── src/main.cc         # 主程序 (OpenCV + GStreamer)
│   └── build/              # 编译输出目录
└── .vscode/                # VSCode 配置
```

---

## 2. 构建/运行命令

### Web 应用 (Flask)
```bash
conda activate bishe
python web/app.py
# 访问 http://0.0.0.0:5000
mysql -u root -pheweijie -e "CREATE DATABASE IF NOT EXISTS bishe DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;"
```

### C++ 程序 (RK3588)
```bash
cd rk3588/build && cmake .. && make
./build/main
```

---

## 3. 测试与 Linting

### Python
```bash
pytest web/tests/              # 运行所有测试
pytest web/tests/test_auth.py  # 运行单个文件
pytest web/tests/test_auth.py::test_login  # 运行单个用例
black web/                     # 格式化
flake8 web/ --max-line-length=120  # 检查
```

---

## 4. 代码风格指南

### 4.1 Python (Web)

#### 导入顺序
```python
import os
from datetime import datetime

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from .models import User
from exts import db
```

#### 命名规范
- 文件/模块: `snake_case.py`
- 类: `PascalCase`
- 函数/变量: `snake_case`
- 常量: `UPPER_SNAKE_CASE`
- 蓝图: `snake_case` + `_bp` 后缀 (如 `auth_bp`)

#### Blueprint 结构
- API 路由: `/api/` 前缀，返回 `jsonify()`
- UI 路由: 返回 `render_template()`

#### 错误处理
- 数据库: `try-except` + `db.session.rollback()`
- API: 返回 JSON + 状态码 (400/401/403/404/500)
- UI: 使用 `flash(message, category)`

#### RBAC 角色
- `admin`: 管理员
- `assistant`: 助理
- `user`: 普通用户
- 使用 `@admin_required` 和 `@super_admin_required` 装饰器

### 4.2 C++ (RK3588)

#### 编译标准
- C++17 (`-std=c++17`)
- 启用 pthread

#### 警告配置 (VSCode)
```json
"-Wall", "-Wextra", "-Wpedantic", "-Wshadow",
"-Wformat=2", "-Wcast-align", "-Wconversion",
"-Wsign-conversion", "-Wnull-dereference"
```

#### 命名规范
- 文件: `snake_case.cc`
- 类/函数: `PascalCase`
- 变量: `snake_case`
- 常量: `kPascalCase` (枚举) 或 `UPPER_SNAKE_CASE`

#### 代码风格
- 大括号独立一行
- 使用 `std::` 而非 `using namespace std`
- 优先使用 `const` 引用传参
- 智能指针管理资源 (`std::unique_ptr`)

---

## 5. 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | Flask 3.1+ (Blueprint 架构) |
| 数据库 | SQLAlchemy 2.0 + MySQL |
| 认证 | Flask-Login + Flask-Bcrypt |
| 物联网 | MQTT (paho-mqtt) |
| 实时通信 | Flask-SocketIO |
| 视频处理 | OpenCV + GStreamer |
| 构建工具 | CMake 3.4.1+ |

---

## 6. 开发注意事项

- **循环导入**: 使用 `exts.py` 管理共享扩展
- **数据库**: 修改模型字段后需手动更新或重建
- **MQTT**: 主题格式 `{MQTT_TOPIC_PREFIX}/{camera_id}/command`
- **视频流**: WebRTC 需要 HTTPS 支持生产环境

---

## 7. 验证步骤

```bash
# Python
flake8 web/ --max-line-length=120
black --check web/

# C++
cd rk3588/build && cmake .. && make
```