# 🚀 sftlogapi v2 - Nginx/Tengine 配置指南

## 📋 配置说明

### 网络架构

```
用户 → Nginx (8091) → 静态文件 (/var/www/sftlogapi-v2/)
                  → API (127.0.0.1:5001) → Docker 容器
```

### 配置文件位置

```bash
/usr/local/tengine/conf/conf.d/sftlogapi-v2.conf
```

### 关键配置

#### 1. SPA 路由处理

```nginx
# 所有前端路由都返回 index.html
location /sftlogapi-v2/ {
    alias /var/www/sftlogapi-v2/;
    index index.html;
    try_files $uri $uri/ /sftlogapi-v2/index.html;
}
```

**说明**: `try_files` 确保直接访问 `/sftlogapi-v2/config` 等子路径时，返回 `index.html`，由前端 JavaScript 处理路由。

#### 2. 静态资源缓存

```nginx
location ~* ^/sftlogapi-v2/static/ {
    alias /var/www/sftlogapi-v2/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

#### 3. API 代理

```nginx
location /sftlogapi-v2/api/ {
    proxy_pass http://127.0.0.1:5001/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_connect_timeout 60s;
    proxy_read_timeout 60s;
}
```

## 🔧 部署步骤

### 1. 复制前端文件

```bash
mkdir -p /var/www/sftlogapi-v2/static
cp /root/sft/sftlogapi-v2/frontend/index.html /var/www/sftlogapi-v2/
cp /root/sft/sftlogapi-v2/frontend/static/* /var/www/sftlogapi-v2/static/
```

### 2. 配置 Nginx

```bash
# 编辑配置文件
vim /usr/local/tengine/conf/conf.d/sftlogapi-v2.conf

# 测试配置
/usr/local/tengine/sbin/nginx -t

# 重载配置
/usr/local/tengine/sbin/nginx -s reload
```

### 3. 验证部署

```bash
# 测试首页
curl http://172.16.2.164:8091/sftlogapi-v2/

# 测试子路径（SPA 路由）
curl http://172.16.2.164:8091/sftlogapi-v2/config

# 测试 API
curl http://172.16.2.164:8091/sftlogapi-v2/api/health
```

## ⚠️ 常见问题

### 问题 1: 直接访问子路径跳转到欢迎页

**症状**: 访问 `/sftlogapi-v2/config` 显示 "Welcome to tengine!"

**原因**: `try_files` 配置不正确或缺失

**解决**: 确保主 location 包含：
```nginx
try_files $uri $uri/ /sftlogapi-v2/index.html;
```

### 问题 2: 静态资源 404

**症状**: JS/CSS 文件加载失败

**原因**: `alias` 路径不正确

**解决**: 确认 `/var/www/sftlogapi-v2/static/` 目录存在且包含文件

### 问题 3: API 502 Bad Gateway

**症状**: API 请求返回 502

**原因**: 后端服务未启动或端口错误

**解决**: 
```bash
# 检查容器状态
docker ps | grep sftlogapi

# 检查端口
netstat -tlnp | grep 5001
```

## 📖 相关文档

- [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md) - 完整部署指南
- [SYNC-TO-PROD.md](SYNC-TO-PROD.md) - 联调环境同步指南

---

**最后更新**: 2026-04-17  
**配置版本**: 1.0
