# sftlogapi v2 - 高性能日志查询系统
# 单镜像部署 (Flask + SQLite + APScheduler)
# 版本：2.0.0

FROM python:3.9-slim

LABEL maintainer="xiegm900209"
LABEL version="2.0.0"
LABEL description="sftlogapi v2 - 高性能日志查询系统 (SQLite + MessagePack)"

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    HOST=0.0.0.0 \
    PORT=5000 \
    DB_PATH=/data/index/logs_index.db \
    LOG_BASE_DIR=/data/logs \
    CACHE_TTL=3600 \
    CACHE_MAX_SIZE=10000

# 工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY frontend/ ./frontend/

# 创建数据目录
RUN mkdir -p /data/logs /data/index

# 初始化数据库
COPY backend/models/schema.sql /tmp/schema.sql
RUN sqlite3 /data/index/logs_index.db < /tmp/schema.sql

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# 暴露端口
EXPOSE ${PORT}

# 启动命令
CMD ["python3", "backend/app.py"]
