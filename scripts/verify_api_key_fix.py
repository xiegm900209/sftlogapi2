#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Key 安全修复验证脚本
检查所有相关文件是否已正确修复
"""

import os
import re
import sys

SCRIPT_DIR = os.path.dirname(__file__)
ISSUES = []
PASSED = []

def check_file(filepath, checks):
    """检查文件是否符合安全要求"""
    full_path = os.path.join(SCRIPT_DIR, filepath)
    
    if not os.path.exists(full_path):
        ISSUES.append(f"❌ 文件不存在：{filepath}")
        return
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for check_name, pattern, should_exist in checks:
        match = re.search(pattern, content, re.MULTILINE)
        
        if should_exist and not match:
            ISSUES.append(f"❌ {filepath}: 缺少 {check_name}")
        elif not should_exist and match:
            ISSUES.append(f"❌ {filepath}: 发现不安全配置 - {check_name}")
        else:
            PASSED.append(f"✅ {filepath}: {check_name} 检查通过")

def main():
    print("=" * 60)
    print("🔍 API Key 安全修复验证")
    print("=" * 60)
    print()
    
    # 检查 backend/app.py
    check_file('backend/app.py', [
        ("无默认 API Key", r"'API_KEY': os\.environ\.get\('API_KEY'\)", True),
        ("配置验证函数", r"def validate_config\(\):", True),
        ("启动时验证", r"validate_config\(\)", True),
        ("无硬编码密钥", r"zhiduoxing-2026-secret-key", False),
    ])
    
    # 检查 config.env.example
    check_file('config.env.example', [
        ("占位符格式", r"API_KEY=<YOUR_SECURE_API_KEY_HERE>", True),
        ("无默认密钥", r"zhiduoxing-2026-secret-key", False),
        ("安全提示注释", r"openssl rand", True),
    ])
    
    # 检查 docker-compose.prod.yml
    check_file('docker-compose.prod.yml', [
        ("环境变量引用", r'API_KEY=\$\{API_KEY:', True),
        ("无硬编码密钥", r"zhiduoxing-2026-secret-key", False),
    ])
    
    # 检查 deploy.sh
    check_file('deploy.sh', [
        ("API Key 验证函数", r"check_api_key\(\)", True),
        ("默认值检测", r"zhiduoxing-2026-secret-key", True),
        ("调用验证函数", r"check_api_key", True),
    ])
    
    # 检查 .env.example 是否存在
    if os.path.exists(os.path.join(SCRIPT_DIR, '.env.example')):
        PASSED.append("✅ .env.example: 文件存在")
    else:
        ISSUES.append("❌ .env.example: 文件不存在")
    
    # 检查 generate_api_key.sh 是否存在
    if os.path.exists(os.path.join(SCRIPT_DIR, 'scripts/generate_api_key.sh')):
        PASSED.append("✅ scripts/generate_api_key.sh: 文件存在")
    else:
        ISSUES.append("❌ scripts/generate_api_key.sh: 文件不存在")
    
    # 输出结果
    print("✅ 通过检查:")
    for item in PASSED:
        print(f"  {item}")
    
    if ISSUES:
        print()
        print("❌ 发现问题:")
        for item in ISSUES:
            print(f"  {item}")
        print()
        print(f"总计：{len(PASSED)} 通过，{len(ISSUES)} 失败")
        sys.exit(1)
    else:
        print()
        print("=" * 60)
        print("🎉 所有检查通过！API Key 安全修复已完成。")
        print("=" * 60)
        sys.exit(0)

if __name__ == '__main__':
    main()
