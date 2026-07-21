# Phase 3: Dockerfile
# ====================
# Đóng gói MCP Server thành container độc lập.
# Base image python:3.11-slim để tối ưu kích thước (~150MB).
FROM python:3.11-slim

# Metadata
LABEL maintainer="MindX Fresher Challenge"
LABEL description="Secure Local MCP Server with SQLite FTS5"

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Bước 1: Cài dependencies trước (tận dụng Docker layer cache)
COPY requirements.txt .
RUN apt-get update && apt-get install -y iputils-ping net-tools dnsutils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Bước 2: Copy toàn bộ source code
COPY src/ ./src/

# Bước 3: Tạo thư mục ghi chú (volume mount point)
RUN mkdir -p /app/my_notes

# Biến môi trường
ENV NOTES_DIR=/app/my_notes

# Volume để mount thư mục ghi chú từ host
VOLUME ["/app/my_notes"]

# Streamlit Server chạy ở port 8501, giao tiếp ngầm với server.py
CMD ["streamlit", "run", "src/ui.py", "--server.address=0.0.0.0"]
