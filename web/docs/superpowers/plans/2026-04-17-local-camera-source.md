# 增加本地测试摄像头源 (cameras.json) 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现在没有远程 MQTT 设备在线时，也能根据 `cameras.json` 加载本地 MP4 或 USB 摄像头源并进行 AI 推理。

**Architecture:** 
1. 扩展 `video_stream.list_cameras` 逻辑，同时返回 MQTT 动态设备和 `cameras.json` 静态设备。
2. 优化 `settings.video_stream` 路由，支持从 `cameras.json` 获取 `source` 作为推理源。
3. 保持前端展示逻辑不变，实现无缝切换。

**Tech Stack:** Python, Flask, OpenCV

---

### Task 1: 扩展摄像头列表逻辑以支持静态配置

**Files:**
- Modify: `blueprints/video_stream.py`

- [ ] **Step 1: 修改 list_cameras 函数，加入读取 cameras.json 的逻辑**

```python
def list_cameras():
    """列出所有摄像头 (包括静态配置和动态MQTT发现)"""
    from blueprints.mqtt_manager import mqtt_manager
    
    # 1. 获取静态配置的摄像头
    static_cameras = []
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for cam in config.get('cameras', []):
                    static_cameras.append({
                        'id': cam['id'],
                        'name': cam.get('location', f"测试摄像头 {cam['id']}"),
                        'webrtc_url': 'local_test', # 占位符，前端只要有值即可
                        'is_dynamic': False,
                        'is_test': True
                    })
        except Exception as e:
            print(f"读取静态配置失败: {e}")

    # 2. 获取动态MQTT发现的摄像头
    dynamic_cameras = []
    mqtt_connected = False
    if mqtt_manager and mqtt_manager.connected:
        mqtt_connected = True
        active_info = mqtt_manager.get_active_cameras()
        for cam in active_info:
            dynamic_cameras.append({
                'id': cam['id'],
                'name': cam.get('location', f"摄像头 {cam['id']}"),
                'webrtc_url': cam.get('http_url'), # 兼容前端
                'is_dynamic': True,
                'is_test': False
            })
    
    # 合并列表 (以动态优先或全部显示，这里选择全部显示以便测试)
    all_cameras = static_cameras + dynamic_cameras
    
    return jsonify({
        'cameras': all_cameras,
        'mqtt_connected': True # 即使MQTT未连，我们也让前端显示测试源
    }), 200
```

- [ ] **Step 2: 验证 API 输出**
使用 `curl` 检查 `/api/cameras` 接口是否返回了 `cameras.json` 中的设备。

### Task 2: 优化视频流推理接口以支持本地源

**Files:**
- Modify: `blueprints/settings.py`

- [ ] **Step 1: 修改 video_stream 路由，支持 source 查找**

```python
@settings_bp.route('/api/video/stream/<camera_id>')
def video_stream(camera_id):
    """YOLO推理视频流接口"""
    try:
        from blueprints.mqtt_manager import mqtt_manager
        from blueprints.video_inference import video_inference
        
        stream_url = None
        
        # 1. 尝试从动态 MQTT 数据中查找
        if mqtt_manager and mqtt_manager.connected and mqtt_manager.latest_jetson_info:
            cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
            for cam in cameras_data:
                if str(cam.get('id', '')) == str(camera_id):
                    stream_url = cam.get('rtsp_url') or cam.get('http_url', '')
                    break
        
        # 2. 如果没找到，尝试从静态 cameras.json 中查找 source
        if not stream_url:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for cam in config.get('cameras', []):
                        if str(cam.get('id', '')) == str(camera_id):
                            stream_url = cam.get('source')
                            break
        
        if not stream_url:
            return f"未找到摄像头 {camera_id} 的有效流地址或测试源", 404
        
        # 获取或创建视频捕获
        video_inference.get_or_create_capture(camera_id, stream_url)
        
        # ... 后续 generate 逻辑保持不变 ...
```

- [ ] **Step 2: 验证视频拉取**
访问监控页面，检查 ID 为 `002` 的摄像头是否能播放 `check.mp4` 且带有推理框。
