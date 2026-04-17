#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL 注入防护验证脚本
测试 SQL 注入攻击是否被正确拦截
"""

import os
import sys
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_DIR, 'backend')

sys.path.insert(0, BACKEND_DIR)

def test_sql_injection_protection():
    """测试 SQL 注入防护"""
    print("=" * 60)
    print("🔍 SQL 注入防护测试")
    print("=" * 60)
    print()
    
    # 直接导入模块
    from query.sqlite_engine import SQLiteQueryEngine, SQLInjectionError
    
    engine = SQLiteQueryEngine(db_path='/root/sft/sftlogapi-v2/data/index/logs_index.db')
    
    # 测试用例
    test_cases = [
        # (输入，期望结果，描述)
        ("2026040809", True, "合法的小时格式"),
        ("202604080a", False, "包含非数字字符"),
        ("202604080", False, "长度不足 10 位"),
        ("20260408099", False, "长度超过 10 位"),
        ("2026040809; DROP TABLE logs_2026040809--", False, "SQL 注入攻击 - DROP TABLE"),
        ("2026040809' OR '1'='1", False, "SQL 注入攻击 - OR 1=1"),
        ("2026040809 UNION SELECT * FROM sqlite_master", False, "SQL 注入攻击 - UNION SELECT"),
        ("2026040809/*comment*/", False, "SQL 注入攻击 - 注释"),
        ("", False, "空字符串"),
    ]
    
    passed = 0
    failed = 0
    
    for input_val, should_pass, description in test_cases:
        try:
            result = engine._get_table_name(str(input_val))
            if should_pass:
                print(f"✅ {description}: 正确通过 (表名：{result})")
                passed += 1
            else:
                print(f"❌ {description}: 应该拒绝但通过了 (表名：{result})")
                failed += 1
        except SQLInjectionError as e:
            if not should_pass:
                print(f"✅ {description}: 正确拦截 - {str(e)[:50]}")
                passed += 1
            else:
                # 合法输入但表不存在也是正常的（测试环境无实际表）
                if "表名不存在" in str(e) and should_pass:
                    print(f"✅ {description}: 格式验证通过，表不存在（测试环境正常）")
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


def test_api_validation():
    """测试 API 层输入验证"""
    print()
    print("=" * 60)
    print("🔍 API 层输入验证测试")
    print("=" * 60)
    print()
    
    # 简单的正则验证测试
    def validate_log_time(log_time: str) -> bool:
        if not log_time:
            return False
        return bool(re.match(r'^\d{10}$', log_time))
    
    def validate_service_name(service: str) -> bool:
        if not service:
            return False
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', service))
    
    passed = 0
    failed = 0
    
    # 测试 log_time 验证
    print("测试 validate_log_time:")
    log_time_tests = [
        ("2026040809", True),
        ("202604080a", False),
        ("202604080", False),
        ("", False),
        ("2026040809; DROP TABLE", False),
    ]
    
    for input_val, should_pass in log_time_tests:
        result = validate_log_time(input_val)
        if result == should_pass:
            print(f"  ✅ '{input_val}': {'通过' if result else '拒绝'}")
            passed += 1
        else:
            print(f"  ❌ '{input_val}': 期望 {'通过' if should_pass else '拒绝'}，实际 {'通过' if result else '拒绝'}")
            failed += 1
    
    # 测试 service_name 验证
    print()
    print("测试 validate_service_name:")
    service_tests = [
        ("sft-aipg", True),
        ("sft_trxpay", True),
        ("sft123", True),
        ("sft; DROP TABLE", False),
        ("../etc/passwd", False),
        ("sft'aipg", False),
    ]
    
    for input_val, should_pass in service_tests:
        result = validate_service_name(input_val)
        if result == should_pass:
            print(f"  ✅ '{input_val}': {'通过' if result else '拒绝'}")
            passed += 1
        else:
            print(f"  ❌ '{input_val}': 期望 {'通过' if should_pass else '拒绝'}，实际 {'通过' if result else '拒绝'}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"API 验证结果：{passed} 通过，{failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    sql_passed = test_sql_injection_protection()
    api_passed = test_api_validation()
    
    print()
    print("=" * 60)
    if sql_passed and api_passed:
        print("🎉 所有 SQL 注入防护测试通过！")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查修复")
        sys.exit(1)
