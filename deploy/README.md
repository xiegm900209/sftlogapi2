# 🚀 sftlogapi v2 - 部署目录

## 📁 目录说明

本目录包含部署相关的脚本和文档。**敏感信息已移除**，实际部署时需要配置。

## 🔧 使用方法

### 1. 配置本地敏感信息

```bash
# 复制示例配置
cp deploy/.env.local.example deploy/.env.local

# 编辑并填写实际的主机信息和密码
vim deploy/.env.local
```

**注意**: `.env.local` 已添加到 `.gitignore`，不会被提交到 Git。

### 2. 配置同步脚本

```bash
# 编辑同步脚本
vim scripts/sync-to-prod.sh

# 修改以下变量：
# - JUMP_HOST, JUMP_USER
# - MIDDLE_HOST, MIDDLE_USER
# - BACKEND_HOST, BACKEND_USER
# - FRONTEND_HOST, FRONTEND_USER
```

### 3. 执行同步

```bash
# 方式 1: 使用同步脚本
./scripts/sync-to-prod.sh

# 方式 2: 手动同步
# 参考 docs/SYNC-TO-PROD.md
```

## 📋 文件说明

| 文件 | 用途 | 是否包含敏感信息 |
|------|------|-----------------|
| `README.md` | 部署说明 | ❌ 否 |
| `.env.local.example` | 本地配置示例 | ❌ 否（占位符） |
| `.env.local` | 本地实际配置 | ✅ 是（不提交） |

## 🔒 安全提示

1. **不要提交敏感信息** - IP 地址、密码、API Key 等不要提交到 Git
2. **使用 SSH 密钥** - 建议使用 SSH 密钥认证代替密码
3. **定期轮换密钥** - API Key 建议每 90 天更换一次
4. **限制访问权限** - 仅授权必要人员访问部署配置

## 📖 相关文档

- 同步指南：`docs/SYNC-TO-PROD.md`
- 项目部署：`DEPLOYMENT.md`
- 配置示例：`config.env.example`

---

**最后更新**: 2026-04-17  
**安全级别**: ✅ 已清理敏感信息
