FROM nvidia/cuda:13.3.0-cudnn-devel-ubuntu24.04@sha256:5c9fb04c50d925fc6a97739ee66f00f95e611fca1c82e6e84d9f560d61f3280e

ARG OPENCV_VERSION=4.13.0
# Target SM version, e.g. 8.6 (RTX 30xx), 8.9 (RTX 40xx). Empty = auto-detect (slower build).
ARG CUDA_ARCH_BIN=""

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config \
    python3 python3-dev python3-pip python3-venv \
    libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    libgtk-3-dev libatlas-base-dev gfortran \
  && rm -rf /var/lib/apt/lists/*

ENV VENV_PATH=/opt/venv
ENV PATH="$VENV_PATH/bin:$PATH"
RUN python3 -m venv $VENV_PATH

RUN git clone --branch "${OPENCV_VERSION}" --depth 1 \
      https://github.com/opencv/opencv.git /opt/opencv && \
    git clone --branch "${OPENCV_VERSION}" --depth 1 \
      https://github.com/opencv/opencv_contrib.git /opt/opencv_contrib && \
    cmake -S /opt/opencv -B /opt/opencv/build \
      -D CMAKE_BUILD_TYPE=Release \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D OPENCV_EXTRA_MODULES_PATH=/opt/opencv_contrib/modules \
      -D WITH_CUDA=ON \
      -D ENABLE_FAST_MATH=1 \
      -D CUDA_FAST_MATH=1 \
      -D WITH_CUBLAS=1 \
      -D BUILD_opencv_python3=ON \
      -D "PYTHON3_EXECUTABLE=$(which python3)" \
      -D "PYTHON3_PACKAGES_PATH=$(python3 -c 'import site; print(site.getsitepackages()[0])')" \
      -D BUILD_EXAMPLES=OFF \
      ${CUDA_ARCH_BIN:+-D "CUDA_ARCH_BIN=${CUDA_ARCH_BIN}"} && \
    cmake --build /opt/opencv/build --parallel "$(nproc)" && \
    cmake --install /opt/opencv/build && \
    ldconfig && \
    rm -rf /opt/opencv /opt/opencv_contrib

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assets/models /app/assets/models
ENV IMGTOOLS_M8_MODELS_DIR=/app/assets/models

COPY . /app
RUN pip install --no-cache-dir --no-deps . && \
    useradd --no-create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser
ENTRYPOINT ["python3", "-m", "imgtools_m8"]
CMD ["--help"]
