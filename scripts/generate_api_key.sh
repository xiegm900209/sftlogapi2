#!/bin/bash
# sftlogapi v2 - API Key 生成工具
# 用于生成安全的 API Key 并更新配置文件

set -e

echo "=========================================="
echo "🔑 sftlogapi v2 - API Key 生成工具"
echo "=========================================="
echo ""

# 生成 32 字节（64 字符十六进制）的随机密钥
API_KEY=$(openssl rand -hex 32)

echo "✅ 已生成安全的 API Key:"
echo ""
echo "   $API_KEY"
echo ""

# 询问是否更新配置文件
read -p "是否更新 config.env 文件？(y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    CONFIG_FILE="config.env"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "⚠️  config.env 文件不存在，正在创建..."
        cp config.env.example config.env
    fi
    
    # 更新 API_KEY
    if grep -q "^API_KEY=" "$CONFIG_FILE"; then
        sed -i "s|^API_KEY=.*|API_KEY=$API_KEY|" "$CONFIG_FILE"
    else
        echo "API_KEY=$API_KEY" >> "$CONFIG_FILE"
    fi
    
    # 启用认证
    if grep -q "^ENABLE_AUTH=" "$CONFIG_FILE"; then
        sed -i "s|^ENABLE_AUTH=.*|ENABLE_AUTH=true|" "$CONFIG_FILE"
    else
        echo "ENABLE_AUTH=true" >> "$CONFIG_FILE"
    fi
    
    echo ""
    echo "✅ 已更新 $CONFIG_FILE 文件"
    echo ""
    echo "📋 更新后的配置:"
    grep -E "^API_KEY=|^ENABLE_AUTH=" "$CONFIG_FILE"
    echo ""
else
    echo ""
    echo "💡 手动使用方法:"
    echo "   1. 复制上面的 API_KEY"
    echo "   2. 编辑 config.env 文件"
    echo "   3. 设置 API_KEY=你的密钥"
    echo "   4. 设置 ENABLE_AUTH=true"
    echo ""
fi

echo "=========================================="
echo "⚠️  重要提示:"
echo "   - 请妥善保管 API_KEY，不要提交到版本控制"
echo "   - 建议将 API_KEY 存储在密钥管理系统中"
echo "   - 生产环境请使用独立的密钥管理方案"
echo "=========================================="
