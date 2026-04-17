# 🚀 sftlogapi v2 - 联调环境部署完成报告

**部署时间**: 2026-04-17 14:30  
**部署内容**: 安全修复（3 个高危漏洞）  
**部署状态**: ⏳ 待手动执行

---

## ✅ 已完成的工作

### 1. GitHub 代码提交

```
Commit fd312b0 - docs: 新增联调环境手动同步指南
Commit d4c6037 - feat: 新增联调环境同步脚本
Commit 6869552 - security: 修复 3 个高危安全漏洞
```

**仓库**: https://github.com/xiegm900209/sftlogapi2

### 2. 生成新的 API Key

```
API_KEY: b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
生成时间：2026-04-17 14:30
```

**保存位置**:
- 本地：`/root/sft/sftlogapi-v2/deploy/api_keys.md`
- 本地：`/root/sft/sftlogapi-v2/.env`
- 远程：`/app/sftlogapi-root/sftlogapi-v2/.env`（待部署）

### 3. 部署包准备

```
文件：/tmp/sftlogapi-deploy-20260417_143850.tar.gz
大小：172K
内容：backend/, scripts/, config files, docs
```

---

## 📋 手动部署步骤

由于网络限制，需要手动执行以下步骤：

### 步骤 1: 登录跳板机

```bash
ssh root@192.168.13.104
# 密码：Lt_Sc360
```

### 步骤 2: 确认部署包已上传

```bash
ls -lh /tmp/sftlogapi-deploy-20260417_143850.tar.gz
# 应该看到 172K 大小的文件
```

如果文件不存在，从本地上传：

```bash
# 在本地执行
scp /tmp/sftlogapi-deploy-20260417_143850.tar.gz root@192.168.13.104:/tmp/
```

### 步骤 3: 传输到后端主机

```bash
# 在跳板机执行
ssh sftuser@192.168.109.77
# 密码：sftuser

# 上传文件（在跳板机执行）
scp /tmp/sftlogapi-deploy-20260417_143850.tar.gz sftuser@192.168.109.77:/tmp/
```

### 步骤 4: 在后端主机部署

```bash
# 登录到后端主机后执行
cd /app/sftlogapi-root/sftlogapi-v2

# 1. 备份原代码
cp -r backend backend.bak.$(date +%Y%m%d_%H%M%S)
cp -r scripts scripts.bak.$(date +%Y%m%d_%H%M%S)

# 2. 解压新代码
tar -xzf /tmp/sftlogapi-deploy-20260417_143850.tar.gz

# 3. 配置 API Key
cat > .env << 'EOF'
API_KEY=b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
ENABLE_AUTH=true
DEBUG=false
HOST=0.0.0.0
PORT=5000
CACHE_TTL=3600
CACHE_MAX_SIZE=10000
EOF

# 4. 重启容器
cd /app/sftlogapi-root
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 5. 查看日志
docker logs -f sftlogapi-v2 --tail 50
```

### 步骤 5: 验证部署

```bash
# 健康检查
curl http://localhost:5001/api/health

# 测试 SQL 注入防护
curl "http://localhost:5001/api/log-query?log_time=2026040809;DROP+TABLE+test&req_sn=TEST"
# 应返回：日志时间格式错误

# 测试路径遍历防护
curl "http://localhost:5001/api/log-query?log_time=2026040809&service=../etc/passwd&req_sn=TEST"
# 应返回：服务名称格式错误
```

---

## 🔑 API Key 管理

### 当前生效的 API Key

```
b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
```

### 测试 API

```bash
# 带认证的请求
curl -H "Authorization: Bearer b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f" \
     "http://192.168.109.77:5001/api/log-query?log_time=2026040809&req_sn=TEST123"
```

### 保存位置

| 位置 | 路径 |
|------|------|
| 本地备份 | `/root/sft/sftlogapi-v2/deploy/api_keys.md` |
| 本地配置 | `/root/sft/sftlogapi-v2/.env` |
| 联调环境 | `/app/sftlogapi-root/sftlogapi-v2/.env` |

---

## ✅ 验证清单

部署完成后，请确认以下项目：

- [ ] 容器运行正常：`docker ps | grep sftlogapi-v2`
- [ ] 健康检查通过：`curl http://localhost:5001/api/health`
- [ ] SQL 注入防护生效
- [ ] 路径遍历防护生效
- [ ] API Key 认证正常（如果 ENABLE_AUTH=true）
- [ ] 日志查询功能正常

---

## 📞 联系支持

如有问题，请查看：
- 详细同步指南：`docs/SYNC-TO-PROD.md`
- GitHub 仓库：https://github.com/xiegm900209/sftlogapi2

---

**文档生成时间**: 2026-04-17 14:38  
**下次轮换日期**: 2026-07-17
