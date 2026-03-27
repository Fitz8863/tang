#include "camera_manager.h"

CameraManager::~CameraManager() {
    StopAll();
}

void CameraManager::AddCamera(const std::string& camera_id, const std::string& location,
                              const std::string& http_url, const std::string& device,
                              int width, int height, int fps, const std::string& rtsp_url) {
    CameraContext ctx;
    ctx.status = std::make_unique<CameraStatus>();
    ctx.status->camera_id = camera_id;
    ctx.status->location = location;
    ctx.status->http_url = http_url;
    ctx.status->width = width;
    ctx.status->height = height;
    
    ctx.capture = std::make_unique<CaptureThread>(*ctx.status, device, width, height, fps, rtsp_url);
    ctx.capture->Start();
    cameras_.push_back(std::move(ctx));
}

void CameraManager::StopAll() {
    for (auto& ctx : cameras_) {
        if (ctx.capture) {
            ctx.capture->Stop();
        }
    }
    cameras_.clear();
}

std::vector<std::reference_wrapper<CameraStatus>> CameraManager::GetAllStatuses() {
    std::vector<std::reference_wrapper<CameraStatus>> result;
    for (auto& ctx : cameras_) {
        if (ctx.status) {
            result.push_back(std::ref(*ctx.status));
        }
    }
    return result;
}