#!/bin/bash
# sftlogapi v2 - 联调环境同步脚本
# 注意：请将下面的配置修改为你的实际环境配置

set -e

echo "=========================================="
echo "🚀 sftlogapi v2 - 联调环境同步脚本"
echo "=========================================="
echo ""

# ========== 配置区域（请修改为实际值）==========
# 跳板机配置
JUMP_HOST="<YOUR_JUMP_HOST>"      # 例如：192.168.13.104
JUMP_USER="<YOUR_JUMP_USER>"      # 例如：root
# JUMP_PASS 建议使用 SSH 密钥认证，不要硬编码密码

# 中间机配置
MIDDLE_HOST="<YOUR_MIDDLE_HOST>"  # 例如：192.168.109.75
MIDDLE_USER="<YOUR_MIDDLE_USER>"  # 例如：sftuser

# 后端主机配置
BACKEND_HOST="<YOUR_BACKEND_HOST>" # 例如：192.168.109.77
BACKEND_USER="<YOUR_BACKEND_USER>" # 例如：sftuser
BACKEND_DIR="<YOUR_BACKEND_DIR>"   # 例如：/app/sftlogapi-root/sftlogapi-v2

# 前端主机配置
FRONTEND_HOST="<YOUR_FRONTEND_HOST>" # 例如：192.168.109.54
FRONTEND_USER="<YOUR_FRONTEND_USER>" # 例如：sftuser
FRONTEND_DIR="<YOUR_FRONTEND_DIR>"   # 例如：/app/tengine/frontend
# ================================================

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查配置
if [[ "$JUMP_HOST" == "<YOUR_JUMP_HOST>" ]]; then
    log_error "请先配置脚本中的主机信息"
    echo "编辑脚本并修改以下变量："
    echo "  JUMP_HOST, MIDDLE_HOST, BACKEND_HOST, FRONTEND_HOST"
    exit 1
fi

# 检查 git 状态
check_git_status() {
    log_info "检查 Git 状态..."
    cd "$LOCAL_DIR"
    
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        log_error "当前目录不是 Git 仓库"
        exit 1
    fi
    
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

# 打包代码
create_deploy_package() {
    log_info "创建部署包..."
    
    TEMP_TAR=$(mktemp /tmp/sftlogapi-deploy-XXXXXX.tar.gz)
    
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
    
    log_info "部署包创建完成：$TEMP_TAR"
    echo "$TEMP_TAR"
}

# 主流程
main() {
    echo ""
    echo "请选择同步方式:"
    echo "  1) 自动同步（需要配置 SSH 密钥）"
    echo "  2) 手动同步（生成同步指南）"
    echo "  3) 仅检查 Git 状态"
    echo ""
    read -p "请选择 [1-3]: " choice
    
    case $choice in
        1)
            check_git_status
            TEMP_PACKAGE=$(create_deploy_package)
            log_info "请手动将 $TEMP_PACKAGE 传输到目标主机并执行部署"
            log_warn "自动同步需要配置 SSH 密钥认证，请参考 docs/SYNC-TO-PROD.md"
            ;;
        2)
            log_info "请参考 docs/SYNC-TO-PROD.md 进行手动同步"
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
