#include "voice_capture_thread.h"
#include <iostream>
#include <chrono>
#include <cstdio>
#include <signal.h>

static volatile bool g_ffmpeg_running = true;

void signal_handler(int) {
    g_ffmpeg_running = false;
}

VoiceCaptureThread::VoiceCaptureThread(CameraStatus& status, const std::string& rtsp_url)
    : status_(status), rtsp_url_(rtsp_url), running_(false) {}

VoiceCaptureThread::~VoiceCaptureThread() {
    Stop();
}

void VoiceCaptureThread::Start() {
    if (!running_) {
        running_ = true;
        thread_ = std::thread(&VoiceCaptureThread::Run, this);
    }
}

void VoiceCaptureThread::Stop() {
    if (running_) {
        running_ = false;
        g_ffmpeg_running = false;
        if (thread_.joinable()) {
            thread_.join();
        }
    }
}

bool VoiceCaptureThread::IsRunning() const {
    return running_;
}

void VoiceCaptureThread::Run() {
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    std::string cmd = 
        "ffmpeg -f alsa -channels 1 -sample_rate 44100 -i hw:3,0 "
        "-c:a aac -b:a 128k "
        "-f rtsp -rtsp_transport tcp " + rtsp_url_;

    std::cout << "音频推流命令: " << cmd << std::endl;

    FILE* pipe = popen(cmd.c_str(), "w");
    if (!pipe) {
        std::cerr << "无法启动 ffmpeg" << std::endl;
        running_ = false;
        return;
    }

    std::cout << "音频推流已启动 → " << rtsp_url_ << std::endl;

    auto last_print = std::chrono::steady_clock::now();

    while (running_ && g_ffmpeg_running) {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - last_print).count();
        if (elapsed >= 5) {
            std::cout << "音频推流中..." << std::endl;
            last_print = now;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    pclose(pipe);
    std::cout << "音频推流线程已退出" << std::endl;
}