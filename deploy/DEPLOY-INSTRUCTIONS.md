# 🚀 sftlogapi v2 - 联调环境部署指南

**部署时间**: 2026-04-17  
**部署内容**: 安全修复（3 个高危漏洞）  
**部署方式**: 手动执行（网络限制）

---

## ✅ 准备工作已完成

### 1. 代码已提交 GitHub
```
Commit 49e1576 - docs: 添加部署报告和 API Key 记录
Commit fd312b0 - docs: 新增联调环境手动同步指南
Commit d4c6037 - feat: 新增联调环境同步脚本
Commit 6869552 - security: 修复 3 个高危安全漏洞
```

### 2. API Key 已生成
```
API_KEY: b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
```

### 3. 部署包已准备
```
文件：/tmp/sftlogapi-deploy-20260417_143850.tar.gz
大小：172K
```

---

## 📋 部署步骤

### 方式一：一键部署脚本（推荐）

#### 步骤 1: 登录跳板机
```bash
ssh root@192.168.13.104
# 密码：Lt_Sc360
```

#### 步骤 2: 确认部署包存在
```bash
ls -lh /tmp/sftlogapi-deploy-20260417_143850.tar.gz
# 应显示约 172K
```

如果文件不存在，从本地上传：
```bash
# 在本地机器执行
scp /tmp/sftlogapi-deploy-20260417_143850.tar.gz root@192.168.13.104:/tmp/
```

#### 步骤 3: 复制部署脚本到跳板机

在本地执行：
```bash
scp /root/sft/sftlogapi-v2/deploy/remote-deploy.sh root@192.168.13.104:/tmp/deploy.sh
```

或者直接复制脚本内容（复制 `deploy/remote-deploy.sh` 的全部内容）

#### 步骤 4: 执行部署

```bash
# 在跳板机上执行
chmod +x /tmp/deploy.sh
export PATH=/usr/local/bin:$PATH
bash /tmp/deploy.sh
```

脚本会自动完成：
- ✅ 传输部署包到后端主机
- ✅ 备份原代码
- ✅ 解压新代码
- ✅ 配置 API Key
- ✅ 重启容器
- ✅ 验证部署（健康检查 + 安全测试）

---

### 方式二：手动分步执行

如果脚本执行失败，可以手动执行以下步骤：

```bash
# 1. 登录跳板机
ssh root@192.168.13.104
# 密码：Lt_Sc360

# 2. 设置 PATH
export PATH=/usr/local/bin:$PATH

# 3. 传输部署包到后端主机
sshpass -p 'sftuser' scp -o StrictHostKeyChecking=no \
  /tmp/sftlogapi-deploy-20260417_143850.tar.gz \
  sftuser@192.168.109.77:/tmp/

# 4. 登录后端主机
sshpass -p 'sftuser' ssh -o StrictHostKeyChecking=no sftuser@192.168.109.77

# 5. 在后端主机执行部署
cd /app/sftlogapi-root/sftlogapi-v2

# 备份
cp -r backend backend.bak.$(date +%Y%m%d_%H%M%S)
cp -r scripts scripts.bak.$(date +%Y%m%d_%H%M%S)

# 解压
tar -xzf /tmp/sftlogapi-deploy-20260417_143850.tar.gz

# 配置 API Key
cat > .env << 'EOF'
API_KEY=b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
ENABLE_AUTH=true
DEBUG=false
HOST=0.0.0.0
PORT=5000
CACHE_TTL=3600
CACHE_MAX_SIZE=10000
EOF

# 重启容器
cd /app/sftlogapi-root
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 等待启动
sleep 5

# 验证
curl http://localhost:5001/api/health
```

---

## ✅ 验证清单

部署完成后，请确认以下项目：

### 容器状态
```bash
docker ps | grep sftlogapi-v2
# 应显示容器运行中
```

### 健康检查
```bash
curl http://192.168.109.77:5001/api/health
# 应返回：{"success":true,"status":"healthy",...}
```

### SQL 注入防护
```bash
curl "http://192.168.109.77:5001/api/log-query?log_time=2026040809;DROP+TABLE+test&req_sn=TEST"
# 应返回：日志时间格式错误
```

### 路径遍历防护
```bash
curl "http://192.168.109.77:5001/api/log-query?log_time=2026040809&service=../etc/passwd&req_sn=TEST"
# 应返回：服务名称格式错误
```

### API Key 认证（如果 ENABLE_AUTH=true）
```bash
# 无密钥请求（应返回 401）
curl "http://192.168.109.77:5001/api/log-query?log_time=2026040809&req_sn=TEST"

# 带密钥请求（应返回查询结果）
curl -H "Authorization: Bearer b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f" \
     "http://192.168.109.77:5001/api/log-query?log_time=2026040809&req_sn=TEST"
```

---

## 🔑 API Key 管理

### 当前生效的 API Key
```
b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
```

### 保存位置
| 位置 | 路径 |
|------|------|
| 本地备份 | `/root/sft/sftlogapi-v2/deploy/api_keys.md` |
| 本地配置 | `/root/sft/sftlogapi-v2/.env` |
| 联调环境 | `/app/sftlogapi-root/sftlogapi-v2/.env` |

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
```

### 部署包传输失败
```bash
# 检查跳板机 sshpass
export PATH=/usr/local/bin:$PATH
which sshpass

# 检查后端主机连通性
sshpass -p 'sftuser' ssh -o StrictHostKeyChecking=no sftuser@192.168.109.77 'hostname'
```

---

## 📞 联系支持

- GitHub 仓库：https://github.com/xiegm900209/sftlogapi2
- 部署文档：`deploy/DEPLOYMENT-REPORT.md`
- API Key 记录：`deploy/api_keys.md`

---

**最后更新**: 2026-04-17  
**下次轮换**: 2026-07-17
