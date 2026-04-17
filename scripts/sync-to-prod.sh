#!/bin/bash
# sftlogapi v2 - 联调环境同步脚本
# 安全修复代码同步到联调环境

set -e

echo "=========================================="
echo "🚀 sftlogapi v2 - 联调环境同步脚本"
echo "=========================================="
echo ""

# 配置
JUMP_HOST="192.168.13.104"
JUMP_USER="root"
JUMP_PASS="Lt_Sc360"

MIDDLE_HOST="192.168.109.75"
MIDDLE_USER="sftuser"
MIDDLE_PASS="sftuser"

BACKEND_HOST="192.168.109.77"
BACKEND_USER="sftuser"
FRONTEND_HOST="192.168.109.54"
FRONTEND_USER="sftuser"

LOCAL_DIR="/root/sft/sftlogapi-v2"
REMOTE_BACKEND_DIR="/app/sftlogapi-root/sftlogapi-v2"
REMOTE_FRONTEND_DIR="/app/tengine/frontend"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 git 状态
check_git_status() {
    log_info "检查 Git 状态..."
    cd "$LOCAL_DIR"
    
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        log_error "当前目录不是 Git 仓库"
        exit 1
    fi
    
    # 检查是否有未提交的更改
    if ! git diff-index --quiet HEAD --; then
        log_warn "存在未提交的更改，请先提交"
        git status
        read -p "是否继续同步？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    log_info "Git 状态检查通过"
}

# 同步后端代码
sync_backend() {
    log_info "开始同步后端代码到 $BACKEND_HOST..."
    
    # 创建临时打包文件
    TEMP_TAR=$(mktemp /tmp/sftlogapi-backend-XXXXXX.tar.gz)
    
    # 打包需要同步的文件
    cd "$LOCAL_DIR"
    tar -czf "$TEMP_TAR" \
        backend/ \
        scripts/ \
        config.env.example \
        .env.example \
        docker-compose.prod.yml \
        Dockerfile \
        requirements.txt \
        DEPLOYMENT.md \
        README.md
    
    log_info "打包完成：$TEMP_TAR"
    
    # 使用 sshpass 传输（需要安装 sshpass）
    if command -v sshpass &> /dev/null; then
        # 通过跳板机传输
        log_info "通过跳板机传输到 $BACKEND_HOST..."
        
        # 方法 1: 直接 scp (如果网络可达)
        if sshpass -p "$MIDDLE_PASS" ssh -o StrictHostKeyChecking=no \
            -o ConnectTimeout=10 \
            "$MIDDLE_USER"@"$MIDDLE_HOST" \
            "sshpass -p '$MIDDLE_PASS' ssh -o StrictHostKeyChecking=no \
            $BACKEND_USER@$BACKEND_HOST 'echo 连接成功'" 2>/dev/null; then
            
            # 传输文件
            sshpass -p "$MIDDLE_PASS" ssh -o StrictHostKeyChecking=no \
                "$MIDDLE_USER"@"$MIDDLE_HOST" \
                "sshpass -p '$MIDDLE_PASS' scp -o StrictHostKeyChecking=no \
                $BACKEND_USER@$BACKEND_HOST:/tmp/sftlogapi-backend.tar.gz" \
                < "$TEMP_TAR"
            
            log_info "传输成功"
        else
            log_warn "自动传输失败，请手动执行以下命令:"
            echo ""
            echo "1. 连接到跳板机:"
            echo "   ssh root@$JUMP_HOST (密码：$JUMP_PASS)"
            echo ""
            echo "2. 连接到中间机:"
            echo "   ssh $MIDDLE_USER@$MIDDLE_HOST (密码：$MIDDLE_PASS)"
            echo ""
            echo "3. 连接到目标机:"
            echo "   ssh $BACKEND_USER@$BACKEND_HOST (密码：$MIDDLE_PASS)"
            echo ""
            echo "4. 上传文件并部署"
            echo ""
        fi
    else
        log_error "未安装 sshpass，请手动同步或使用 rsync"
        log_warn "安装 sshpass: apt-get install sshpass (Ubuntu) 或 yum install sshpass (CentOS)"
    fi
    
    # 清理临时文件
    rm -f "$TEMP_TAR"
}

# 同步前端代码
sync_frontend() {
    log_info "开始同步前端代码到 $FRONTEND_HOST..."
    
    # 前端代码在 frontend/dist 目录
    if [ ! -d "$LOCAL_DIR/frontend/dist" ]; then
        log_warn "frontend/dist 目录不存在，需要先构建前端"
        log_info "执行前端构建..."
        cd "$LOCAL_DIR/frontend"
        if [ -f "package.json" ]; then
            npm install && npm run build
        else
            log_error "frontend 目录没有 package.json，无法构建"
        fi
    fi
    
    # 打包前端文件
    TEMP_TAR=$(mktemp /tmp/sftlogapi-frontend-XXXXXX.tar.gz)
    cd "$LOCAL_DIR/frontend"
    tar -czf "$TEMP_TAR" dist/
    
    log_info "前端打包完成：$TEMP_TAR"
    
    # 清理临时文件
    rm -f "$TEMP_TAR"
}

# 重启容器
restart_container() {
    log_info "重启后端容器..."
    
    # 通过 SSH 执行重启命令
    sshpass -p "$MIDDLE_PASS" ssh -o StrictHostKeyChecking=no \
        "$MIDDLE_USER"@"$MIDDLE_HOST" \
        "sshpass -p '$MIDDLE_PASS' ssh -o StrictHostKeyChecking=no \
        $BACKEND_USER@$BACKEND_HOST '
        cd $REMOTE_BACKEND_DIR
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml up -d
        docker logs -f sftlogapi-v2 --tail 50
        '" || log_warn "自动重启失败，请手动执行"
}

# 验证部署
verify_deployment() {
    log_info "验证部署..."
    
    # 健康检查
    HEALTH_URL="http://$BACKEND_HOST:5001/api/health"
    
    for i in {1..10}; do
        sleep 2
        if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
            log_info "健康检查通过 ✅"
            curl -s "$HEALTH_URL" | python3 -m json.tool 2>/dev/null || curl -s "$HEALTH_URL"
            return 0
        fi
        log_warn "等待容器启动... ($i/10)"
    done
    
    log_error "健康检查失败 ❌"
    return 1
}

# 主流程
main() {
    echo ""
    echo "请选择同步方式:"
    echo "  1) 自动同步（需要 sshpass）"
    echo "  2) 手动同步（生成同步指南）"
    echo "  3) 仅检查 Git 状态"
    echo ""
    read -p "请选择 [1-3]: " choice
    
    case $choice in
        1)
            check_git_status
            sync_backend
            sync_frontend
            restart_container
            verify_deployment
            ;;
        2)
            echo ""
            echo "=========================================="
            echo "📋 手动同步指南"
            echo "=========================================="
            echo ""
            echo "步骤 1: 打包代码"
            echo "  cd $LOCAL_DIR"
            echo "  tar -czf /tmp/sftlogapi-fix.tar.gz backend/ scripts/ config.env.example .env.example docker-compose.prod.yml"
            echo ""
            echo "步骤 2: 连接到跳板机"
            echo "  ssh $JUMP_USER@$JUMP_HOST"
            echo "  密码：$JUMP_PASS"
            echo ""
            echo "步骤 3: 连接到中间机"
            echo "  ssh $MIDDLE_USER@$MIDDLE_HOST"
            echo "  密码：$MIDDLE_PASS"
            echo ""
            echo "步骤 4: 连接到后端主机"
            echo "  ssh $BACKEND_USER@$BACKEND_HOST"
            echo "  密码：$MIDDLE_PASS"
            echo ""
            echo "步骤 5: 上传并部署"
            echo "  cd $REMOTE_BACKEND_DIR"
            echo "  # 备份原代码"
            echo "  cp -r backend backend.bak.\$(date +%Y%m%d_%H%M%S)"
            echo "  # 上传新代码 (使用 scp 或 rz)"
            echo "  tar -xzf /tmp/sftlogapi-fix.tar.gz"
            echo "  # 重启容器"
            echo "  docker-compose -f docker-compose.prod.yml down"
            echo "  docker-compose -f docker-compose.prod.yml up -d"
            echo ""
            echo "步骤 6: 验证"
            echo "  curl http://localhost:5001/api/health"
            echo ""
            ;;
        3)
            check_git_status
            ;;
        *)
            log_error "无效选择"
            exit 1
            ;;
    esac
}

main
