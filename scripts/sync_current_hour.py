#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
当前小时日志实时同步到 SQLite

功能：
- 每 5 分钟扫描一次当前小时的日志文件
- 将新增的日志块索引同步到 SQLite
- 支持增量同步（记录已同步的位置）

使用场景：
- 当前小时日志也需要 SQLite 查询（解决并发内存风险）
- 实时性要求：5 分钟延迟

使用方法：
    # 后台运行（每 5 分钟同步一次）
    python3 sync_current_hour.py --daemon
    
    # 手动同步一次
    python3 sync_current_hour.py --service sft-aipg --sync-once
"""

import os
import sys
import time
import sqlite3
import re
import gzip
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class CurrentHourSyncer:
    """当前小时日志同步器"""
    
    def __init__(self, log_dir: str, db_path: str):
        self.log_dir = log_dir
        self.db_path = db_path
        self.state_file = os.path.join(os.path.dirname(db_path), 'current_hour_state.json')
        self.state = self._load_state()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建 reqsn_mapping 表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reqsn_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT NOT NULL,
                service TEXT NOT NULL,
                req_sn TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                synced_at TEXT DEFAULT (datetime('now')),
                UNIQUE(hour, service, req_sn)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_reqsn_query 
            ON reqsn_mapping(hour, service, req_sn)
        ''')
        
        # 创建 trace_index 表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trace_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT NOT NULL,
                service TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                file TEXT NOT NULL,
                block INTEGER NOT NULL,
                timestamp TEXT,
                level TEXT,
                thread TEXT,
                length INTEGER,
                synced_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trace_query 
            ON trace_index(hour, service, trace_id)
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_hour ON trace_index(hour)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trace_id ON trace_index(trace_id)')
        
        conn.commit()
        conn.close()
    
    def _load_state(self) -> Dict:
        """加载同步状态"""
        import json
        
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        
        return {
            'last_sync': {},  # {service: {file: last_block}}
            'current_hour': None
        }
    
    def _save_state(self):
        """保存同步状态"""
        import json
        
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_current_hour(self) -> str:
        """获取当前小时"""
        return datetime.now().strftime('%Y%m%d%H')
    
    def sync_service(self, service: str) -> int:
        """
        同步指定服务的当前小时日志
        
        Returns:
            同步的记录数
        """
        current_hour = self.get_current_hour()
        service_dir = os.path.join(self.log_dir, service)
        
        if not os.path.exists(service_dir):
            return 0
        
        # 初始化服务状态
        if service not in self.state['last_sync']:
            self.state['last_sync'][service] = {}
        
        # 检查小时是否变化，变化则清空状态
        if self.state.get('current_hour') != current_hour:
            print(f"[INFO] 小时变化：{self.state.get('current_hour')} → {current_hour}")
            self.state['last_sync'][service] = {}
            self.state['current_hour'] = current_hour
        
        # 查找当前小时的日志文件
        log_files = []
        for filename in os.listdir(service_dir):
            if current_hour not in filename:
                continue
            if filename.endswith('.log') or filename.endswith('.log.gz'):
                log_files.append(os.path.join(service_dir, filename))
        
        if not log_files:
            return 0
        
        total_synced = 0
        
        # 处理每个日志文件
        for log_file in log_files:
            synced = self._sync_file(service, current_hour, log_file)
            total_synced += synced
        
        # 保存状态
        self._save_state()
        
        return total_synced
    
    def _sync_file(self, service: str, hour: str, log_file: str) -> int:
        """同步单个日志文件"""
        filename = os.path.basename(log_file)
        
        # 获取上次同步的位置
        last_block = self.state['last_sync'][service].get(filename, -1)
        
        # 打开文件
        try:
            if log_file.endswith('.gz'):
                f = gzip.open(log_file, 'rt', encoding='utf-8', errors='ignore')
            else:
                f = open(log_file, 'r', encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"[ERROR] 打开文件失败 {log_file}: {e}")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        block_num = 0
        current_lines = []
        synced_count = 0
        
        try:
            for line in f:
                # 检查是否为新日志块开头
                if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
                    # 处理上一个块
                    if current_lines and block_num > last_block:
                        self._process_and_insert(
                            cursor, service, hour, current_lines, block_num, filename
                        )
                        synced_count += 1
                    
                    current_lines = [line]
                    block_num += 1
                else:
                    current_lines.append(line)
            
            # 处理最后一个块
            if current_lines and block_num > last_block:
                self._process_and_insert(
                    cursor, service, hour, current_lines, block_num, filename
                )
                synced_count += 1
            
            # 更新状态
            if block_num > last_block:
                self.state['last_sync'][service][filename] = block_num
            
            conn.commit()
            
        except Exception as e:
            print(f"[ERROR] 处理文件失败 {log_file}: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            f.close()
            conn.close()
        
        if synced_count > 0:
            print(f"[DEBUG] {service}/{filename}: 同步 {synced_count} 条 (block {last_block+1} → {block_num})")
        
        return synced_count
    
    def _process_and_insert(self, cursor, service: str, hour: str, 
                           lines: List[str], block_num: int, filename: str):
        """处理日志块并插入 SQLite"""
        if not lines:
            return
        
        first_line = lines[0]
        
        # 解析日志头部
        pattern = r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[\]-\[(.*)$'
        match = re.match(pattern, first_line.strip())
        
        if not match:
            return
        
        timestamp = match.group(1)
        thread = match.group(2)
        trace_id = match.group(3)
        level = match.group(4)
        
        # 提取 REQ_SN
        content = ''.join(lines)
        req_sn = self._extract_req_sn(content)
        length = len(content.encode('utf-8'))
        
        # 插入 trace_index
        cursor.execute('''
            INSERT INTO trace_index 
            (hour, service, trace_id, file, block, timestamp, level, thread, length)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (hour, service, trace_id, filename, block_num, timestamp, level, thread, length))
        
        # 插入 reqsn_mapping（仅 sft-aipg）
        if service == 'sft-aipg' and req_sn:
            cursor.execute('''
                INSERT OR REPLACE INTO reqsn_mapping 
                (hour, service, req_sn, trace_id)
                VALUES (?, ?, ?, ?)
            ''', (hour, service, req_sn, trace_id))
    
    def _extract_req_sn(self, content: str) -> Optional[str]:
        """从日志内容中提取 REQ_SN"""
        # XML 格式
        if '<?xml' in content and '</AIPG>' in content:
            match = re.search(r'<REQ_SN>([^<]+)</REQ_SN>', content)
            if match:
                return match.group(1)
        
        # 文本格式
        match = re.search(r'REQ_SN[=:\s]+([A-Za-z0-9-]+)', content)
        if match:
            return match.group(1)
        
        return None
    
    def run_daemon(self, interval_seconds: int = 300):
        """后台运行，定期同步"""
        print(f"[INFO] 启动后台同步服务 (间隔：{interval_seconds} 秒)")
        print(f"[INFO] 日志目录：{self.log_dir}")
        print(f"[INFO] 数据库：{self.db_path}")
        
        services = [d for d in os.listdir(self.log_dir) 
                   if os.path.isdir(os.path.join(self.log_dir, d))]
        
        print(f"[INFO] 服务：{services}")
        
        try:
            while True:
                total = 0
                
                for service in services:
                    synced = self.sync_service(service)
                    total += synced
                
                if total > 0:
                    print(f"[INFO] 本次同步：{total} 条记录")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n[INFO] 停止同步服务")
            self._save_state()


def main():
    parser = argparse.ArgumentParser(description='当前小时日志实时同步')
    parser.add_argument('--log-dir', '-d', default='/data/logs',
                       help='日志根目录')
    parser.add_argument('--db-path', '-db', default='/data/index/logs_index.db',
                       help='SQLite 数据库路径')
    parser.add_argument('--service', '-s', help='服务名')
    parser.add_argument('--daemon', action='store_true',
                       help='后台运行模式')
    parser.add_argument('--interval', default=300, type=int,
                       help='后台运行间隔（秒，默认 300）')
    parser.add_argument('--sync-once', action='store_true',
                       help='手动同步一次')
    
    args = parser.parse_args()
    
    syncer = CurrentHourSyncer(args.log_dir, args.db_path)
    
    if args.daemon:
        syncer.run_daemon(args.interval)
    
    elif args.sync_once:
        if not args.service:
            print("错误：--sync-once 需要指定 --service")
            sys.exit(1)
        
        synced = syncer.sync_service(args.service)
        print(f"同步完成：{synced} 条记录")
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
