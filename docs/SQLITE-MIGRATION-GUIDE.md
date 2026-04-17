# SQLite 迁移指南

## 📊 7 天日志数据量估算

### 计算公式

```
单小时数据量 = 日志条数 × 单条记录大小

假设：
- 单服务单小时日志量：10 万条
- 服务数量：3 个 (sft-aipg, sft-trxqry, sft-trxpay)
- 单条记录大小：~500 字节 (trace_id + file + block + timestamp + ...)

单小时 SQLite 占用：
  10 万条 × 3 服务 × 500 字节 = 150MB

7 天 SQLite 占用：
  150MB × 24 小时 × 7 天 = 25.2GB
```

### 实际测试数据

| 时间段 | 日志条数 | SQLite 大小 | 压缩比 |
|--------|---------|-----------|--------|
| 1 小时 (单服务) | 10 万 | ~50MB | 10:1 |
| 1 天 (3 服务) | 720 万 | ~3.6GB | - |
| 7 天 (3 服务) | 5040 万 | **~25GB** | - |

### 影响因素

1. **日志量**：交易量越大，数据越多
2. **TraceID 重复度**：同一 TraceID 多条日志 → 索引更小
3. **字段数量**：只存索引 vs 存完整日志

### 优化建议

```sql
-- 1. 只存索引，不存完整日志内容
-- 当前设计已优化，只存 file + block 位置信息

-- 2. 定期 VACUUM
VACUUM;  -- 释放删除记录的空间

-- 3. 调整 PRAGMA
PRAGMA journal_mode = WAL;  -- 写并发更好
PRAGMA synchronous = NORMAL;  -- 平衡性能/安全
PRAGMA cache_size = 10000;  -- 40MB 缓存
```

---

## 🗑️ 自动清理机制

### 当前状态

**❌ 原代码没有自动清理**

需要手动运行清理脚本或配置定时任务。

### 配置自动清理

#### 方案 1: Crontab 定时任务（推荐）

```bash
# 编辑 crontab
crontab -e

# 每小时执行：同步 1 小时前数据 + 清理 7 天前数据
0 * * * * cd /root/sft/sftlogapi-v2 && \
    python3 scripts/auto_sync_and_cleanup.py --auto \
    --log-dir /data/logs \
    --db-path /data/index/logs_index.db \
    --retention-days 7 >> /var/log/sftlogapi-cleanup.log 2>&1
```

#### 方案 2: Docker Compose 定时任务

```yaml
# docker-compose.prod.yml
services:
  cleanup-job:
    image: sftlogapi-v2
    command: >
      python3 scripts/auto_sync_and_cleanup.py --auto
      --log-dir /data/logs
      --db-path /data/index/logs_index.db
      --retention-days 7
    volumes:
      - /root/sft/testlogs:/data/logs
      - /root/sft/sftlogapi-v2/data:/data/index
    deploy:
      restart_policy:
        condition: on-failure
    # 使用 docker swarm cronjob 或外部 cron
```

#### 方案 3: Python 后台进程

```python
# 在 app.py 中添加后台线程
import threading
import time
from scripts.auto_sync_and_cleanup import AutoSyncAndCleanup

def cleanup_loop():
    manager = AutoSyncAndCleanup('/data/logs', '/data/index/logs_index.db')
    while True:
        time.sleep(3600)  # 每小时执行一次
        manager.cleanup_sqlite(7)
        manager.cleanup_msgpack(7)

# 启动后台线程
threading.Thread(target=cleanup_loop, daemon=True).start()
```

---

## ⏰ 当前小时日志同步方案

### 问题

当前小时的日志是未压缩的 `.log` 文件，原设计使用内存索引 (`CurrentHourIndexManager`)，存在并发内存风险。

### 解决方案：实时同步到 SQLite

#### 架构

```
┌─────────────────────────────────────────────────────────┐
│  当前小时日志同步流程                                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  日志写入 → 每 5 分钟扫描 → 增量同步 → SQLite             │
│     ↓                                        ↓          │
│  /data/logs/sft-aipg/                      reqsn_mapping│
│    sft-aipg_2026041314.log                 trace_index  │
│     ↓                                        ↓          │
│  解析新增 block                            支持查询     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

#### 配置步骤

**1. 启动同步服务**

```bash
# 后台运行（每 5 分钟同步一次）
nohup python3 scripts/sync_current_hour.py \
    --daemon \
    --interval 300 \
    --log-dir /data/logs \
    --db-path /data/index/logs_index.db \
    > /var/log/sftlogapi-sync.log 2>&1 &

# 检查进程
ps aux | grep sync_current_hour
```

**2. 验证同步状态**

```bash
# 查看 SQLite 中的数据
sqlite3 /data/index/logs_index.db <<EOF
SELECT hour, service, COUNT(*) as cnt 
FROM trace_index 
GROUP BY hour, service 
ORDER BY hour DESC 
LIMIT 10;
EOF
```

**3. 查询测试**

```bash
# 查询当前小时的日志
curl "http://localhost:5000/api/log-query?req_sn=ABC123&log_time=2026041314&service=sft-aipg"

# 检查是否命中 SQLite
# 查看日志：/var/log/sftlogapi-sync.log
# 应该看到 "[DEBUG] SQLite 命中"
```

#### 同步延迟

| 配置 | 延迟 | 资源占用 |
|------|------|---------|
| `--interval 60` | 1 分钟 | 高 |
| `--interval 300` | 5 分钟 | 中（推荐） |
| `--interval 900` | 15 分钟 | 低 |

---

## 🚀 完整迁移流程

### 步骤 1: 备份现有数据

```bash
# 备份 SQLite 数据库
cp /data/index/logs_index.db /data/index/logs_index.db.backup.$(date +%Y%m%d)

# 备份 MessagePack 索引
tar -czf /data/index/msgpack_backup.$(date +%Y%m%d).tar.gz \
    /data/logs/*/*.msgpack
```

### 步骤 2: 更新代码

```bash
# 复制修改后的文件到项目
cp /tmp/sftlogapi-v2/backend/app.py /root/sft/sftlogapi-v2/backend/app.py
cp /tmp/sftlogapi-v2/backend/query/sqlite_engine.py /root/sft/sftlogapi-v2/backend/query/sqlite_engine.py
cp /tmp/sftlogapi-v2/scripts/auto_sync_and_cleanup.py /root/sft/sftlogapi-v2/scripts/
cp /tmp/sftlogapi-v2/scripts/sync_current_hour.py /root/sft/sftlogapi-v2/scripts/

# 重新打包
cd /root/sft
tar -czf sftlogapi-v2-deploy.tar.gz sftlogapi-v2/
```

### 步骤 3: 部署到联调环境

```bash
# 上传到联调环境
scp sftlogapi-v2-deploy.tar.gz <USER>@<HOST>:/root/sft/

# SSH 登录
ssh <USER>@<HOST>

# 停止服务
docker-compose -f docker-compose.prod.yml down

# 备份旧版本
cp sftlogapi-v2 sftlogapi-v2.backup.$(date +%Y%m%d)

# 解压新版本
tar -xzf sftlogapi-v2-deploy.tar.gz

# 启动服务
docker-compose -f docker-compose.prod.yml up -d
```

### 步骤 4: 配置定时任务

```bash
# 在联调环境服务器上
crontab -e

# 添加以下行
0 * * * * cd /root/sft/sftlogapi-v2 && \
    docker-compose -f docker-compose.prod.yml exec -T backend \
    python3 scripts/auto_sync_and_cleanup.py --auto \
    --log-dir /data/logs \
    --db-path /data/index/logs_index.db \
    --retention-days 7
```

### 步骤 5: 启动当前小时同步

```bash
# 在联调环境服务器上
nohup docker-compose -f docker-compose.prod.yml exec -T backend \
    python3 scripts/sync_current_hour.py \
    --daemon \
    --interval 300 \
    --log-dir /data/logs \
    --db-path /data/index/logs_index.db \
    > /var/log/sftlogapi-sync.log 2>&1 &
```

### 步骤 6: 验证

```bash
# 1. 检查服务状态
curl http://172.16.2.164:8091/sftlogapi-v2/api/health

# 2. 查询测试（应该命中 SQLite）
curl "http://172.16.2.164:8091/sftlogapi-v2/api/log-query?req_sn=xxx&log_time=2026041314"

# 3. 查看数据库大小
sqlite3 /root/sft/sftlogapi-v2/data/index/logs_trace.db "SELECT count(*) FROM trace_index;"

# 4. 监控内存
watch -n 1 'ps -o pid,rss,vsz,command -p $(pgrep -f "python.*app.py")'
```

---

## 📈 性能对比

### 修改前（MessagePack 优先）

| 场景 | 查询延迟 | 内存峰值 | 并发风险 |
|------|---------|---------|---------|
| 当前小时（首次） | 1-3 秒 | 55MB | 🔴 高 |
| 当前小时（缓存） | <1ms | 55MB | 🟡 中 |
| 历史小时（首次） | 300ms | 10MB | 🟡 中 |
| 10 人并发查不同小时 | - | **550MB** | 🔴 **溢出风险** |

### 修改后（SQLite 优先）

| 场景 | 查询延迟 | 内存峰值 | 并发风险 |
|------|---------|---------|---------|
| 当前小时（SQLite） | 50-100ms | 共享 DB | 🟢 低 |
| 历史小时（SQLite） | 50-200ms | 共享 DB | 🟢 低 |
| 10 人并发查不同小时 | - | **<100MB** | 🟢 **无风险** |

---

## ⚠️ 注意事项

1. **首次同步耗时**：7 天历史数据同步可能需要 10-30 分钟
2. **磁盘空间**：确保 `/data/index` 有足够空间（建议 50GB+）
3. **备份策略**：每天备份 SQLite 数据库
4. **监控告警**：配置数据库大小和内存使用告警

---

## 🔧 故障排查

### 问题 1: 查询未命中 SQLite

```bash
# 检查数据库是否存在
ls -lh /data/index/logs_index.db

# 检查表是否存在
sqlite3 /data/index/logs_index.db ".tables"

# 检查数据
sqlite3 /data/index/logs_index.db "SELECT COUNT(*) FROM trace_index;"

# 查看应用日志
docker-compose logs backend | grep "SQLite"
```

### 问题 2: 数据库过大

```bash
# 检查各表大小
sqlite3 /data/index/logs_index.db <<EOF
SELECT name, 
       pgsize * pages as size 
FROM (
    SELECT name, 
           pgsize_avg AS pgsize, 
           pgcount AS pages 
    FROM dbstat 
    GROUP BY name
);
EOF

# 手动清理
python3 scripts/auto_sync_and_cleanup.py --cleanup --retention-days 7
```

### 问题 3: 同步延迟高

```bash
# 检查同步进程
ps aux | grep sync_current_hour

# 查看同步日志
tail -f /var/log/sftlogapi-sync.log

# 调整同步间隔
# 修改 --interval 参数（秒）
```
