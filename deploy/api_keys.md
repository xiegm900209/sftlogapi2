# sftlogapi v2 - API Key 管理记录

## 🔑 当前生效的 API Key

**生成时间**: 2026-04-17 14:30  
**环境**: 联调环境 (192.168.109.77:5001)  
**状态**: ✅ 已部署

| 环境 | API Key | 生成时间 | 部署时间 | 备注 |
|------|---------|----------|----------|------|
| 联调环境 | `b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f` | 2026-04-17 14:30 | 2026-04-17 | 安全修复版本 |

---

## 📋 配置位置

### 联调环境配置路径

```bash
# 配置文件位置
/app/sftlogapi-root/sftlogapi-v2/.env
/app/sftlogapi-root/sftlogapi-v2/config.env

# Docker Compose 配置
/app/sftlogapi-root/sftlogapi-v2/docker-compose.prod.yml
```

### 本地备份位置

```bash
# 本地 Git 仓库
/root/sft/sftlogapi-v2/.env
/root/sft/sftlogapi-v2/deploy/api_keys.md (本文件)
```

---

## 🔧 使用方法

### 测试 API

```bash
# 健康检查（无需认证）
curl http://192.168.109.77:5001/api/health

# 日志查询（需要认证）
curl -H "Authorization: Bearer b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f" \
     "http://192.168.109.77:5001/api/log-query?log_time=2026040809&req_sn=TEST123"

# 或使用 URL 参数
curl "http://192.168.109.77:5001/api/log-query?log_time=2026040809&req_sn=TEST123&api_key=b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f"
```

### 前端配置

在联调环境前端使用时，API Key 会自动附加到请求头。

---

## 📅 历史记录

| 日期 | 操作 | 操作人 | 备注 |
|------|------|--------|------|
| 2026-04-17 | 生成新密钥 | AI Agent | 安全修复版本 |

---

## ⚠️ 安全提示

1. **不要将 API Key 提交到 Git** - 已添加到 .gitignore
2. **定期轮换** - 建议每 90 天更换一次
3. **限制访问** - 仅授权必要人员
4. **监控使用** - 检查异常访问日志

---

## 🔄 密钥轮换流程

```bash
# 1. 生成新密钥
openssl rand -hex 32

# 2. 更新配置文件
vim /app/sftlogapi-root/sftlogapi-v2/.env

# 3. 重启容器
docker-compose -f docker-compose.prod.yml restart

# 4. 验证新密钥
curl -H "Authorization: Bearer <新密钥>" http://192.168.109.77:5001/api/health

# 5. 更新本文档
```

---

**最后更新**: 2026-04-17  
**下次轮换**: 2026-07-17
