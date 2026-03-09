# AutoISO — 前后端一体镜像，目标 Linux Debian x86
# 阶段 1：构建前端
FROM node:20-bookworm-slim AS frontend
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev
COPY frontend/ ./
RUN npm run build

# 阶段 2：运行后端并挂载前端静态资源
FROM python:3.12-slim-bookworm
WORKDIR /app

# 安装 xorriso（ISO 制作）
RUN apt-get update && apt-get install -y --no-install-recommends xorriso \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /app/dist ./static

# 数据与日志持久化（宿主机挂载）
ENV PYTHONUNBUFFERED=1
ENV AUTOISO_DATA_DIR=/app/data
VOLUME ["/app/data"]

EXPOSE 7150
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7150"]
