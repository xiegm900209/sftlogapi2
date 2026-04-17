# 日志压缩 + 索引生成工具

## 📦 功能

1. **压缩日志**: 将 `.log` 文件压缩为 `.log.gz`
2. **生成索引**: 
   - `REQ_SN 索引` (仅 sft-aipg): `{service}_{hour}.log.reqsn_index.msgpack`
   - `TraceID 索引` (所有应用): `{service}_{hour}.log.trace_index.msgpack`
3. **清理索引**: 删除 2 天前的索引文件（保留压缩日志）

## 🚀 使用方法

### 1. 自动模式（推荐用于定时任务）

```bash
# 压缩并索引 1 小时前的小时
python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto
```

### 2. 手动指定小时

```bash
# 处理单个服务
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --service sft-aipg \
  --hour 2026040809

# 处理所有服务
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --hour 2026040809
```

### 3. 清理旧索引

```bash
# 删除 2 天前的索引文件
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --cleanup \
  --retention-days 2
```

### 4. 单个文件模式

```bash
python3 scripts/compress_and_index.py \
  --log-dir /root/sft/testlogs \
  --service sft-aipg \
  --hour 2026040809 \
  --file /root/sft/testlogs/sft-aipg/xxx.log
```

---

## ⏰ 定时任务配置

### Crontab 配置

```bash
# 编辑 crontab
crontab -e

# 添加以下任务（每小时执行一次，处理 1 小时前的小时）
0 * * * * cd /root/sft/sftlogapi-v2 && /usr/bin/python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto >> /var/log/sftlogapi_compress.log 2>&1

# 每天 3:00 清理 2 天前的索引
0 3 * * * cd /root/sft/sftlogapi-v2 && /usr/bin/python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --cleanup --retention-days 2 >> /var/log/sftlogapi_cleanup.log 2>&1
```

### Systemd Timer 配置（可选）

**/etc/systemd/system/sftlogapi-compress.service**:
```ini
[Unit]
Description=sftlogapi 日志压缩和索引生成
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/root/sft/sftlogapi-v2
ExecStart=/usr/bin/python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto
```

**/etc/systemd/system/sftlogapi-compress.timer**:
```ini
[Unit]
Description=每小时运行 sftlogapi 压缩任务

[Timer]
OnUnitActiveSec=1h
Unit=sftlogapi-compress.service

[Install]
WantedBy=timers.target
```

**启用定时任务**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sftlogapi-compress.timer
sudo systemctl start sftlogapi-compress.timer
```

---

## 📁 索引文件说明

### REQ_SN 索引（仅 sft-aipg）

**文件名**: `sft-aipg_{hour}.log.reqsn_index.msgpack`

**结构**:
```python
{
  "meta": {
    "service": "sft-aipg",
    "hour": "2026040809",
    "created_at": "2026-04-08T10:00:00",
    "total_req_sn": 10917
  },
  "req_sn_to_trace": {
    "3476885085720940544": "TCJMHVle1234567890abcdef",
    # ...
  }
}
```

**用途**: 快速查找 REQ_SN 对应的 TraceID

---

### TraceID 索引（所有应用）

**文件名**: `{service}_{hour}.log.trace_index.msgpack`

**结构**:
```python
{
  "meta": {
    "service": "sft-aipg",
    "hour": "2026040809",
    "created_at": "2026-04-08T10:00:00",
    "total_trace_ids": 11967,
    "total_blocks": 332626
  },
  "trace_index": {
    "TCJMHVle": [
      {
        "file": "sft-aipg-sft-aipg-59c947b9c9-cj6fm_zb_2026040809.log.gz",
        "line": 1234,
        "block": 1233,
        "timestamp": "2026-04-08 09:00:00.123",
        "level": "INFO",
        "thread": "http-apr-8195-exec-2284",
        "length": 751
      },
      # ...
    ]
  }
}
```

**用途**: 根据 TraceID 快速定位日志在压缩文件中的位置

---

## 📊 性能指标

### 索引文件大小（示例：sft-aipg 单小时）

| 指标 | 数值 |
|------|------|
| 原始日志 | 50MB (.log) |
| 压缩后 | 8.4MB (.log.gz) |
| REQ_SN 索引 | 387KB |
| TraceID 索引 | 53MB |
| 总索引 | 53.4MB |

### 处理速度

| 操作 | 耗时 |
|------|------|
| 压缩 50MB 日志 | ~3s |
| 构建索引 (33 万条) | ~15s |
| 加载索引 (查询时) | ~600ms |

---

## 🔧 环境迁移

### 联调环境

```bash
LOG_DIR=/data/testlogs  # 根据实际路径修改
```

### 生产环境

```bash
LOG_DIR=/data/logs  # 根据实际路径修改
```

**修改方法**: 所有命令中的 `--log-dir` 参数替换为对应路径

---

## 📝 日志文件命名规范

```
{pod-name}_{hostname}_{hour}.log
示例：sft-aipg-sft-aipg-59c947b9c9-cj6fm_zb_2026040809.log

压缩后:
{pod-name}_{hostname}_{hour}.log.gz
示例：sft-aipg-sft-aipg-59c947b9c9-cj6fm_zb_2026040809.log.gz

索引文件:
{service}_{hour}.log.reqsn_index.msgpack  (仅 sft-aipg)
{service}_{hour}.log.trace_index.msgpack  (所有应用)
```

---

## ⚠️ 注意事项

1. **当前小时日志不压缩**: 保留 `.log` 格式，查询时临时生成索引
2. **索引与压缩日志同目录**: 便于管理和清理
3. **2 天索引清理**: 只删索引，保留原始压缩日志
4. **MessagePack 格式**: 需要安装 `msgpack` 库
5. **流式处理**: 避免内存溢出，支持大文件

---

## 🆘 故障排查

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
```

### 定时任务未执行

```bash
# 查看 cron 日志
tail -f /var/log/cron

# 手动执行测试
python3 scripts/compress_and_index.py --log-dir /root/sft/testlogs --auto
```

### 内存溢出

- 检查是否使用了流式处理
- 减少并发处理的服务数量
- 增加系统内存或 swap

---

**版本**: 2.0.0  
**作者**: xiegm900209  
**更新时间**: 2026-04-11
