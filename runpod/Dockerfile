# RunPod GPU-optimized Dockerfile
FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-liberation \
    fonts-freefont-ttf \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY static/ ./static/

# Create necessary directories
RUN mkdir -p uploads output

# Set environment variables
ENV PYTHONPATH=/workspace
ENV CUDA_VISIBLE_DEVICES=0

# GPU optimization environment variables
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
ENV MOVIEPY_TEMP_DIR=/tmp/moviepy

# Copy RunPod handlers
COPY runpod/handler.py .
COPY runpod/handler_simple.py .

# Set the entry point to use simplified handler first
CMD ["python", "handler_simple.py"]