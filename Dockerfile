# helper/image_utils needs cv2 built with CUDA and DNN support
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu20.04

ARG OPENCV_VERSION=4.7.0

# install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config \
    libjpeg-dev libpng-dev libtiff-dev \
    libopencv-dev libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    libgtk-3-dev libatlas-base-dev gfortran \
  && rm -rf /var/lib/apt/lists/*

# download and build OpenCV
WORKDIR /opt
RUN git clone --branch ${OPENCV_VERSION} --depth 1 \
      https://github.com/opencv/opencv.git && \
    git clone --branch ${OPENCV_VERSION} --depth 1 \
      https://github.com/opencv/opencv_contrib.git

WORKDIR /opt/opencv
RUN mkdir build && cd build && \
    cmake \
      -D CMAKE_BUILD_TYPE=Release \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D OPENCV_EXTRA_MODULES_PATH=/opt/opencv_contrib/modules \
      -D WITH_CUDA=ON \
      -D ENABLE_FAST_MATH=1 \
      -D CUDA_FAST_MATH=1 \
      -D WITH_CUBLAS=1 \
      -D BUILD_opencv_python3=ON \
      -D PYTHON3_EXECUTABLE=$(which python3) \
      -D BUILD_EXAMPLES=OFF \
      .. && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig

# install your python dependencies
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y python3-pip && \
    pip3 install --no-cache-dir -r requirements.txt

# copy your code and models
COPY . /app

# expose a port if you have an API
# EXPOSE 8000

CMD ["python3", "-m", "imgtools_m8.main"]