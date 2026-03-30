FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-venv python3-pip \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1 \
    git wget curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python

COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt ultralytics

# 预下载 YOLO 模型
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

EXPOSE 8001
CMD ["python", "-m", "uvicorn", "backend.train_service:app", "--host", "0.0.0.0", "--port", "8001"]
