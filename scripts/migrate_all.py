#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量迁移脚本
将现有日志的索引全部同步到 SQLite
"""

import os
import sys
import time
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from indexer.sqlite_sync import SQLiteSyncer
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'build_index.py'))
# 直接导入文件
import importlib.util
spec = importlib.util.spec_from_file_location("build_index", os.path.join(os.path.dirname(__file__), 'build_index.py'))
build_index_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_index_module)
LogIndexer = build_index_module.LogIndexer


def find_all_log_files(log_base_dir: str):
    """查找所有日志文件"""
    log_files = []
    
    for service_dir in os.listdir(log_base_dir):
        service_path = os.path.join(log_base_dir, service_dir)
        if not os.path.isdir(service_path):
            continue
        
        for filename in os.listdir(service_path):
            if filename.endswith('.log') or filename.endswith('.log.gz'):
                log_files.append(os.path.join(service_path, filename))
    
    return log_files


def find_all_index_files(log_base_dir: str):
    """查找所有索引文件"""
    index_files = []
    
    # 查找服务目录下的索引
    for service_dir in os.listdir(log_base_dir):
        service_path = os.path.join(log_base_dir, service_dir)
        if not os.path.isdir(service_path):
            continue
        
        for filename in os.listdir(service_path):
            if filename.endswith('.index.json') or filename.endswith('.msgpack'):
                index_files.append(os.path.join(service_path, filename))
    
    # 查找 logs_index 目录
    logs_index_dir = os.path.join(log_base_dir, 'logs_index')
    if os.path.exists(logs_index_dir):
        for filename in os.listdir(logs_index_dir):
            if filename.endswith('.json'):
                index_files.append(os.path.join(logs_index_dir, filename))
    
    return index_files


def build_missing_indexes(log_base_dir: str, format: str = 'msgpack'):
    """为没有索引的日志文件构建索引"""
    log_files = find_all_log_files(log_base_dir)
    
    missing = []
    for log_file in log_files:
        # 检查是否有对应索引
        if log_file.endswith('.log.gz'):
            index_file = log_file.replace('.log.gz', '.log.index.json')
            msgpack_index = log_file.replace('.log.gz', '.log.msgpack')
        else:
            index_file = log_file + '.index.json'
            msgpack_index = log_file + '.msgpack'
        
        if not os.path.exists(index_file) and not os.path.exists(msgpack_index):
            missing.append(log_file)
    
    if not missing:
        print("✅ 所有日志文件都有索引")
        return
    
    print(f"发现 {len(missing)} 个日志文件缺少索引，开始构建...")
    
    for i, log_file in enumerate(missing, 1):
        print(f"\n[{i}/{len(missing)}] {os.path.basename(log_file)}")
        indexer = LogIndexer()
        indexer.index_file(log_file)
        
        # 保存为 msgpack
        if log_file.endswith('.log.gz'):
            output = log_file.replace('.log.gz', '.log.msgpack')
        else:
            output = log_file + '.msgpack'
        
        indexer.save_index(output, format='msgpack')


def sync_all_indexes(log_base_dir: str, db_path: str):
    """同步所有索引到 SQLite"""
    syncer = SQLiteSyncer(db_path)
    
    # 查找所有索引文件
    index_files = find_all_index_files(log_base_dir)
    
    # 过滤 msgpack 和 json
    index_files = [f for f in index_files if f.endswith('.msgpack') or f.endswith('.index.json')]
    
    print(f"发现 {len(index_files)} 个索引文件")
    
    success_count = 0
    total_records = 0
    start_time = time.time()
    
    for i, index_file in enumerate(index_files, 1):
        print(f"\n[{i}/{len(index_files)}] {os.path.basename(index_file)}")
        success, records = syncer.sync_index_file(index_file)
        
        if success:
            success_count += 1
            total_records += records
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*50}")
    print(f"迁移完成!")
    print(f"  成功：{success_count}/{len(index_files)}")
    print(f"  总记录数：{total_records:,}")
    print(f"  耗时：{elapsed:.1f}s")
    print(f"{'='*50}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='全量迁移脚本')
    parser.add_argument('--log-dir', default='/root/sft/testlogs', help='日志根目录')
    parser.add_argument('--db-path', default='/root/sft/sftlogapi-v2/data/index/logs_index.db', help='数据库路径')
    parser.add_argument('--build-missing', action='store_true', help='构建缺失的索引')
    parser.add_argument('--sync-only', action='store_true', help='只同步，不构建')
    
    args = parser.parse_args()
    
    print(f"""
╔═══════════════════════════════════════════════════════╗
║         sftlogapi v2 - 全量迁移工具                    ║
╠═══════════════════════════════════════════════════════╣
║  日志目录：{args.log_dir}
║  数据库：{args.db_path}
╚═══════════════════════════════════════════════════════╝
    """)
    
    if args.build_missing or not args.sync_only:
        print("\n步骤 1: 构建缺失索引...")
        build_missing_indexes(args.log_dir)
    
    print("\n步骤 2: 同步索引到 SQLite...")
    sync_all_indexes(args.log_dir, args.db_path)


if __name__ == '__main__':
    main()
