#include "publisher_thread.h"
#include <mqtt/async_client.h>
#include <iostream>
#include <chrono>
#include <sstream>
#include <iomanip>

PublisherThread::PublisherThread(CameraStatus& status, const std::string& server,
                                 const std::string& topic, int interval,
                                 const std::string& camera_id, const std::string& location,
                                 const std::string& http_url, int width, int height)
    : status_(status), server_(server), topic_(topic), interval_(interval),
      camera_id_(camera_id), location_(location), http_url_(http_url),
      width_(width), height_(height), running_(false), connected_(false) {}

PublisherThread::~PublisherThread() {
    Stop();
}

void PublisherThread::Start() {
    if (!running_) {
        running_ = true;
        thread_ = std::thread(&PublisherThread::Run, this);
    }
}

void PublisherThread::Stop() {
    if (running_) {
        running_ = false;
        if (thread_.joinable()) {
            thread_.join();
        }
        if (connected_ && client_) {
            client_->disconnect()->wait();
        }
    }
}

bool PublisherThread::IsRunning() const {
    return running_;
}

bool PublisherThread::IsConnected() const {
    return connected_;
}

std::string PublisherThread::BuildJsonMessage() {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(4);
    
    float fps = status_.GetFps();
    int64_t timestamp = status_.GetTimestamp();
    
    oss << "{"
        << "\"timestamp_ns\":" << timestamp << ","
        << "\"cameras\":[{"
        << "\"id\":\"" << camera_id_ << "\","
        << "\"location\":\"" << location_ << "\","
        << "\"http_url\":\"" << http_url_ << "\","
        << "\"resolution\":{"
        << "\"width\":" << width_ << ","
        << "\"height\":" << height_ << ","
        << "\"fps\":" << fps << "}"
        << "}]"
        << "}";
    
    return oss.str();
}

void PublisherThread::Run() {
    try {
        client_ = std::make_unique<mqtt::async_client>(server_, "rk3588_pub");
        
        mqtt::connect_options connOpts;
        connOpts.set_keep_alive_interval(20);
        connOpts.set_clean_session(true);
        
        client_->connect(connOpts)->wait();
        connected_ = true;
        std::cout << "MQTT 连接成功，主题: " << topic_ << std::endl;
        
        while (running_) {
            auto start = std::chrono::steady_clock::now();
            
            std::string payload = BuildJsonMessage();
            auto msg = mqtt::make_message(topic_, payload, 1, false);
            client_->publish(msg)->wait();
            
            std::cout << "已发送状态信息 - FPS: " << std::fixed << std::setprecision(2) 
                      << status_.GetFps() << std::endl;
            
            auto elapsed = std::chrono::steady_clock::now() - start;
            auto sleep_time = std::chrono::seconds(interval_) - elapsed;
            if (sleep_time > std::chrono::seconds(0)) {
                std::this_thread::sleep_for(sleep_time);
            }
        }
        
        client_->disconnect()->wait();
        connected_ = false;
        std::cout << "MQTT 客户端已断开" << std::endl;
        
    } catch (const mqtt::exception& exc) {
        std::cerr << "MQTT 错误: " << exc.what() << std::endl;
        connected_ = false;
    }
}
