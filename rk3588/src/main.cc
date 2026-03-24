#include <opencv2/opencv.hpp>
#include <iostream>
#include <string>
#include <chrono>

int main()
{
    // ====================== 参数配置 ======================
    int width = 1920;
    int height = 1080;
    int fps = 30;

    std::string device = "/dev/video0";
    std::string rtsp_url = "rtsp://10.60.83.159:8554/rk3588";

    // ====================== Pipeline 1：读取摄像头 (MJPEG) ======================
    std::string read_pipeline =
    "v4l2src device=" + device + " ! "
    "image/jpeg, width=(int)" + std::to_string(width) +
    ", height=(int)" + std::to_string(height) +
    ", framerate=" + std::to_string(fps) + "/1 ! "
    "jpegdec ! "
    "videoconvert ! video/x-raw, format=BGR ! "
    "appsink drop=1 max-buffers=1";

    std::cout << "正在打开摄像头 (MJPEG " << width << "x" << height << "@" << fps << "fps)..." << std::endl;

    cv::VideoCapture cap(read_pipeline, cv::CAP_GSTREAMER);

    if (!cap.isOpened())
    {
        std::cerr << "错误：无法打开摄像头 pipeline！" << std::endl;
        return -1;
    }

    std::cout << "摄像头打开成功！开始推流..." << std::endl;

    // ====================== Pipeline 2：RK3588 硬件编码推流（已修正） ======================
    std::string push_pipeline =
        "appsrc ! "
        "videoconvert ! "
        "video/x-raw,format=NV12,width=" + std::to_string(width) +
        ",height=" + std::to_string(height) +
        ",framerate=" + std::to_string(fps) + "/1 ! "
        "mpph264enc bps=8000000 ! "
        "h264parse ! "
        "rtspclientsink location=" + rtsp_url;


    cv::VideoWriter writer(push_pipeline, cv::CAP_GSTREAMER, 0, fps, cv::Size(width, height), true);

    if (!writer.isOpened())
    {
        std::cerr << "错误：无法打开推流 pipeline！" << std::endl;
        std::cerr << "请运行下面命令查看 rtspclientsink 支持的属性：" << std::endl;
        std::cerr << "gst-inspect-1.0 rtspclientsink" << std::endl;
        return -1;
    }

    std::cout << "RTSP 推流已启动 → " << rtsp_url << " (8Mbps)" << std::endl;

    // ====================== FPS 计算 ======================
    auto last_time = std::chrono::high_resolution_clock::now();
    float current_fps = 0.0f;
    int frame_count = 0;
    auto fps_update_time = last_time;

    // ====================== 主循环 ======================
    cv::Mat frame;
    while (true)
    {
        cap >> frame;

        if (frame.empty())
        {
            std::cerr << "读取摄像头帧失败！" << std::endl;
            break;
        }

        auto now = std::chrono::high_resolution_clock::now();
        frame_count++;
        float elapsed = std::chrono::duration<float>(now - fps_update_time).count();
        if (elapsed >= 1.0f)
        {
            current_fps = frame_count / elapsed;
            frame_count = 0;
            fps_update_time = now;
        }

        std::string fps_text = "FPS: " + std::to_string(int(current_fps));
        cv::putText(frame, fps_text, cv::Point(frame.cols - 130, 40),
                    cv::FONT_HERSHEY_SIMPLEX, 1.0, cv::Scalar(0, 255, 0), 2);

        writer << frame;                 // 送入硬件编码 + 推流

    }

    cap.release();
    writer.release();
    cv::destroyAllWindows();

    std::cout << "程序已退出，推流停止。" << std::endl;
    return 0;
}