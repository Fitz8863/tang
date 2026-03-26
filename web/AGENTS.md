# AGENTS.md - Code Guidelines for This Project

## 全局规则 (Global Rules)

**必须始终使用中文回答所有问题。** (Always answer all questions in Chinese.)

## 1. Project Overview

- **Project Name**: 校园安防智能监测系统 (Campus Security Intelligent Monitoring System)
- **Framework**: Flask 3.1+ with Blueprint architecture
- **Database**: MySQL (host: 127.0.0.1, port: 3306, user: root, password: heweijie, db: bishe) via SQLAlchemy 2.0
- **Frontend**: HTML + Bootstrap 5 + JavaScript (Jinja2 templates)
- **Message Queue**: MQTT (paho-mqtt) for camera commands
- **Real-time**: Flask-SocketIO for live updates
- **Python Version**: 3.10+
- **Environment**: Conda env named `bishe`

## 2. Build / Run Commands

### Start the Application
```bash
# Ensure you are in the project root
conda activate bishe
python app.py
```
App runs on `http://0.0.0.0:5000` with SocketIO support.

### Database Setup
Tables are auto-created on app startup via `db.create_all()` in `blueprints/__init__.py` called by `init_db(app)`.
To initialize manually:
```bash
mysql -u root -pheweijie -e "CREATE DATABASE IF NOT EXISTS bishe DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;"
```

## 3. Testing & Linting

### Testing Commands
```bash
# Run all tests (if any)
pytest tests/

# Run a specific test file
pytest tests/test_auth.py

# Run a single test case
pytest tests/test_auth.py::test_login
```

### Linting Commands
```bash
# Run Black for formatting
black .

# Run Flake8 for linting
flake8 . --max-line-length=120
```

## 4. Code Style Guidelines

### 4.1 Structure
- `app.py`: Entry point, registers blueprints and initializes extensions.
- `config.py`: Configuration variables.
- `exts.py`: Extensions (db, socketio, etc.) instances to avoid circular imports.
- `blueprints/`: Modular logic split by feature.
- `templates/`: Jinja2 templates inheriting from `base.html`.
- `static/`: CSS, JS, and uploaded captures.

### 4.2 Import Order
Group imports and separate with a blank line:
1. Standard library (`os`, `json`, `datetime`)
2. Third-party (`flask`, `sqlalchemy`, `flask_socketio`)
3. Local application imports (`.models`, `exts`, `config`)

```python
import os
from datetime import datetime

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from .models import User
from exts import db
```

### 4.3 Naming Conventions
- **Files/Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Blueprints**: `snake_case` with `_bp` suffix (e.g., `auth_bp`)

### 4.4 Blueprint Structure & API Design
- Use `url_prefix` in Blueprint definitions.
- API Endpoints should be prefixed with `/api/` and return `jsonify()`.
- UI routes return `render_template()`.

### 4.5 Error Handling
- **Database**: Wrap in `try-except`, use `db.session.rollback()` on failure.
- **API**: Return JSON with `error` key and appropriate HTTP status code (400, 401, 403, 404, 500).
- **UI**: Use `flash(message, category)` for user feedback.

### 4.6 Role-Based Access Control (RBAC)
- Roles: `admin`, `assistant`, `user`.
- Use `@admin_required` or `@super_admin_required` decorators from `blueprints.auth`.
- `admin_required` allows `admin` and `assistant`.
- `super_admin_required` allows only `admin`.

## 5. Agent Instructions

- **Circular Imports**: Always use `exts.py` for shared extensions.
- **Proactivity**: Before implementing, check if a similar pattern exists in `blueprints/`.
- **Documentation**: If adding a new feature, update the README if necessary.
- **Verification**: Run `flake8` before claiming a task is done.
- **Plans**: Create a `todowrite` list for multi-step tasks.
