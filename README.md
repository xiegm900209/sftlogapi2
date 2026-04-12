# sftlogapi v2 - 高性能日志查询系统

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/xiegm900209/sftlogapi2)
[![Performance](https://img.shields.io/badge/query-≤3ms-brightgreen.svg)](https://github.com/xiegm900209/sftlogapi2)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/xiegm900209/sftlogapi2)

> 查询耗时从 **23 秒** 降至 **≤3 毫秒**，性能提升 **7,600 倍**

## 📊 项目简介

sftlogapi v2 是一个企业级高性能日志查询系统，专为分布式交易链路追踪设计。通过 **SQLite 持久化索引 + 流式日志读取**技术，实现毫秒级日志查询和完整的交易链路追踪。

### 核心优势

- ⚡ **极速查询** - 单次查询 ≤3ms（原 23 秒）
- 🔗 **链路追踪** - 完整展示交易在所有应用间的流转
- 💾 **持久化** - SQLite 存储，容器重启数据不丢失
- 📦 **低内存** - 内存占用 <50MB
- 🗜️ **高压缩** - 小时级压缩，节省 85% 存储空间

### 技术指标

| 指标 | 数值 |
|------|------|
| 查询耗时 | ≤3ms |
| 索引记录 | 500 万+ |
| 支持服务 | 30+ |
| 日志保留 | 7 天 |
| 内存占用 | <50MB |
| 数据库大小 | ~1.4GB/3 小时 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  前端层 (Vue.js + Nginx:8091)                            │
│  - 响应式单页应用                                        │
│  - Nginx 反向代理                                        │
│  - History API 路由                                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  API 层 (Flask:5001)                                      │
│  - RESTful API                                           │
│  - LRU 缓存                                               │
│  - 流式日志读取 (<1MB)                                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  索引层 (SQLite)                                         │
│  - 持久化存储 (logs_trace.db)                            │
│  - 按小时分表                                            │
│  - REQ_SN ↔ TraceID 双向索引                              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  存储层 (日志文件)                                        │
│  - 小时级压缩 (.log.gz)                                  │
│  - MessagePack 索引                                       │
│  - 7 天滚动清理                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 功能特性

### 1. 单日志查询 🔍
- 通过 REQ_SN（交易序列号）快速查询日志
- 支持时间范围筛选（格式：YYYYMMDDHH）
- 毫秒级响应（≤3ms）
- 适用于快速定位某笔交易的日志记录

### 2. 交易链路追踪 🔗
- 完整展示交易在所有应用间的流转过程
- 支持 12 种交易类型的链路追踪
- 可视化的应用流程时间轴
- 按时间顺序展示所有日志

### 3. 日志路径配置 📁
- 管理各服务的日志存储路径
- 表格化展示，支持增删改查
- 支持导入导出功能

### 4. 交易类型配置 ⚙️
- 配置不同交易类型对应的应用链路
- 可视化展示应用流转顺序
- 支持自定义追踪流程

---

## 📚 文档导航

| 文档 | 说明 | 路径 |
|------|------|------|
| **📦 部署指南** | 完整部署步骤、环境配置、迁移指南 | [docs/DEPLOYMENT-GUIDE.md](docs/DEPLOYMENT-GUIDE.md) |
| **🔧 路径配置** | 所有路径配置清单、环境变量说明 | [docs/PATH-CONFIG.md](docs/PATH-CONFIG.md) |
| **📋 部署完成** | 当前部署信息、访问入口、运维命令 | [DEPLOYMENT.md](DEPLOYMENT.md) |
| **📖 项目说明** | 本文档 | [README.md](README.md) |

---

## 🚀 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 1.29+
- Python 3.9+
- 磁盘空间：≥200GB（7 天日志）
- 内存：≥2GB

### 方式一：使用部署脚本（推荐）

```bash
# 1. 克隆项目
git clone git@github.com:xiegm900209/sftlogapi2.git
cd sftlogapi2

# 2. 配置路径
cp config.env.example config.env
vim config.env  # 修改为实际路径

# 3. 一键部署
chmod +x deploy.sh
./deploy.sh
```

### 方式二：使用 Docker Compose

```bash
# 1. 克隆项目
git clone git@github.com:xiegm900209/sftlogapi2.git
cd sftlogapi2

# 2. 配置路径
cp config.env.example config.env
vim config.env  # 修改为实际路径

# 3. 启动容器
docker-compose --env-file config.env -f docker-compose.env.yml up -d
```

### 方式三：手动配置

```bash
# 1. 创建配置文件
mkdir -p /root/sft-data/index
cp config.env.example config.env
vim config.env  # 修改路径

# 2. 构建镜像
docker build -t sftlogapi:v2 .

# 3. 启动容器（使用实际路径）
docker run -d \
  --name sftlogapi-v2 \
  -p 5001:5000 \
  -v /your/path/to/logs:/data/logs:ro \
  -v /your/path/to/db/logs_trace.db:/data/index/logs_trace.db \
  -v $(pwd)/config:/app/config:ro \
  -e DB_PATH=/data/index/logs_trace.db \
  -e LOG_BASE_DIR=/data/logs \
  -e API_KEY=your-api-key \
  sftlogapi:v2
```

### 5. 配置 Nginx

```bash
# 复制 Nginx 配置文件
cp conf/nginx.conf /usr/local/tengine/conf/conf.d/sftlogapi.conf

# 测试配置
/usr/local/tengine/sbin/nginx -t

# 重载 Nginx
/usr/local/tengine/sbin/nginx -s reload
```

### 6. 访问系统

打开浏览器访问：
```
http://<your-server-ip>:8091/sftlogapi/
```

---

## 📁 项目结构

```
sftlogapi-v2/
├── backend/                    # 后端代码
│   ├── app.py                  # Flask 主应用
│   ├── indexer/
│   │   └── sqlite_sync.py      # SQLite 同步器
│   ├── query/
│   │   ├── index_loader.py     # 索引加载器
│   │   ├── log_reader.py       # 日志读取器
│   │   ├── current_hour_index.py # 当前小时索引
│   │   └── cache.py            # LRU 缓存
│   └── models/
│       ├── log_parser.py       # 日志解析
│       └── schema.sql          # 数据库结构
├── frontend/
│   └── index.html              # 前端页面
├── scripts/
│   ├── compress_and_index.py   # 压缩 + 索引生成
│   ├── sync_index_to_sqlite.py # 同步到 SQLite
│   └── test_*.py               # 测试脚本
├── config/
│   ├── transaction_types.json  # 交易类型配置
│   └── log_dirs.json           # 日志路径配置
├── conf/
│   └── nginx.conf              # Nginx 配置
├── docker-compose.prod.yml     # 生产环境配置
├── Dockerfile                  # 容器镜像
├── requirements.txt            # Python 依赖
└── README.md                   # 项目文档
```

---

## ⏰ 定时任务

### 每小时压缩 + 索引生成

```bash
# 编辑 crontab
crontab -e

# 添加任务（每小时执行一次）
0 * * * * cd /root/sft/sftlogapi-v2 && \
    python3 scripts/compress_and_index.py \
    --log-dir /root/sft/testlogs \
    --hour $(date -d '1 hour ago' +\%Y\%m\%d\%H) \
    --all-services \
    --sync-sqlite \
    >> /var/log/sftlogapi_compress.log 2>&1
```

### 每天清理 7 天前数据

```bash
# 每天 3:00 清理
0 3 * * * cd /root/sft/sftlogapi-v2 && \
    python3 scripts/sync_index_to_sqlite.py \
    --cleanup --retention-days 7 \
    >> /var/log/sftlogapi_cleanup.log 2>&1
```

---

## 📊 API 接口

### 健康检查
```bash
curl http://localhost:5001/api/health
```

### 单日志查询
```bash
curl "http://localhost:5001/api/log-query?req_sn=xxx&log_time=2026040809&service=sft-aipg"
```

### 交易链路追踪
```bash
curl "http://localhost:5001/api/transaction-trace?req_sn=xxx&log_time=2026040809&transaction_type=310011"
```

### 获取服务列表
```bash
curl http://localhost:5001/api/services
```

### 配置管理
```bash
# 获取日志路径配置
curl http://localhost:5001/api/config/log-dirs

# 更新日志路径配置
curl -X POST http://localhost:5001/api/config/log-dirs \
  -H "Content-Type: application/json" \
  -d '{"sft-aipg": "/path/to/logs"}'
```

---

## 🔧 运维命令

### 容器管理

```bash
# 查看状态
docker ps | grep sftlogapi

# 查看日志
docker logs -f sftlogapi-v2

# 重启容器
docker restart sftlogapi-v2

# 进入容器
docker exec -it sftlogapi-v2 bash
```

### 数据库管理

```bash
# 查看数据库大小
ls -lh /root/sft-data/index/logs_trace.db

# 备份数据库
cp /root/sft-data/index/logs_trace.db \
   /root/sft-data/backup/logs_trace_$(date +%Y%m%d).db

# 优化数据库
docker exec sftlogapi-v2 \
    sqlite3 /data/index/logs_trace.db "VACUUM;"
```

### 日志管理

```bash
# 查看压缩日志
ls -lh /root/sft/testlogs/sft-aipg/

# 手动生成索引
python3 scripts/compress_and_index.py \
    --log-dir /root/sft/testlogs \
    --hour 2026040812 \
    --service sft-aipg \
    --sync-sqlite
```

---

## 📈 性能优化建议

### 1. 磁盘 IO
- 使用 SSD 存储数据库和日志
- 数据库和日志分盘存放
- 定期 VACUUM 优化数据库

### 2. 内存优化
- LRU 缓存热点数据
- 流式读取日志（<1MB）
- 当前小时索引自动过期

### 3. 查询优化
- SQLite 索引加速（≤1ms）
- 按小时分表查询
- REQ_SN → TraceID 双向索引

---

## 🆘 故障排查

### 问题 1: 容器无法启动

```bash
# 查看容器日志
docker logs sftlogapi-v2

# 检查配置文件
docker exec sftlogapi-v2 ls -la /app/config/

# 检查数据库
docker exec sftlogapi-v2 ls -lh /data/index/
```

### 问题 2: 查询超时

```bash
# 检查数据库大小
ls -lh /root/sft-data/index/logs_trace.db

# 检查缓存状态
curl http://localhost:5001/api/cache/stats

# 重启容器
docker restart sftlogapi-v2
```

### 问题 3: Nginx 502 错误

```bash
# 检查容器是否运行
docker ps | grep sftlogapi

# 检查 Nginx 配置
/usr/local/tengine/sbin/nginx -t

# 重启 Nginx
/usr/local/tengine/sbin/nginx -s reload
```

---

## 📝 配置示例

### 交易类型配置 (config/transaction_types.json)

```json
{
  "310011": {
    "name": "协议支付",
    "apps": [
      "sft-aipg",
      "sft-merapi",
      "sft-trxcharge",
      "sft-chnlagent",
      "sft-ucpagent",
      "sft-rtresult-http",
      "sft-rtresult-listener"
    ]
  }
}
```

### 日志路径配置 (config/log_dirs.json)

```json
{
  "sft-aipg": "/root/sft/testlogs/sft-aipg",
  "sft-merapi": "/root/sft/testlogs/sft-merapi",
  "sft-trxpay": "/root/sft/testlogs/sft-trxpay"
}
```

---

## 🎯 最佳实践

1. **定期备份** - 每天备份 SQLite 数据库
2. **监控磁盘** - 确保磁盘使用率 <80%
3. **定期清理** - 每天清理 7 天前索引
4. **性能监控** - 定期检查查询耗时
5. **日志轮转** - 小时级压缩，保留 7 天

---

## 📞 技术支持

- **项目地址**: https://github.com/xiegm900209/sftlogapi2
- **作者**: xiegm900209
- **版本**: 2.0.0
- **许可证**: MIT

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**最后更新**: 2026-04-12  
**性能**: 查询耗时 ≤3ms (提升 7,600 倍) 🚀
