#ifndef PUBLISHER_THREAD_H
#define PUBLISHER_THREAD_H

#include <thread>
#include <string>
#include <memory>
#include "camera_status.h"

namespace mqtt { class async_client; }

class PublisherThread {
public:
    PublisherThread(CameraStatus& status, const std::string& server, 
                    const std::string& topic, int interval,
                    const std::string& camera_id, const std::string& location,
                    const std::string& http_url, int width, int height);
    ~PublisherThread();
    
    void Start();
    void Stop();
    bool IsRunning() const;
    bool IsConnected() const;
    
private:
    void Run();
    std::string BuildJsonMessage();
    
    CameraStatus& status_;
    std::thread thread_;
    std::string server_;
    std::string topic_;
    int interval_;
    std::string camera_id_;
    std::string location_;
    std::string http_url_;
    int width_;
    int height_;
    bool running_;
    bool connected_;
    std::unique_ptr<mqtt::async_client> client_;
};

#endif
