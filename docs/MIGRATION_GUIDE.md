# sftlogapi v2 迁移指南

> 从硬编码路径迁移到配置化部署

## 📋 为什么要迁移？

**旧版本问题**:
- ❌ 路径硬编码在代码中
- ❌ 难以迁移到其他环境
- ❌ 不同环境需要修改代码
- ❌ 容器和宿主机路径混淆

**新版本优势**:
- ✅ 所有路径配置化
- ✅ 支持环境变量
- ✅ 一键部署脚本
- ✅ 轻松迁移到任何环境

---

## 🚀 迁移步骤

### 步骤 1: 备份现有数据

```bash
# 备份数据库
cp /root/sft-data/index/logs_trace.db \
   /root/sft-data/backup/logs_trace_$(date +%Y%m%d).db

# 备份配置文件
cp -r /root/sft/sftlogapi-v2/config \
      /root/sft-data/backup/config_$(date +%Y%m%d)
```

### 步骤 2: 更新代码

```bash
cd /root/sft/sftlogapi-v2
git pull origin main
```

### 步骤 3: 创建配置文件

```bash
# 复制配置模板
cp config.env.example config.env

# 编辑配置文件
vim config.env
```

### 步骤 4: 修改配置项

**必须修改的配置**:

```bash
# 日志根目录（根据你的实际路径修改）
LOG_BASE_DIR=/root/sft/testlogs

# 数据库路径（根据你的实际路径修改）
DB_PATH=/root/sft-data/index/logs_trace.db

# API Key（建议修改为自定义密钥）
API_KEY=your-custom-api-key-2026
```

**可选修改的配置**:

```bash
# 容器名称
CONTAINER_NAME=sftlogapi-v2

# 镜像名称
DOCKER_IMAGE=sftlogapi:v2

# 端口映射
PORT=5000

# 是否启用认证
ENABLE_AUTH=false
```

### 步骤 5: 使用脚本部署（推荐）

```bash
# 赋予执行权限
chmod +x deploy.sh

# 运行部署脚本
./deploy.sh
```

### 步骤 6: 验证部署

```bash
# 检查容器状态
docker ps | grep sftlogapi

# 查看日志
docker logs sftlogapi-v2

# 测试 API
curl http://localhost:5001/api/health
```

---

## 📁 路径说明

### 宿主机路径（需要配置）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_BASE_DIR` | `/root/sft/testlogs` | 日志文件根目录 |
| `DB_PATH` | `/root/sft-data/index/logs_trace.db` | SQLite 数据库路径 |
| `SCRIPTS_DIR` | `/root/sft/sftlogapi-v2/scripts` | 脚本目录 |

### 容器内路径（不要修改）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CONTAINER_LOG_DIR` | `/data/logs` | 容器内日志目录 |
| `CONTAINER_DB_DIR` | `/data/index` | 容器内数据库目录 |

---

## 🔧 常见场景

### 场景 1: 迁移到新服务器

```bash
# 1. 在新服务器上克隆项目
git clone git@github.com:xiegm900209/sftlogapi2.git
cd sftlogapi2

# 2. 配置新路径
cp config.env.example config.env
vim config.env

# 修改为：
LOG_BASE_DIR=/data/logs  # 新服务器的日志路径
DB_PATH=/data/index/logs_trace.db  # 新服务器的数据库路径

# 3. 部署
./deploy.sh

# 4. 导入旧数据（可选）
scp old-server:/root/sft-data/index/logs_trace.db \
    /data/index/logs_trace.db
```

### 场景 2: 多环境部署

**开发环境** (`config.dev.env`):
```bash
LOG_BASE_DIR=/home/dev/logs
DB_PATH=/home/dev/data/logs_trace.db
API_KEY=dev-key-2026
DEBUG=true
```

**生产环境** (`config.prod.env`):
```bash
LOG_BASE_DIR=/data/prod/logs
DB_PATH=/data/prod/index/logs_trace.db
API_KEY=prod-secure-key-2026
DEBUG=false
```

**部署命令**:
```bash
# 开发环境
docker-compose --env-file config.dev.env -f docker-compose.env.yml up -d

# 生产环境
docker-compose --env-file config.prod.env -f docker-compose.env.yml up -d
```

### 场景 3: Docker Swarm/K8s 部署

**环境变量**:
```yaml
env:
  - name: LOG_BASE_DIR
    value: /data/logs
  - name: DB_PATH
    value: /data/index/logs_trace.db
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: sftlogapi-secret
        key: api-key
```

**持久化存储**:
```yaml
volumes:
  - name: logs-data
    hostPath:
      path: /data/logs
  - name: db-data
    hostPath:
      path: /data/index
```

---

## ⚠️ 注意事项

### 1. 路径权限

确保 Docker 有权限访问配置的路径：

```bash
# 日志目录
chmod 755 /root/sft/testlogs

# 数据库目录
chmod 755 /root/sft-data/index
chown 1000:1000 /root/sft-data/index  # 如果需要
```

### 2. 路径挂载

容器内路径是固定的，不要修改：
- `/data/logs` - 日志目录
- `/data/index` - 数据库目录

修改的是**宿主机路径**到容器内路径的映射。

### 3. 数据库迁移

如果修改了数据库路径，需要迁移旧数据：

```bash
# 旧路径
OLD_DB=/root/sft/sftlogapi-v2/data/index/logs_trace.db

# 新路径
NEW_DB=/root/sft-data/index/logs_trace.db

# 迁移
mkdir -p $(dirname $NEW_DB)
cp $OLD_DB $NEW_DB
```

### 4. 配置文件安全

```bash
# 保护配置文件
chmod 600 config.env

# 不要将 config.env 提交到 Git
echo "config.env" >> .gitignore
```

---

## 🆘 故障排查

### 问题 1: 容器启动失败

```bash
# 查看错误日志
docker logs sftlogapi-v2

# 检查路径是否存在
ls -la $LOG_BASE_DIR
ls -la $(dirname $DB_PATH)

# 检查配置文件
cat config.env
```

### 问题 2: 数据库无法访问

```bash
# 检查数据库文件
ls -lh $DB_PATH

# 检查权限
chmod 644 $DB_PATH

# 重启容器
docker restart sftlogapi-v2
```

### 问题 3: 日志目录找不到

```bash
# 检查路径配置
grep LOG_BASE_DIR config.env

# 验证路径
ls -la $LOG_BASE_DIR

# 如果是相对路径，改为绝对路径
```

---

## 📞 技术支持

- **GitHub Issues**: https://github.com/xiegm900209/sftlogapi2/issues
- **文档**: https://github.com/xiegm900209/sftlogapi2/tree/main/docs
- **示例配置**: `config.env.example`

---

**版本**: 2.0.0  
**更新时间**: 2026-04-12  
**作者**: xiegm900209
