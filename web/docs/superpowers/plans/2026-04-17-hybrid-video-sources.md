# 视频源融合（MQTT 动态流 + cameras.json 静态流）实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现监控系统同时支持 MQTT 动态上线的 RTSP 流和 `cameras.json` 中配置的本地/静态视频源（MP4/USB 摄像头），并使二者在前端监控页面同时展示并进行 AI 推理。

**Architecture:** 
1. **统一发现逻辑**：重写 `blueprints/video_stream.py` 中的 `list_cameras`，合并静态配置和动态心跳数据。
2. **统一拉流逻辑**：优化 `blueprints/settings.py` 中的视频流路由，建立“先查动态，后查静态”的源寻址机制。
3. **守护进程适配**：由于 `video_inference` 的守护进程主要依赖 MQTT 心跳维持，我们需要在其中加入对静态源的定期检查，或在请求流时按需启动。

**Tech Stack:** Python, Flask, OpenCV, MQTT

---

### Task 1: 合并摄像头发现逻辑

**Files:**
- Modify: `blueprints/video_stream.py`

- [ ] **Step 1: 更新 list_cameras 函数，实现双源合并**

```python
def list_cameras():
    """列出所有摄像头 (同时包含静态配置和动态发现)"""
    from blueprints.mqtt_manager import mqtt_manager
    
    # 1. 强制读取静态配置 (cameras.json)
    all_cameras = []
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for cam in config.get('cameras', []):
                    all_cameras.append({
                        'id': cam['id'],
                        'name': cam.get('location', f"静态源 {cam['id']}"),
                        'webrtc_url': 'static_source', # 占位符
                        'is_dynamic': False,
                        'is_static': True
                    })
        except Exception as e:
            print(f"[Stream] 加载静态配置失败: {e}")

    # 2. 获取动态 MQTT 发现的摄像头 (如果已连接)
    mqtt_connected = False
    if mqtt_manager and mqtt_manager.connected:
        mqtt_connected = True
        active_info = mqtt_manager.get_active_cameras()
        # 为了防止 ID 冲突，我们在这里做一个简单的去重或合并逻辑
        existing_ids = {c['id'] for c in all_cameras}
        for cam in active_info:
            cam_id = str(cam['id'])
            if cam_id not in existing_ids:
                all_cameras.append({
                    'id': cam_id,
                    'name': cam.get('location', f"动态摄像头 {cam_id}"),
                    'webrtc_url': cam.get('http_url'), 
                    'is_dynamic': True,
                    'is_static': False
                })
            else:
                # 如果 ID 冲突，通常以动态数据为准（因为动态流通常是实时的）
                for c in all_cameras:
                    if c['id'] == cam_id:
                        c['is_dynamic'] = True
                        c['webrtc_url'] = cam.get('http_url')
    
    return jsonify({
        'cameras': all_cameras,
        'mqtt_connected': mqtt_connected
    }), 200
```

### Task 2: 增强视频流路由的源寻址能力

**Files:**
- Modify: `blueprints/settings.py`

- [ ] **Step 1: 修改 video_stream 路由，支持双向溯源**

```python
@settings_bp.route('/api/video/stream/<camera_id>')
def video_stream(camera_id):
    """YOLO推理视频流接口 (融合源查找)"""
    try:
        from blueprints.mqtt_manager import mqtt_manager
        from blueprints.video_inference import video_inference
        
        stream_url = None
        
        # 策略 A: 先看动态 MQTT 数据 (优先级高，通常是实时硬件)
        if mqtt_manager and mqtt_manager.connected and mqtt_manager.latest_jetson_info:
            cameras_data = mqtt_manager.latest_jetson_info.get('cameras', [])
            for cam in cameras_data:
                if str(cam.get('id', '')) == str(camera_id):
                    stream_url = cam.get('rtsp_url') or cam.get('http_url', '')
                    break
        
        # 策略 B: 如果动态库里没有，或者没连 MQTT，查静态 cameras.json
        if not stream_url:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        for cam in config.get('cameras', []):
                            if str(cam.get('id', '')) == str(camera_id):
                                stream_url = cam.get('source')
                                break
                except: pass
        
        if not stream_url:
            return f"无法定位摄像头 {camera_id} 的有效视频源", 404
        
        # 启动/获取推理实例
        video_inference.get_or_create_capture(camera_id, stream_url)
        
        # ... 后续 MJPEG generate 逻辑 ...
```

### Task 3: 优化 VideoInference 守护进程对静态源的支持

**Files:**
- Modify: `blueprints/video_inference.py`

- [ ] **Step 1: 修改 _daemon_sync_loop，防止静态源被意外清理**

```python
# 在 _daemon_sync_loop 中清理资源时，需要排除 cameras.json 中定义的 ID
def _daemon_sync_loop(self):
    while self.running:
        time.sleep(3.0)
        try:
            # 获取动态 ID
            active_ids = set()
            # ... 原有的 MQTT 获取逻辑 ...
            
            # 获取静态 ID (防止静态源在心跳丢失时被 stop_capture)
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cameras.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    static_config = json.load(f)
                    for cam in static_config.get('cameras', []):
                        active_ids.add(str(cam['id']))
            
            # ... 原有的资源清理逻辑 (现在 cameras_to_stop 会保留静态 ID) ...
```

- [ ] **Step 2: 验证静态源的长期运行能力**
检查 `check.mp4` 在循环播放时是否稳定。
