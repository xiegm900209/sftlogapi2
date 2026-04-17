#!/bin/bash
# sftlogapi v2 - 联调环境部署脚本
# 使用方法：在跳板机 (192.168.13.104) 上执行此脚本
# 
# 步骤：
# 1. ssh root@192.168.13.104 (密码：Lt_Sc360)
# 2. 复制此脚本内容到跳板机 /tmp/deploy.sh
# 3. chmod +x /tmp/deploy.sh
# 4. bash /tmp/deploy.sh

set -e

echo "=========================================="
echo "🚀 sftlogapi v2 - 联调环境部署"
echo "=========================================="
echo ""

# 配置
BACKEND_HOST="192.168.109.77"
BACKEND_USER="sftuser"
BACKEND_PASS="sftuser"
BACKEND_DIR="/app/sftlogapi-root/sftlogapi-v2"

DEPLOY_PACKAGE="/tmp/sftlogapi-deploy-20260417_143850.tar.gz"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 设置 PATH 包含 sshpass
export PATH=/usr/local/bin:$PATH

# 检查 sshpass
if ! command -v sshpass &> /dev/null; then
    log_error "sshpass 未找到，请确认 /usr/local/bin/sshpass 存在"
    exit 1
fi
log_info "sshpass 版本：$(sshpass -V 2>&1 | head -1)"

# 检查安装包
if [ ! -f "$DEPLOY_PACKAGE" ]; then
    log_error "部署包不存在：$DEPLOY_PACKAGE"
    log_info "请先从本地上传:"
    echo "  scp /tmp/sftlogapi-deploy-*.tar.gz root@192.168.13.104:/tmp/"
    exit 1
fi
log_info "部署包存在：$DEPLOY_PACKAGE ($(ls -lh $DEPLOY_PACKAGE | awk '{print $5}'))"

# 步骤 1: 传输到后端主机
log_info "步骤 1: 传输部署包到后端主机 $BACKEND_HOST..."

sshpass -p "$BACKEND_PASS" scp -o StrictHostKeyChecking=no -o ConnectTimeout=60 \
    "$DEPLOY_PACKAGE" "$BACKEND_USER"@"$BACKEND_HOST":/tmp/ 2>&1

if [ $? -eq 0 ]; then
    log_info "✅ 传输成功"
else
    log_error "❌ 传输失败"
    exit 1
fi

# 步骤 2: 在后端主机部署
log_info "步骤 2: 在 $BACKEND_HOST 上执行部署..."

sshpass -p "$BACKEND_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=60 \
    "$BACKEND_USER"@"$BACKEND_HOST" "bash -s" << 'REMOTE_SCRIPT'
set -e

echo ""
echo "  [1/7] 进入项目目录..."
cd /app/sftlogapi-root/sftlogapi-v2

echo "  [2/7] 备份原代码..."
BACKUP_TS=$(date +%Y%m%d_%H%M%S)
if [ -d "backend" ]; then
    cp -r backend backend.bak.$BACKUP_TS
    echo "    ✅ backend 备份完成"
fi
if [ -d "scripts" ]; then
    cp -r scripts scripts.bak.$BACKUP_TS
    echo "    ✅ scripts 备份完成"
fi

echo "  [3/7] 解压新代码..."
tar -xzf /tmp/sftlogapi-deploy-20260417_143850.tar.gz
echo "    ✅ 解压完成"

echo "  [4/7] 配置 API Key..."
cat > .env << 'ENVFILE'
# sftlogapi v2 - 联调环境配置
# 生成时间：2026-04-17 14:30
API_KEY=b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f
ENABLE_AUTH=true
DEBUG=false
HOST=0.0.0.0
PORT=5000
CACHE_TTL=3600
CACHE_MAX_SIZE=10000
ENVFILE
echo "    ✅ API Key 配置完成"

# 同时更新 config.env
cp config.env.example config.env 2>/dev/null || true
sed -i 's/^API_KEY=.*/API_KEY=b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f/' config.env 2>/dev/null || true
sed -i 's/^ENABLE_AUTH=.*/ENABLE_AUTH=true/' config.env 2>/dev/null || true
echo "    ✅ config.env 更新完成"

echo "  [5/7] 重启容器..."
cd /app/sftlogapi-root

echo "    停止旧容器..."
docker-compose -f docker-compose.prod.yml down 2>/dev/null || true

echo "    启动新容器..."
docker-compose -f docker-compose.prod.yml up -d

echo "    ✅ 容器重启完成"

echo "  [6/7] 等待服务启动..."
sleep 8

echo "  [7/7] 验证部署..."
echo ""
echo "    容器状态:"
CONTAINER_STATUS=$(docker ps | grep sftlogapi-v2 || echo "")
if [ -n "$CONTAINER_STATUS" ]; then
    echo "    ✅ 容器运行正常"
    echo "    $CONTAINER_STATUS"
else
    echo "    ⚠️ 容器未运行，查看日志:"
    docker logs sftlogapi-v2 --tail 20
fi

echo ""
echo "    健康检查:"
HEALTH_RESP=$(curl -s -f http://localhost:5001/api/health 2>/dev/null || echo "")
if [ -n "$HEALTH_RESP" ]; then
    echo "    ✅ 健康检查通过"
    echo "    $HEALTH_RESP" | python3 -m json.tool 2>/dev/null || echo "    $HEALTH_RESP"
else
    echo "    ⚠️ 健康检查失败"
    curl -s http://localhost:5001/api/health || echo "    无法连接服务"
fi

echo ""
echo "    安全功能验证:"
echo ""
echo "    - SQL 注入防护测试:"
RESP=$(curl -s "http://localhost:5001/api/log-query?log_time=2026040809;DROP+TABLE+test&req_sn=TEST" 2>/dev/null || echo "")
if echo "$RESP" | grep -q "格式错误"; then
    echo "      ✅ 通过 - SQL 注入被拦截"
else
    echo "      ⚠️ 未通过 - 响应：$RESP"
fi

echo ""
echo "    - 路径遍历防护测试:"
RESP=$(curl -s "http://localhost:5001/api/log-query?log_time=2026040809&service=../etc/passwd&req_sn=TEST" 2>/dev/null || echo "")
if echo "$RESP" | grep -q "格式错误"; then
    echo "      ✅ 通过 - 路径遍历被拦截"
else
    echo "      ⚠️ 未通过 - 响应：$RESP"
fi

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📋 API Key 信息:"
echo "   Key: b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f"
echo "   位置：/app/sftlogapi-root/sftlogapi-v2/.env"
echo ""
echo "🔗 访问地址:"
echo "   健康检查：http://192.168.109.77:5001/api/health"
echo "   公网访问：https://tlt-test.allinpay.com/sftlogapi-v2/"
echo ""
echo "📝 日志查看:"
echo "   docker logs -f sftlogapi-v2 --tail 50"
echo ""

REMOTE_SCRIPT

if [ $? -eq 0 ]; then
    log_info "✅ 后端部署成功"
else
    log_error "❌ 后端部署失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "🎉 同步部署完成！"
echo "=========================================="
echo ""
echo "📋 API Key 信息:"
echo "   b7cf32ac3fcbff88088bce13bf49dd181009afd5bd1fbe759e11ccc3e3db4d1f"
echo ""
echo "🔗 访问地址:"
echo "   http://192.168.109.77:5001/api/health"
echo "   https://tlt-test.allinpay.com/sftlogapi-v2/"
echo ""
