cmake_minimum_required(VERSION 3.4.1)

project(main)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "-pthread")


# install target and libraries
set(CMAKE_SKIP_INSTALL_RPATH FALSE)
set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)
set(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/lib")



# opencv
find_package(OpenCV REQUIRED)
set(CMAKE_INSTALL_RPATH "lib")


message(STATUS "OpenCV libraries: ${OpenCV_LIBS}")

add_executable(main
        src/main.cc

)

target_link_libraries(main
  ${OpenCV_LIBS}
)

