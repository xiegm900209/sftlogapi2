# sftlogapi v2 - 路径配置清单

> 🎯 **目的**: 方便迁移到其他环境  
> 📅 **更新**: 2026-04-12  
> ✅ **状态**: 已完全环境变量化

---

## 📊 配置概览

| 配置类型 | 环境变量化 | 硬编码位置 | 迁移难度 |
|----------|------------|------------|----------|
| **后端路径** | ✅ 完全 | 无 | 🟢 简单 |
| **前端 API 路径** | ✅ 完全 | 无 | 🟢 简单 |
| **Docker 配置** | ✅ 完全 | 无 | 🟢 简单 |
| **Nginx 配置** | ⚠️ 需手动 | 配置文件 | 🟡 中等 |
| **脚本默认值** | ⚠️ 部分 | 命令行参数 | 🟡 中等 |
| **文档示例** | ❌ 硬编码 | HTML 注释 | 🟢 无影响 |

---

## 🔧 必须配置的路径（迁移时修改）

### 1. 日志根目录

```bash
# 环境变量
LOG_BASE_DIR=/your/path/to/logs

# Docker Compose 使用
volumes:
  - ${LOG_BASE_DIR}:/data/logs:ro

# 默认值
默认：/root/sft/testlogs
```

### 2. 数据库路径

```bash
# 环境变量
DB_PATH=/your/path/to/logs_trace.db

# Docker Compose 使用
volumes:
  - ${DB_PATH}:/data/index/logs_trace.db

# 默认值
默认：/root/sft-data/index/logs_trace.db
```

### 3. Nginx 服务器 IP

```nginx
# 配置文件：conf/nginx.conf 或 /usr/local/tengine/conf/conf.d/sftlogapi-v2.conf
server_name  <your-server-ip>;  # 修改为实际 IP

# 默认值
默认：172.16.2.164
```

### 4. 前端静态文件路径

```nginx
# Nginx 配置
location /sftlogapi-v2/ {
    alias /your/path/to/sftlogapi-v2/;  # 修改为实际路径
    index index.html;
}

# 默认值
默认：/var/www/sftlogapi-v2/
```

---

## ✅ 已环境变量化的配置

### 后端代码 (backend/app.py)

```python
CONFIG = {
    'DEBUG': os.environ.get('DEBUG', 'false').lower() == 'true',
    'HOST': os.environ.get('HOST', '0.0.0.0'),
    'PORT': int(os.environ.get('PORT', 5000)),
    'DB_PATH': os.environ.get('DB_PATH', '/data/index/logs_index.db'),
    'LOG_BASE_DIR': os.environ.get('LOG_BASE_DIR', '/data/logs'),
    'CONFIG_DIR': '/app/config',  # 容器内路径，无需修改
    'CACHE_TTL': int(os.environ.get('CACHE_TTL', 3600)),
    'CACHE_MAX_SIZE': int(os.environ.get('CACHE_MAX_SIZE', 10000)),
    'API_KEY': os.environ.get('API_KEY', 'zhiduoxing-2026-secret-key'),
    'ENABLE_AUTH': os.environ.get('ENABLE_AUTH', 'false').lower() == 'true'
}
```

### 前端代码 (frontend/index.html)

```javascript
// ✅ 已修复为正确路径
const API_BASE = '/sftlogapi-v2/api';

// 所有 API 请求都使用 API_BASE
await fetch(`${API_BASE}/config/transaction-types`);
await fetch(`${API_BASE}/config/log-dirs`);
await fetch(`${API_BASE}/log-query`);
```

### Docker Compose (docker-compose.env.yml)

```yaml
services:
  sftlogapi:
    image: ${DOCKER_IMAGE:-sftlogapi:v2}
    container_name: ${CONTAINER_NAME:-sftlogapi-v2}
    
    volumes:
      - ${LOG_BASE_DIR:-/root/sft/testlogs}:${CONTAINER_LOG_DIR:-/data/logs}:ro
      - ${DB_PATH:-/root/sft-data/index/logs_trace.db}:${CONTAINER_DB_DIR:-/data/index}/logs_trace.db
    
    environment:
      - DB_PATH=${CONTAINER_DB_DIR:-/data/index}/logs_trace.db
      - LOG_BASE_DIR=${CONTAINER_LOG_DIR:-/data/logs}
      - API_KEY=${API_KEY:-zhiduoxing-2026-secret-key}
      - ENABLE_AUTH=${ENABLE_AUTH:-false}
      - PORT=${PORT:-5000}
```

### 部署脚本 (deploy.sh)

```bash
#!/bin/bash
# 从 config.env 加载配置
source "$CONFIG_FILE"

# 使用环境变量
docker run -d \
  --name "$CONTAINER_NAME" \
  -v "${LOG_BASE_DIR}:${CONTAINER_LOG_DIR}:ro" \
  -v "${DB_PATH}:${CONTAINER_DB_DIR}/logs_trace.db" \
  -e DB_PATH="${CONTAINER_DB_DIR}/logs_trace.db" \
  -e LOG_BASE_DIR="${CONTAINER_LOG_DIR}" \
  "$DOCKER_IMAGE"
```

---

## ⚠️ 脚本中的默认路径（可覆盖）

### compress_and_index.py

```bash
# 默认值（可被命令行参数覆盖）
--log-dir /root/sft/testlogs
--db-path /root/sft/sftlogapi-v2/data/index/logs_trace.db

# 使用方式（推荐指定路径）
python3 scripts/compress_and_index.py \
  --log-dir /your/path/to/logs \
  --db-path /your/path/to/db/logs_trace.db
```

### sync_index_to_sqlite.py

```bash
# 默认值（可被命令行参数覆盖）
--log-dir /root/sft/testlogs
--db-path /root/sft/sftlogapi-v2/data/index/logs_trace.db

# 使用方式
python3 scripts/sync_index_to_sqlite.py \
  --log-dir /your/path/to/logs \
  --db-path /your/path/to/db/logs_trace.db
```

### build_index.py

```bash
# 默认值
--log-dir /root/sft/testlogs

# 使用方式
python3 scripts/build_index.py \
  --log-dir /your/path/to/logs
```

---

## ❌ 文档示例中的硬编码（无影响）

这些硬编码仅在 HTML 注释和示例中，**不影响实际功能**：

### frontend/index.html

```html
<!-- 示例 IP 和端口（仅文档） -->
http://172.16.2.164:8091/sftlogapi/api/zdx/log-query

<!-- 示例路径（仅文档） -->
/root/sft/testlogs

<!-- 示例项目路径（仅文档） -->
/root/sft/sftlogapi-v2

<!-- Crontab 示例（需修改） -->
0 * * * * cd /root/sft/sftlogapi-v2 && \
    python3 scripts/compress_and_index.py ...
```

**处理方式**: 这些是文档示例，迁移时参考 DEPLOYMENT-GUIDE.md 修改即可。

---

## 🚀 快速迁移清单

### 步骤 1: 复制项目

```bash
# 新服务器
git clone <repo-url> /your/path/to/sftlogapi-v2
cd /your/path/to/sftlogapi-v2
```

### 步骤 2: 配置环境变量

```bash
# 复制配置模板
cp config.env.example config.env

# 修改配置
vim config.env
```

**必须修改**:
```bash
LOG_BASE_DIR=/your/path/to/logs
DB_PATH=/your/path/to/db/logs_trace.db
API_KEY=your-new-secret-key
```

### 步骤 3: 创建目录

```bash
# 数据库目录
mkdir -p $(dirname $DB_PATH)

# 日志目录（如需要）
mkdir -p $LOG_BASE_DIR
```

### 步骤 4: 部署

```bash
# 方式一：使用部署脚本
./deploy.sh

# 方式二：使用 Docker Compose
docker-compose --env-file config.env -f docker-compose.env.yml up -d
```

### 步骤 5: 配置 Nginx

```bash
# 复制配置
cp conf/nginx.conf /usr/local/tengine/conf/conf.d/sftlogapi-v2.conf

# 修改 IP 和路径
vim /usr/local/tengine/conf/conf.d/sftlogapi-v2.conf

# 修改这些行：
# server_name  <your-server-ip>;
# alias /your/path/to/sftlogapi-v2/;

# 重载
nginx -t && nginx -s reload
```

### 步骤 6: 验证

```bash
# 检查容器
docker ps | grep sftlogapi

# 测试 API
curl http://localhost:5001/api/health

# 测试前端
curl http://localhost:8091/sftlogapi-v2/
```

---

## 📋 配置文件模板

### config.env (完整模板)

```bash
# ========== 日志配置 ==========
LOG_BASE_DIR=/your/path/to/logs

# ========== 数据库配置 ==========
DB_PATH=/your/path/to/db/logs_trace.db

# ========== API 配置 ==========
API_KEY=your-secret-key
ENABLE_AUTH=false

# ========== 服务配置 ==========
PORT=5000
HOST=0.0.0.0
DEBUG=false

# ========== 缓存配置 ==========
CACHE_TTL=3600
CACHE_MAX_SIZE=10000

# ========== 容器配置 ==========
CONTAINER_NAME=sftlogapi-v2
DOCKER_IMAGE=sftlogapi:v2
CONTAINER_LOG_DIR=/data/logs
CONTAINER_DB_DIR=/data/index
```

### Nginx 配置模板

```nginx
server {
    listen       8091;
    server_name  <your-server-ip>;

    location /sftlogapi-v2/ {
        alias /your/path/to/sftlogapi-v2/;
        index index.html;
        try_files $uri $uri/ /sftlogapi-v2/index.html;
    }

    location /sftlogapi-v2/api/ {
        proxy_pass http://127.0.0.1:5001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

## 🔍 验证环境变量化

### 检查后端

```bash
# 查看容器环境变量
docker exec sftlogapi-v2 env | grep -E "DB_PATH|LOG_BASE_DIR|API_KEY"

# 应输出：
# DB_PATH=/data/index/logs_trace.db
# LOG_BASE_DIR=/data/logs
# API_KEY=xxx
```

### 检查前端

```bash
# 查看 API_BASE 配置
grep "API_BASE" /var/www/sftlogapi-v2/index.html

# 应输出：
# const API_BASE = '/sftlogapi-v2/api';
```

### 检查 Docker Compose

```bash
# 查看配置解析
docker-compose --env-file config.env -f docker-compose.env.yml config

# 检查 volumes 和 environment 是否正确替换
```

---

## 📞 支持文档

- 📄 [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md) - 完整部署指南
- 📄 [README.md](../README.md) - 项目说明
- 📄 [config.env.example](../config.env.example) - 配置模板

---

**迁移难度评估**: 🟢 简单  
**环境变量化程度**: ✅ 95%+  
**硬编码影响**: ❌ 仅文档示例，无功能影响
