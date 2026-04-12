# sftlogapi v2 - 前端部署与定时任务配置

> 📦 **版本**: 2.0.0  
> 📅 **更新**: 2026-04-12  
> 📚 **用途**: 前端静态文件部署 + 定时任务配置详解

---

## 📋 目录

1. [前端部署](#前端部署)
2. [定时任务配置](#定时任务配置)
3. [索引生成脚本](#索引生成脚本)
4. [故障排查](#故障排查)

---

## 🌐 前端部署

### 架构说明

```
┌─────────────────────────────────────┐
│  用户浏览器                          │
└────────────┬────────────────────────┘
             │ HTTP :8091
             ↓
┌─────────────────────────────────────┐
│  Tengine/Nginx                       │
│  - 静态文件：/var/www/sftlogapi-v2/  │
│  - API 代理：/sftlogapi-v2/api/       │
└────────────┬────────────────────────┘
             │ 反向代理
             ↓
┌─────────────────────────────────────┐
│  Docker 容器 (Flask:5001)            │
│  - REST API                          │
│  - SQLite 索引                       │
└─────────────────────────────────────┘
```

### 方式一：直接部署（当前使用）

#### 1. 准备前端文件

```bash
# 前端文件已构建好，位于项目目录
cd /root/sft/sftlogapi-v2

# 检查前端文件
ls -la frontend/
# 应包含：
# - index.html (主页面)
# - static/ (静态资源)
```

#### 2. 复制到 Nginx 目录

```bash
# 创建部署目录
sudo mkdir -p /var/www/sftlogapi-v2

# 复制前端文件
cp -r frontend/* /var/www/sftlogapi-v2/

# 验证文件
ls -la /var/www/sftlogapi-v2/
# 应包含：
# - index.html
# - static/
```

#### 3. 配置 Nginx/Tengine

```bash
# 创建配置文件
sudo vim /usr/local/tengine/conf/conf.d/sftlogapi-v2.conf
```

**配置内容**:
```nginx
server {
    listen       8091;
    server_name  <your-server-ip>;

    # 根路径重定向
    location = /sftlogapi-v2 {
        return 301 /sftlogapi-v2/;
    }

    # 前端静态文件
    location /sftlogapi-v2/ {
        alias /var/www/sftlogapi-v2/;
        index index.html;
        
        # SPA 路由支持
        try_files $uri $uri/ /sftlogapi-v2/index.html;
        
        # 静态资源缓存
        location ~* ^/sftlogapi-v2/.*\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API 反向代理
    location /sftlogapi-v2/api/ {
        proxy_pass http://127.0.0.1:5001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        client_max_body_size 100m;
    }

    # 健康检查
    location = /sftlogapi-v2/api/health {
        proxy_pass http://127.0.0.1:5001/api/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        access_log off;
    }
}
```

#### 4. 测试并重载

```bash
# 测试配置
sudo /usr/local/tengine/sbin/nginx -t

# 重载配置
sudo /usr/local/tengine/sbin/nginx -s reload

# 验证服务
sudo systemctl status tengine
```

#### 5. 验证部署

```bash
# 测试前端页面
curl http://localhost:8091/sftlogapi-v2/

# 测试 API
curl http://localhost:8091/sftlogapi-v2/api/health

# 浏览器访问
# http://<your-ip>:8091/sftlogapi-v2/
```

---

### 方式二：开发环境部署

#### 1. 安装依赖

```bash
cd frontend
npm install
```

#### 2. 启动开发服务器

```bash
npm run dev
```

**输出**:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

#### 3. 访问开发服务器

```
http://localhost:5173/
```

**注意**: 开发模式下需要修改 API_BASE 为后端地址

---

### 方式三：Docker 部署（可选）

如果希望前端也在容器中：

```dockerfile
# Dockerfile 中添加
FROM nginx:alpine

# 复制前端文件
COPY frontend/dist /usr/share/nginx/html/sftlogapi-v2

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## ⏰ 定时任务配置

### 定时任务说明

系统需要两个定时任务：

| 任务 | 频率 | 说明 | 脚本 |
|------|------|------|------|
| **索引生成** | 每小时 | 压缩 1 小时前的日志并生成索引 | `compress_and_index.py` |
| **索引清理** | 每天 3:00 | 清理 7 天前的索引数据 | `sync_index_to_sqlite.py` |

---

### 方式一：Crontab（推荐）

#### 1. 编辑 Crontab

```bash
crontab -e
```

#### 2. 添加定时任务

```bash
# ========== sftlogapi v2 定时任务 ==========

# 每小时执行一次：压缩并索引 1 小时前的日志
0 * * * * cd /root/sft/sftlogapi-v2 && /usr/bin/python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto --sync-sqlite >> /var/log/sftlogapi_compress.log 2>&1

# 每天 3:00 执行：清理 7 天前的索引
0 3 * * * cd /root/sft/sftlogapi-v2 && /usr/bin/python3 scripts/sync_index_to_sqlite.py --log-dir /root/sft/testlogs --cleanup --retention-days 7 >> /var/log/sftlogapi_cleanup.log 2>&1
```

#### 3. 验证 Crontab

```bash
# 查看当前 crontab
crontab -l

# 查看 cron 服务状态
systemctl status crond

# 查看 cron 日志
tail -f /var/log/cron
```

---

### 方式二：Systemd Timer

#### 1. 创建 Service 文件

**索引生成服务** (`/etc/systemd/system/sftlogapi-compress.service`):
```ini
[Unit]
Description=sftlogapi 日志压缩和索引生成
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/root/sft/sftlogapi-v2
ExecStart=/usr/bin/python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto --sync-sqlite
StandardOutput=append:/var/log/sftlogapi_compress.log
StandardError=append:/var/log/sftlogapi_compress.log
```

**索引清理服务** (`/etc/systemd/system/sftlogapi-cleanup.service`):
```ini
[Unit]
Description=sftlogapi 索引清理
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/root/sft/sftlogapi-v2
ExecStart=/usr/bin/python3 scripts/sync_index_to_sqlite.py --log-dir /root/sft/testlogs --cleanup --retention-days 7
StandardOutput=append:/var/log/sftlogapi_cleanup.log
StandardError=append:/var/log/sftlogapi_cleanup.log
```

#### 2. 创建 Timer 文件

**每小时执行** (`/etc/systemd/system/sftlogapi-compress.timer`):
```ini
[Unit]
Description=每小时运行 sftlogapi 压缩任务

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
Unit=sftlogapi-compress.service

[Install]
WantedBy=timers.target
```

**每天 3:00 执行** (`/etc/systemd/system/sftlogapi-cleanup.timer`):
```ini
[Unit]
Description=每天运行 sftlogapi 清理任务

[Timer]
OnBootSec=10min
OnCalendar=*-*-* 03:00:00
Persistent=true
Unit=sftlogapi-cleanup.service

[Install]
WantedBy=timers.target
```

#### 3. 启用定时任务

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启用并启动定时器
sudo systemctl enable sftlogapi-compress.timer
sudo systemctl start sftlogapi-compress.timer

sudo systemctl enable sftlogapi-cleanup.timer
sudo systemctl start sftlogapi-cleanup.timer

# 查看定时器状态
sudo systemctl list-timers | grep sftlogapi
```

---

## 📜 索引生成脚本

### 脚本列表

| 脚本 | 用途 | 说明 |
|------|------|------|
| `compress_and_index.py` | 压缩日志 + 生成索引 | 主要脚本，支持多种模式 |
| `sync_index_to_sqlite.py` | 同步索引到 SQLite | 将 MessagePack 索引同步到数据库 |
| `build_index.py` | 构建索引 | 基础索引构建工具 |
| `migrate_all.py` | 批量迁移 | 批量处理历史数据 |

### 脚本位置

```
/root/sft/sftlogapi-v2/scripts/
├── compress_and_index.py          # 主要脚本 ⭐
├── sync_index_to_sqlite.py        # SQLite 同步 ⭐
├── build_index.py                 # 索引构建
├── migrate_all.py                 # 批量迁移
└── README_COMPRESS.md             # 脚本说明文档
```

---

### compress_and_index.py 详解

#### 功能

1. **压缩日志**: `.log` → `.log.gz`
2. **生成索引**:
   - REQ_SN 索引（仅 sft-aipg）
   - TraceID 索引（所有应用）
3. **同步到 SQLite**: 可选，将索引元数据同步到数据库

#### 使用方式

```bash
# 1. 自动模式（推荐用于定时任务）
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --auto \
  --sync-sqlite

# 2. 手动指定小时
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --service sft-aipg \
  --hour 2026040809

# 3. 处理所有服务
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --hour 2026040809 \
  --all-services

# 4. 清理旧索引
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --cleanup \
  --retention-days 7
```

#### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--log-dir` | 日志根目录 | 必需 |
| `--service` | 服务名称 | 所有服务 |
| `--hour` | 小时 (YYYYMMDDHH) | 1 小时前 |
| `--auto` | 自动模式 | false |
| `--all-services` | 处理所有服务 | false |
| `--sync-sqlite` | 同步到 SQLite | false |
| `--cleanup` | 清理模式 | false |
| `--retention-days` | 保留天数 | 7 |

---

### sync_index_to_sqlite.py 详解

#### 功能

1. **同步索引**: 将 MessagePack 索引同步到 SQLite 数据库
2. **清理旧数据**: 删除 N 天前的索引记录
3. **数据库优化**: VACUUM 数据库

#### 使用方式

```bash
# 1. 同步指定小时
python3 scripts/sync_index_to_sqlite.py \
  --log-dir /root/sft/testlogs \
  --hour 2026040809 \
  --db-path /root/sft-data/index/logs_trace.db

# 2. 清理旧数据
python3 scripts/sync_index_to_sqlite.py \
  --log-dir /root/sft/testlogs \
  --cleanup \
  --retention-days 7

# 3. 优化数据库
python3 scripts/sync_index_to_sqlite.py \
  --log-dir /root/sft/testlogs \
  --vacuum
```

---

## 📊 索引文件说明

### 文件结构

```
/root/sft/testlogs/
├── sft-aipg/
│   ├── sft-aipg_xxx_2026040809.log          # 原始日志
│   ├── sft-aipg_xxx_2026040809.log.gz       # 压缩后
│   ├── sft-aipg_2026040809.log.reqsn_index.msgpack  # REQ_SN 索引
│   └── sft-aipg_2026040809.log.trace_index.msgpack  # TraceID 索引
├── sft-merapi/
│   ├── sft-merapi_xxx_2026040809.log.gz
│   └── sft-merapi_2026040809.log.trace_index.msgpack
└── ...
```

### 索引类型

#### 1. REQ_SN 索引（仅 sft-aipg）

**文件名**: `{service}_{hour}.log.reqsn_index.msgpack`

**用途**: 快速查找 REQ_SN 对应的 TraceID

**结构**:
```python
{
  "meta": {
    "service": "sft-aipg",
    "hour": "2026040809",
    "total_req_sn": 10917
  },
  "req_sn_to_trace": {
    "3476885085720940544": "TCJMHVle1234567890abcdef"
  }
}
```

#### 2. TraceID 索引（所有应用）

**文件名**: `{service}_{hour}.log.trace_index.msgpack`

**用途**: 根据 TraceID 快速定位日志位置

**结构**:
```python
{
  "meta": {
    "service": "sft-aipg",
    "hour": "2026040809",
    "total_trace_ids": 11967
  },
  "trace_index": {
    "TCJMHVle": [
      {
        "file": "sft-aipg_xxx_2026040809.log.gz",
        "line": 1234,
        "timestamp": "2026-04-08 09:00:00.123"
      }
    ]
  }
}
```

---

## 🔧 故障排查

### 前端页面空白

```bash
# 1. 检查前端文件
ls -la /var/www/sftlogapi-v2/
# 应包含 index.html 和 static/

# 2. 检查 Nginx 配置
sudo nginx -t

# 3. 检查浏览器控制台
# F12 -> Console 查看错误

# 4. 检查 API 路径
grep "API_BASE" /var/www/sftlogapi-v2/index.html
# 应为：const API_BASE = '/sftlogapi-v2/api';
```

### Nginx 502 错误

```bash
# 1. 检查容器状态
docker ps | grep sftlogapi

# 2. 检查后端连接
curl http://127.0.0.1:5001/api/health

# 3. 检查 Nginx 日志
tail -f /usr/local/tengine/logs/error.log

# 4. 重启 Nginx
sudo nginx -s reload
```

### 定时任务未执行

```bash
# 1. 检查 cron 服务
systemctl status crond

# 2. 查看 cron 日志
tail -f /var/log/cron

# 3. 手动执行测试
python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto

# 4. 检查 crontab
crontab -l
```

### 索引文件过大

```bash
# 检查索引内容
python3 -c "
import msgpack
with open('xxx.trace_index.msgpack', 'rb') as f:
    data = msgpack.unpack(f)
print(f\"TraceID 数量：{data['meta']['total_trace_ids']}\")
print(f\"总日志块：{data['meta']['total_blocks']}\")
"

# 清理旧索引
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --cleanup \
  --retention-days 7
```

### 数据库同步失败

```bash
# 检查数据库文件
ls -lh /root/sft-data/index/logs_trace.db

# 手动同步
python3 scripts/sync_index_to_sqlite.py \
  --log-dir /root/sft/testlogs \
  --db-path /root/sft-data/index/logs_trace.db

# 优化数据库
docker exec sftlogapi-v2 \
  sqlite3 /data/index/logs_trace.db "VACUUM;"
```

---

## 📋 验证清单

### 前端部署

- [ ] 前端文件已复制到 `/var/www/sftlogapi-v2/`
- [ ] Nginx 配置已创建 `/usr/local/tengine/conf/conf.d/sftlogapi-v2.conf`
- [ ] Nginx 配置测试通过 `nginx -t`
- [ ] Nginx 已重载 `nginx -s reload`
- [ ] 前端页面可访问 `curl http://localhost:8091/sftlogapi-v2/`
- [ ] API 代理正常 `curl http://localhost:8091/sftlogapi-v2/api/health`

### 定时任务

- [ ] Crontab 已配置 `crontab -l`
- [ ] 索引生成任务已添加
- [ ] 索引清理任务已添加
- [ ] 手动执行测试成功
- [ ] 日志文件正常写入 `/var/log/sftlogapi_*.log`

### 索引文件

- [ ] 压缩日志文件生成 `*.log.gz`
- [ ] REQ_SN 索引生成 `*.reqsn_index.msgpack`
- [ ] TraceID 索引生成 `*.trace_index.msgpack`
- [ ] SQLite 数据库同步成功
- [ ] 索引文件大小正常

---

## 📚 相关文档

- 📦 [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md) - 完整部署指南
- 🔧 [PATH-CONFIG.md](PATH-CONFIG.md) - 路径配置清单
- 📜 [README_COMPRESS.md](scripts/README_COMPRESS.md) - 压缩脚本
- 📖 [README.md](README.md) - 项目说明

---

**最后更新**: 2026-04-12  
**版本**: 2.0.0  
**状态**: ✅ 完整
