# 🔧 联调环境手动同步指南

**安全修复代码同步到联调环境**

---

## 📋 同步前检查

### 1. 确认代码已提交

```bash
cd /root/sft/sftlogapi-v2
git log --oneline -5
```

✅ 已提交 commit: `d4c6037 feat: 新增联调环境同步脚本`

---

## 🚀 同步方式

### 方式一：使用同步脚本（推荐）

```bash
cd /root/sft/sftlogapi-v2
./scripts/sync-to-prod.sh
```

选择 `1) 自动同步` 或 `2) 手动同步`

---

### 方式二：手动同步（详细步骤）

#### 步骤 1: 打包代码

```bash
cd /root/sft/sftlogapi-v2

# 打包后端代码
tar -czf /tmp/sftlogapi-security-fix.tar.gz \
    backend/ \
    scripts/generate_api_key.sh \
    scripts/test_*.py \
    scripts/verify_api_key_fix.py \
    config.env.example \
    .env.example \
    docker-compose.prod.yml \
    Dockerfile \
    requirements.txt
```

#### 步骤 2: 通过跳板机传输

```bash
# 2.1 连接到跳板机
ssh root@192.168.13.104
# 密码：Lt_Sc360

# 2.2 上传文件到跳板机（本地执行）
scp /tmp/sftlogapi-security-fix.tar.gz root@192.168.13.104:/tmp/

# 2.3 从跳板机连接到中间机
ssh sftuser@192.168.109.75
# 密码：sftuser

# 2.4 从中间机下载文件
exit  # 返回本地
scp root@192.168.13.104:/tmp/sftlogapi-security-fix.tar.gz /tmp/

# 2.5 连接到后端主机
ssh sftuser@192.168.109.77
# 密码：sftuser

# 2.6 上传文件到后端主机（从中间机执行）
scp /tmp/sftlogapi-security-fix.tar.gz sftuser@192.168.109.77:/tmp/
```

#### 步骤 3: 在后端主机部署

```bash
# 3.1 登录到后端主机
ssh sftuser@192.168.109.77
# 密码：sftuser

# 3.2 进入项目目录
cd /app/sftlogapi-root/sftlogapi-v2

# 3.3 备份原代码
cp -r backend backend.bak.$(date +%Y%m%d_%H%M%S)
cp -r scripts scripts.bak.$(date +%Y%m%d_%H%M%S)

# 3.4 解压新代码
tar -xzf /tmp/sftlogapi-security-fix.tar.gz

# 3.5 配置 API Key（重要！）
# 如果启用认证，必须设置 API_KEY
cp config.env.example config.env
vim config.env  # 编辑配置

# 3.6 重启容器
cd /app/sftlogapi-root
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 3.7 查看日志
docker logs -f sftlogapi-v2 --tail 50
```

#### 步骤 4: 验证部署

```bash
# 4.1 健康检查
curl http://localhost:5001/api/health

# 预期输出:
# {"success":true,"status":"healthy","timestamp":"...","version":"2.0.0"}

# 4.2 测试查询 API
curl "http://localhost:5001/api/log-query?log_time=2026040809&req_sn=TEST123"

# 4.3 检查安全修复
# 测试 SQL 注入防护
curl "http://localhost:5001/api/log-query?log_time=2026040809;DROP+TABLE+logs_2026040809--&req_sn=TEST"
# 应返回：日志时间格式错误

# 测试路径遍历防护
curl "http://localhost:5001/api/log-query?log_time=2026040809&service=../etc/passwd&req_sn=TEST"
# 应返回：服务名称格式错误
```

---

### 方式三：使用 rsync 同步（如果网络允许）

```bash
# 从本地直接同步（需要配置 SSH 密钥或 sshpass）
rsync -avz --exclude='.git' \
    --exclude='data/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    backend/ \
    scripts/ \
    config.env.example \
    .env.example \
    docker-compose.prod.yml \
    sftuser@192.168.109.77:/app/sftlogapi-root/sftlogapi-v2/
```

---

## 🔑 API Key 配置（重要）

如果联调环境启用 API 认证，必须配置 API_KEY：

### 生成 API Key

```bash
# 在联调环境执行
openssl rand -hex 32
```

### 配置到容器

```bash
# 方法 1: 编辑 .env 文件
cd /app/sftlogapi-root/sftlogapi-v2
cp .env.example .env
vim .env  # 设置 API_KEY=生成的密钥

# 方法 2: 直接修改 docker-compose.prod.yml
vim docker-compose.prod.yml
# 修改:
#   - API_KEY=生成的密钥
#   - ENABLE_AUTH=true

# 重启容器
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

---

## ✅ 验证清单

同步完成后，请验证以下项目：

- [ ] 容器状态正常：`docker ps | grep sftlogapi-v2`
- [ ] 健康检查通过：`curl http://localhost:5001/api/health`
- [ ] 日志查询正常：查询一条实际存在的日志
- [ ] SQL 注入防护：尝试注入攻击应被拒绝
- [ ] 路径遍历防护：尝试路径遍历应被拒绝
- [ ] API Key 认证（如启用）：无密钥应返回 401

---

## 🔧 故障排查

### 容器启动失败

```bash
# 查看容器日志
docker logs sftlogapi-v2 --tail 100

# 常见错误：
# 1. API_KEY 未设置但 ENABLE_AUTH=true
#    解决：设置 API_KEY 或设置 ENABLE_AUTH=false

# 2. 端口被占用
#    解决：docker ps 查看占用端口的容器并停止

# 3. 配置文件错误
#    解决：检查 config.env 和 docker-compose.prod.yml
```

### 查询失败

```bash
# 检查日志目录挂载
docker exec sftlogapi-v2 ls -la /data/logs

# 检查数据库
docker exec sftlogapi-v2 sqlite3 /data/index/logs_trace.db ".tables"

# 检查 Python 依赖
docker exec sftlogapi-v2 pip list | grep -E "Flask|msgpack"
```

---

## 📞 联系支持

如有问题，请联系：
- 开发负责人：xiegm900209
- 项目仓库：https://github.com/xiegm900209/sftlogapi2

---

**最后更新**: 2026-04-17  
**文档版本**: 1.0
