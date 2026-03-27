#include <iostream>
#include <memory>
#include "camera_status.h"
#include "capture_thread.h"
#include "publisher_thread.h"
#include <yaml-cpp/yaml.h>

int main() {
    YAML::Node config = YAML::LoadFile("config.yaml");
    
    std::string mqtt_server = "mqtt://" + config["mqtt"]["server"].as<std::string>();
    std::string mqtt_topic = config["mqtt"]["topic"].as<std::string>();
    int publish_interval = config["mqtt"]["publish_interval"].as<int>();
    
    std::string device = config["camera"]["device"].as<std::string>();
    int width = config["camera"]["width"].as<int>();
    int height = config["camera"]["height"].as<int>();
    int fps = config["camera"]["fps"].as<int>();
    std::string rtsp_url = config["camera"]["rtsp_url"].as<std::string>();
    
    std::string camera_id = config["info"]["id"].as<std::string>();
    std::string location = config["info"]["location"].as<std::string>();
    std::string http_url = config["info"]["http_url"].as<std::string>();
    
    CameraStatus status;
    status.width = width;
    status.height = height;
    status.camera_id = camera_id;
    status.location = location;
    status.http_url = http_url;
    
    CaptureThread capture(status, device, width, height, fps, rtsp_url);
    capture.Start();
    
    PublisherThread publisher(status, mqtt_server, mqtt_topic, publish_interval,
                             camera_id, location, http_url, width, height);
    publisher.Start();
    
    std::cout << "服务已启动，按 Enter 键退出..." << std::endl;
    std::cin.get();
    
    capture.Stop();
    publisher.Stop();
    
    std::cout << "服务已停止" << std::endl;
    return 0;
}