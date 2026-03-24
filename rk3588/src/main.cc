#include <stdio.h>
#include <memory>
#include <sys/time.h>
#include "opencv2/core/core.hpp"
#include "opencv2/highgui/highgui.hpp"
#include "opencv2/imgproc/imgproc.hpp"
#include <thread>
#include <iostream>


int main(int argc, char** argv)
{

    int width = 1280;
    int height = 720;
    int fps = 60;

    std::string video_name = "/dev/video0";

    cv::VideoCapture capture;


    std::string pipeline = "v4l2src device=" + video_name +
        " ! image/jpeg, width=" + std::to_string(width) + "+, height=" + std::to_string(height) + "+, framerate=60/1 ! "
        "jpegdec ! videoconvert ! appsink";
    capture.open(pipeline, cv::CAP_GSTREAMER);

    // 如果没有GStreamer环境的话使用下面这个
    // capture.open(std::string(video_name));

    if (!capture.isOpened())
    {
        printf("打开摄像头失败！\n");
        return -1;
    }

    // FFmpeg 推流命令
    std::string cmd =
        "ffmpeg -y "
        "-f rawvideo -pix_fmt bgr24 -s " + std::to_string(width) + "x" + std::to_string(height) +
        " -r " + std::to_string(fps) +
        " -i - "
        "-c:v h264_rkmpp -preset ultrafast -tune zerolatency "
        "-fflags nobuffer -flags low_delay "
        "-rtsp_transport udp "
        "-f rtsp rtsp://fnas:8554/rk3588";

    struct timeval time;
    gettimeofday(&time, nullptr);
    auto beforeTime = time.tv_sec * 1000 + time.tv_usec / 1000;
    int frames = 0;

    while (capture.isOpened())
    {
        cv::Mat frame;          // 存储每一帧图像
        capture >> frame;       // 从摄像头读取一帧

        // 如果读取失败（摄像头断开等），退出循环
        if (frame.empty())
        {
            std::cout << "读取帧失败！" << std::endl;
            break;
        }

        frames++;
        if (frames >= 60) {
            gettimeofday(&time, nullptr);
            auto currentTime = time.tv_sec * 1000 + time.tv_usec / 1000;
            printf("60帧平均帧率: %.2f fps\n", 60.0 / float(currentTime - beforeTime) * 1000.0);
            beforeTime = currentTime;
            frames = 0;
        }

        // 打开管道写入 FFmpeg
        FILE* ffmpeg = popen(cmd.c_str(), "w");
        if (!ffmpeg) {
            std::cerr << "Failed to open ffmpeg pipe!" << std::endl;
            return;
        }
    }

    capture.release();
    cv::destroyAllWindows();
    return 0;
}