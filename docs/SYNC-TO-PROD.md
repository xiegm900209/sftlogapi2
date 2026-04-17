# 🔧 联调环境手动同步指南

**安全修复代码同步到联调环境**

---

## 📋 同步前检查

### 1. 确认代码已提交

```bash
cd /root/sft/sftlogapi-v2
git log --oneline -5
```

---

## 🚀 网络架构

```
本地 → 跳板机 → 中间机 → 后端主机
       ↓              ↓
     (可选)        前端主机
```

### 需要配置的主机信息

| 主机 | 用途 | 配置位置 |
|------|------|----------|
| 跳板机 | 入口主机 | `scripts/sync-to-prod.sh` |
| 中间机 | 中转主机 | `scripts/sync-to-prod.sh` |
| 后端主机 | 应用服务器 | `scripts/sync-to-prod.sh` |
| 前端主机 | Web 服务器 | `scripts/sync-to-prod.sh` |

---

## 📋 同步方式

### 方式一：使用同步脚本

```bash
cd /root/sft/sftlogapi-v2

# 1. 编辑脚本，配置主机信息
vim scripts/sync-to-prod.sh

# 2. 执行同步
./scripts/sync-to-prod.sh
```

### 方式二：手动同步

#### 步骤 1: 打包代码

```bash
cd /root/sft/sftlogapi-v2

# 打包后端代码
tar -czf /tmp/sftlogapi-deploy.tar.gz \
    backend/ \
    scripts/ \
    config.env.example \
    .env.example \
    docker-compose.prod.yml \
    Dockerfile \
    requirements.txt
```

#### 步骤 2: 传输到目标主机

```bash
# 使用 scp 或 rsync 传输
scp /tmp/sftlogapi-deploy.tar.gz user@target-host:/tmp/
```

#### 步骤 3: 在目标主机部署

```bash
# 登录到目标主机
ssh user@target-host

# 进入项目目录
cd /path/to/sftlogapi-v2

# 备份原代码
cp -r backend backend.bak.$(date +%Y%m%d_%H%M%S)

# 解压新代码
tar -xzf /tmp/sftlogapi-deploy.tar.gz

# 配置 API Key
cp config.env.example config.env
vim config.env  # 编辑配置

# 重启容器
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker logs -f sftlogapi-v2 --tail 50
```

---

## 🔑 API Key 配置

### 生成 API Key

```bash
openssl rand -hex 32
```

### 配置到环境

```bash
# 编辑 .env 文件
vim .env

# 设置以下变量：
API_KEY=<生成的密钥>
ENABLE_AUTH=true
```

---

## ✅ 验证清单

- [ ] 容器状态正常：`docker ps | grep sftlogapi-v2`
- [ ] 健康检查通过：`curl http://localhost:5001/api/health`
- [ ] 日志查询正常
- [ ] API Key 认证正常（如启用）

---

## 🔧 故障排查

### 容器启动失败

```bash
# 查看容器日志
docker logs sftlogapi-v2 --tail 100
```

### 端口被占用

```bash
# 查看占用端口的进程
netstat -tlnp | grep 5001
```

---

**最后更新**: 2026-04-17  
**文档版本**: 1.1 (已清理敏感信息)
