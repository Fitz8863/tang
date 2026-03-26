# 校园安防智能监测系统 最终实施计划 (v1.1)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按照毕设项目 (`bishe/web`) 的风格，构建一个包含 MySQL 后端、蓝图架构、左侧导航栏以及超级管理员与游客权限区分的安防系统。

**Architecture:** 采用扁平化的蓝图模式（`blueprints/` 目录）。

**Tech Stack:** Flask, MySQL (PyMySQL), Flask-SQLAlchemy, Flask-Login, Bootstrap 5.

---

## Chunk 1: 项目核心初始化 [DONE]
- [x] **Step 1: 创建 exts.py**
初始化 db, login_manager。

- [x] **Step 2: 编写 config.py**
同步毕设项目的 HOSTNAME, PORT, USERNAME, PASSWORD (heweijie) 等。

- [x] **Step 3: 编写 app.py**
显式安装 pymysql 驱动，配置 Blueprint 注册及 setup_admin 逻辑。

## Chunk 2: 数据库与模型 [DONE]
- [x] **Step 1: 定义 User 模型**
字段 id, username, password_hash (256), role, created_at。

- [x] **Step 2: 初始化数据库**
自动创建 campus_security 数据库及 users 表。

## Chunk 3: 蓝图与路由逻辑 [DONE]
- [x] **Step 1: Auth 模块**
实现登录、注销、注册逻辑（默认角色 guest）。

- [x] **Step 2: User Management 模块**
实现超级管理员专属的用户列表与删除功能。

- [x] **Step 3: Main 模块**
实现首页仪表盘展示。

## Chunk 4: 前端 UI [DONE]
- [x] **Step 1: 侧边导航栏布局**
在 base.html 中实现左侧固定菜单及权限显示逻辑。

- [x] **Step 2: 扁平化模板结构**
所有 HTML 文件直接存放在 templates/ 根目录下。
