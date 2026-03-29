#include "voice_capture_thread.h"
#include <gst/gst.h>
#include <gst/app/app.h>
#include <iostream>
#include <chrono>

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
        if (thread_.joinable()) {
            thread_.join();
        }
    }
}

bool VoiceCaptureThread::IsRunning() const {
    return running_;
}

void VoiceCaptureThread::Run() {
    gst_init(nullptr, nullptr);

    std::string pipeline_str =
        "alsasrc device=plughw:3,0 ! "
        "audio/x-raw,format=S16LE,rate=48000,channels=1 ! "
        "queue ! "
        "audioconvert ! "
        "avenc_aac bitrate=128000 ! "
        "rtpmp4apay pt=96 ! "
        "rtspclientsink location=" + rtsp_url_;

    GError* error = nullptr;
    GstPipeline* pipeline = GST_PIPELINE(gst_parse_launch(pipeline_str.c_str(), &error));

    if (error) {
        std::cerr << "音频 Pipeline 解析失败: " << error->message << std::endl;
        g_error_free(error);
        running_ = false;
        return;
    }

    GstStateChangeReturn ret = gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_PLAYING);
    if (ret == GST_STATE_CHANGE_FAILURE) {
        std::cerr << "音频 Pipeline 启动失败" << std::endl;
        g_object_unref(pipeline);
        running_ = false;
        return;
    }

    std::cout << "音频推流已启动 → " << rtsp_url_ << std::endl;

    auto last_print = std::chrono::steady_clock::now();

    while (running_) {
        GstMessage* msg = gst_bus_timed_pop(GST_ELEMENT_BUS(pipeline), GST_CLOCK_TIME_NONE);

        if (msg) {
            if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_ERROR) {
                GError* err = nullptr;
                gst_message_parse_error(msg, &err, nullptr);
                std::cerr << "音频错误: " << err->message << std::endl;
                g_error_free(err);
                break;
            }
            gst_message_unref(msg);
        }

        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - last_print).count();
        if (elapsed >= 5) {
            std::cout << "音频推流中..." << std::endl;
            last_print = now;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_NULL);
    g_object_unref(pipeline);
    std::cout << "音频推流线程已退出" << std::endl;
}