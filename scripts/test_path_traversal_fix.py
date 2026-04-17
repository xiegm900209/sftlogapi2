#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径遍历防护验证脚本
测试路径遍历攻击是否被正确拦截
"""

import os
import sys
import tempfile
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_DIR, 'backend')

sys.path.insert(0, BACKEND_DIR)


def test_path_traversal_protection():
    """测试路径遍历防护"""
    print("=" * 60)
    print("🔍 路径遍历防护测试")
    print("=" * 60)
    print()
    
    from query.log_reader import LogReader, PathTraversalError
    
    # 创建临时测试目录
    test_base = tempfile.mkdtemp(prefix='sftlog_test_')
    test_logs_dir = os.path.join(test_base, 'logs')
    test_service_dir = os.path.join(test_logs_dir, 'sft-aipg')
    os.makedirs(test_service_dir)
    
    # 创建测试文件
    test_file = os.path.join(test_service_dir, 'sft-aipg_2026040809.log')
    with open(test_file, 'w') as f:
        f.write('[2026-04-08 09:00:00.000][thread][trace123][INFO][C02][sft][sft-aipg][]-[test log]\n')
    
    # 创建敏感文件（模拟 /etc/passwd）
    sensitive_file = os.path.join(test_base, 'sensitive.txt')
    with open(sensitive_file, 'w') as f:
        f.write('SECRET_DATA=should_not_be_accessible\n')
    
    try:
        reader = LogReader(test_logs_dir)
        
        # 测试用例
        test_cases = [
            # (文件名，服务，期望结果，描述)
            ("sft-aipg_2026040809.log", "sft-aipg", True, "合法的文件名"),
            ("sft-aipg_2026040809.log.gz", "sft-aipg", True, "文件不存在（返回 None 正常）"),
            ("../sensitive.txt", "sft-aipg", False, "路径遍历攻击 - ../"),
            ("../../etc/passwd", "sft-aipg", False, "路径遍历攻击 - ../../"),
            ("....//....//etc/passwd", "sft-aipg", False, "路径遍历攻击 - 混淆"),
            ("/etc/passwd", "sft-aipg", False, "绝对路径攻击"),
            ("sft-aipg/../../../etc/passwd", "sft-aipg", False, "路径遍历攻击 - 混合"),
            ("file.txt", "sft-aipg", False, "不允许的扩展名"),
            ("malicious.php", "sft-aipg", False, "危险扩展名"),
            ("test.log; cat /etc/passwd", "sft-aipg", False, "命令注入攻击"),
            ("$(cat /etc/passwd).log", "sft-aipg", False, "命令替换攻击"),
            ("test%00.log", "sft-aipg", False, "空字节注入"),
            ("", "sft-aipg", False, "空文件名"),
        ]
        
        passed = 0
        failed = 0
        
        for filename, service, should_pass, description in test_cases:
            try:
                # 对于不存在的文件，_resolve_file_path 返回 None 而不是抛出异常
                result = reader._resolve_file_path(filename, service)
                
                if should_pass:
                    if result and os.path.exists(result):
                        print(f"✅ {description}: 正确通过")
                        passed += 1
                    elif result is None and filename.endswith('.gz'):
                        # 文件不存在但格式合法也算通过（返回 None 是正常的）
                        print(f"✅ {description}: 格式验证通过（文件不存在返回 None 正常）")
                        passed += 1
                    else:
                        print(f"❌ {description}: 应该通过但被拒绝")
                        failed += 1
                else:
                    print(f"❌ {description}: 应该拒绝但通过了 (路径：{result})")
                    failed += 1
                    
            except PathTraversalError as e:
                if not should_pass:
                    print(f"✅ {description}: 正确拦截 - {str(e)[:50]}")
                    passed += 1
                else:
                    print(f"❌ {description}: 错误拦截 - {e}")
                    failed += 1
            except Exception as e:
                print(f"❌ {description}: 意外异常 - {e}")
                failed += 1
        
        print()
        print("=" * 60)
        print(f"测试结果：{passed} 通过，{failed} 失败")
        print("=" * 60)
        
        return failed == 0
        
    finally:
        # 清理测试目录
        shutil.rmtree(test_base, ignore_errors=True)


def test_safe_join_path():
    """测试安全路径拼接"""
    print()
    print("=" * 60)
    print("🔍 安全路径拼接测试")
    print("=" * 60)
    print()
    
    from query.log_reader import LogReader, PathTraversalError
    
    # 创建临时测试目录
    test_base = tempfile.mkdtemp(prefix='sftlog_test_')
    
    try:
        reader = LogReader(test_base)
        
        test_cases = [
            # (基础目录，文件名，期望结果，描述)
            (test_base, "test.log", True, "正常文件名"),
            (test_base, "subdir/test.log", False, "包含子目录"),
            (test_base, "../etc/passwd", False, "父目录遍历"),
            (test_base, "..\\etc\\passwd", False, "Windows 风格遍历"),
            (test_base, "test.log.gz", True, "压缩文件"),
        ]
        
        passed = 0
        failed = 0
        
        for base_dir, filename, should_pass, description in test_cases:
            try:
                result = reader._safe_join_path(base_dir, filename)
                
                if should_pass:
                    print(f"✅ {description}: 正确通过 (路径：{result})")
                    passed += 1
                else:
                    print(f"❌ {description}: 应该拒绝但通过了 (路径：{result})")
                    failed += 1
                    
            except PathTraversalError as e:
                if not should_pass:
                    print(f"✅ {description}: 正确拦截 - {str(e)[:50]}")
                    passed += 1
                else:
                    print(f"❌ {description}: 错误拦截 - {e}")
                    failed += 1
            except Exception as e:
                print(f"❌ {description}: 意外异常 - {e}")
                failed += 1
        
        print()
        print("=" * 60)
        print(f"路径拼接测试：{passed} 通过，{failed} 失败")
        print("=" * 60)
        
        return failed == 0
        
    finally:
        # 清理测试目录
        shutil.rmtree(test_base, ignore_errors=True)


def test_filename_validation():
    """测试文件名验证"""
    print()
    print("=" * 60)
    print("🔍 文件名验证测试")
    print("=" * 60)
    print()
    
    from query.log_reader import LogReader, PathTraversalError
    
    test_base = tempfile.mkdtemp(prefix='sftlog_test_')
    
    try:
        reader = LogReader(test_base)
        
        test_cases = [
            ("sft-aipg_2026040809.log", True, "标准日志文件名"),
            ("sft-trxpay_2026040809.log.gz", True, "压缩日志文件名"),
            ("test_file.log", True, "带下划线"),
            ("test-file.log", True, "带连字符"),
            ("TEST.LOG", False, "大写扩展名"),
            ("test.log.txt", False, "多重扩展名"),
            ("test.php", False, "PHP 文件"),
            ("test.sh", False, "Shell 脚本"),
            ("test.exe", False, "可执行文件"),
            ("../../../etc/passwd", False, "路径遍历"),
            ("/etc/passwd", False, "绝对路径"),
            ("", False, "空字符串"),
            ("test.log;", False, "包含分号"),
            ("test`whoami`.log", False, "包含反引号"),
            ("$(whoami).log", False, "包含命令替换"),
        ]
        
        passed = 0
        failed = 0
        
        for filename, should_pass, description in test_cases:
            try:
                result = reader._validate_filename(filename)
                
                if should_pass:
                    print(f"✅ {description}: 正确通过")
                    passed += 1
                else:
                    print(f"❌ {description}: 应该拒绝但通过了")
                    failed += 1
                    
            except PathTraversalError as e:
                if not should_pass:
                    print(f"✅ {description}: 正确拦截 - {str(e)[:50]}")
                    passed += 1
                else:
                    print(f"❌ {description}: 错误拦截 - {e}")
                    failed += 1
            except Exception as e:
                print(f"❌ {description}: 意外异常 - {e}")
                failed += 1
        
        print()
        print("=" * 60)
        print(f"文件名验证：{passed} 通过，{failed} 失败")
        print("=" * 60)
        
        return failed == 0
        
    finally:
        # 清理测试目录
        shutil.rmtree(test_base, ignore_errors=True)


if __name__ == '__main__':
    test1_passed = test_path_traversal_protection()
    test2_passed = test_safe_join_path()
    test3_passed = test_filename_validation()
    
    print()
    print("=" * 60)
    if test1_passed and test2_passed and test3_passed:
        print("🎉 所有路径遍历防护测试通过！")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查修复")
        sys.exit(1)
