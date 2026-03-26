# 校园安防智能监测系统 - 设计规格书 (Spec)
日期: 2026-03-27
版本: 1.1

## 1. 项目概述
本项目是一个基于 Flask 的校园安防系统，旨在提供实时的监控、用户管理及系统设置功能。

## 2. 技术栈
- **后端**: Flask 3.1.3 + Flask-SQLAlchemy + Flask-Login
- **数据库**: MySQL 8.0+ (PyMySQL)
- **布局风格**: 仿造毕设项目 `bishe/web` 架构。

## 3. 目录布局 (扁平化蓝图)
```text
web/
├── app.py                # 程序入口 (支持 root/admini 自动创建)
├── config.py             # 数据库配置 (USERNAME: root, PASSWORD: heweijie)
├── exts.py               # 插件独立初始化
├── blueprints/           # 核心功能模块
│   ├── auth.py           # 登录注册 (/auth/)
│   ├── main.py           # 首页及监控
│   ├── models.py         # User 模型 (password_hash 长度已设为 256)
│   └── user_management.py# 管理员管理页面 (/admin/)
├── templates/            # 模板文件 (base.html, index.html, etc.)
└── static/               # 静态资源 (css, image, bootstrap)
```

## 4. 权限逻辑
- **超级管理员 (root)**: 可访问全部导航菜单。
- **游客 (Guest)**: 仅可访问首页。
- **注册逻辑**: 新用户注册默认为 guest。
