#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速修复：为指定小时的 SQLite 数据添加 content 字段
"""

import os
import sys
import sqlite3
import msgpack
import re

def sync_content(log_dir: str, db_path: str, service: str, hour: str):
    """为指定小时同步 content 字段"""
    print(f"同步 content: {service} {hour}")
    
    # 读取 MessagePack 索引
    trace_index_file = os.path.join(log_dir, service, f'{service}_{hour}.log.trace_index.msgpack')
    if not os.path.exists(trace_index_file):
        print(f"  索引文件不存在：{trace_index_file}")
        return
    
    with open(trace_index_file, 'rb') as f:
        data = msgpack.unpack(f)
    
    trace_index = data.get('trace_index', {})
    print(f"  TraceID 数量：{len(trace_index)}")
    
    # 连接 SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 读取日志文件
    log_file = os.path.join(log_dir, service, f'{service}_{hour}.log')
    if not os.path.exists(log_file):
        # 尝试压缩文件
        log_file_gz = log_file + '.gz'
        if os.path.exists(log_file_gz):
            import gzip
            log_file = log_file_gz
        else:
            print(f"  日志文件不存在：{log_file}")
            return
    
    print(f"  读取日志文件：{log_file}")
    
    # 读取所有日志块
    log_blocks = {}  # block_num -> content
    
    if log_file.endswith('.gz'):
        f = gzip.open(log_file, 'rt', encoding='gbk', errors='replace')
    else:
        f = open(log_file, 'r', encoding='gbk', errors='replace')
    
    block_num = 0
    current_lines = []
    
    for line in f:
        if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
            if current_lines:
                log_blocks[block_num] = ''.join(current_lines)
            current_lines = [line]
            block_num += 1
        else:
            current_lines.append(line)
    
    if current_lines:
        log_blocks[block_num] = ''.join(current_lines)
    
    f.close()
    print(f"  读取 {len(log_blocks)} 个日志块")
    
    # 更新 SQLite
    updated = 0
    for trace_id, entries in trace_index.items():
        for entry in entries:
            block = entry.get('block')
            if block is not None and block in log_blocks:
                content = log_blocks[block][:10000]  # 限制长度
                cursor.execute('''
                    UPDATE trace_index 
                    SET content = ? 
                    WHERE hour = ? AND service = ? AND trace_id = ? AND block = ?
                ''', (content, hour, service, trace_id, block))
                updated += 1
    
    conn.commit()
    conn.close()
    print(f"  更新 {updated} 条记录")

if __name__ == '__main__':
    if len(sys.argv) < 5:
        print("用法：python3 sync_content_fix.py <log_dir> <db_path> <service> <hour> [hour2] ...")
        sys.exit(1)
    
    log_dir = sys.argv[1]
    db_path = sys.argv[2]
    service = sys.argv[3]
    hours = sys.argv[4:]
    
    for hour in hours:
        sync_content(log_dir, db_path, service, hour)
