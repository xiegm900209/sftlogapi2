#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
索引同步工具 - MessagePack → SQLite

将压缩生成的 MessagePack 索引文件同步到 SQLite 数据库
实现持久化存储，避免每次加载大文件

使用方法：
    # 同步指定小时
    python3 sync_index_to_sqlite.py --hour 2026040809 --service sft-aipg
    
    # 同步所有服务的小时
    python3 sync_index_to_sqlite.py --hour 2026040809
    
    # 清理 2 天前的数据
    python3 sync_index_to_sqlite.py --cleanup --retention-days 2
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path

# 尝试导入 msgpack
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    print("错误：msgpack 未安装")
    sys.exit(1)


class IndexSyncer:
    """索引同步器 - MessagePack → SQLite"""
    
    def __init__(self, log_dir: str, db_path: str):
        self.log_dir = log_dir
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建 TraceID 索引表（按小时分表）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trace_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT NOT NULL,
                service TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                file TEXT NOT NULL,
                block INTEGER NOT NULL,
                line INTEGER,
                timestamp TEXT,
                level TEXT,
                thread TEXT,
                length INTEGER,
                synced_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        
        # 创建索引（加速查询）
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trace_query 
            ON trace_index(hour, service, trace_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trace_id 
            ON trace_index(trace_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_hour 
            ON trace_index(hour)
        ''')
        
        # 创建 REQ_SN 映射表（仅 sft-aipg）
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
        
        # 创建同步元数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT NOT NULL UNIQUE,
                service TEXT NOT NULL,
                index_file TEXT NOT NULL,
                record_count INTEGER,
                synced_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'synced'
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print(f"✅ 数据库初始化完成：{self.db_path}")
    
    def sync_hour(self, service: str, hour: str) -> Tuple[bool, int]:
        """
        同步指定小时的索引到 SQLite
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
        
        Returns:
            (success, record_count)
        """
        print(f"\n同步索引：{service} {hour}")
        
        # 检查是否已同步
        if self._is_synced(service, hour):
            print(f"  ✓ 已同步，跳过")
            return True, 0
        
        # 加载 TraceID 索引
        trace_index_file = os.path.join(
            self.log_dir, service,
            f'{service}_{hour}.log.trace_index.msgpack'
        )
        
        if not os.path.exists(trace_index_file):
            print(f"  ⚠️ TraceID 索引文件不存在：{trace_index_file}")
            return False, 0
        
        # 加载 REQ_SN 索引（仅 sft-aipg）
        reqsn_index_file = None
        if service == 'sft-aipg':
            reqsn_index_file = os.path.join(
                self.log_dir, service,
                f'{service}_{hour}.log.reqsn_index.msgpack'
            )
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            total_records = 0
            
            # 1. 同步 TraceID 索引
            with open(trace_index_file, 'rb') as f:
                trace_data = msgpack.unpack(f)
            
            trace_index = trace_data.get('trace_index', {})
            
            # 批量插入
            batch = []
            batch_size = 1000
            
            for trace_id, entries in trace_index.items():
                for entry in entries:
                    batch.append((
                        hour,
                        service,
                        trace_id,
                        entry.get('file', ''),
                        entry.get('block', 0),
                        entry.get('line', 0),
                        entry.get('timestamp', ''),
                        entry.get('level', ''),
                        entry.get('thread', ''),
                        entry.get('length', 0)
                    ))
                    
                    total_records += 1
                    
                    if len(batch) >= batch_size:
                        self._insert_batch(cursor, batch)
                        batch = []
            
            # 插入剩余数据
            if batch:
                self._insert_batch(cursor, batch)
            
            print(f"  ✓ TraceID 索引：{total_records} 条记录")
            
            # 2. 同步 REQ_SN 映射（仅 sft-aipg）
            reqsn_count = 0
            if reqsn_index_file and os.path.exists(reqsn_index_file):
                with open(reqsn_index_file, 'rb') as f:
                    reqsn_data = msgpack.unpack(f)
                
                reqsn_to_trace = reqsn_data.get('req_sn_to_trace', {})
                
                for req_sn, trace_id in reqsn_to_trace.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO reqsn_mapping 
                        (hour, service, req_sn, trace_id)
                        VALUES (?, ?, ?, ?)
                    ''', (hour, service, req_sn, trace_id))
                    
                    reqsn_count += 1
                
                print(f"  ✓ REQ_SN 映射：{reqsn_count} 条记录")
            
            # 3. 记录同步元数据
            cursor.execute('''
                INSERT OR REPLACE INTO sync_meta 
                (hour, service, index_file, record_count, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (hour, service, trace_index_file, total_records, 'synced'))
            
            conn.commit()
            conn.close()
            
            print(f"  ✓ 同步完成：{total_records + reqsn_count} 条记录")
            
            return True, total_records + reqsn_count
            
        except Exception as e:
            print(f"  ✗ 同步失败：{e}")
            import traceback
            traceback.print_exc()
            return False, 0
    
    def _insert_batch(self, cursor, batch):
        """批量插入数据"""
        cursor.executemany('''
            INSERT INTO trace_index 
            (hour, service, trace_id, file, block, line, timestamp, level, thread, length)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
    
    def _is_synced(self, service: str, hour: str) -> bool:
        """检查是否已同步"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM sync_meta 
            WHERE hour = ? AND service = ? AND status = 'synced'
        ''', (hour, service))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def query_by_trace_id(self, service: str, hour: str, trace_id: str) -> List[Dict]:
        """
        通过 TraceID 查询日志位置
        
        Args:
            service: 服务名
            hour: 小时
            trace_id: TraceID
        
        Returns:
            日志位置列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file, block, line, timestamp, level, thread, length
            FROM trace_index
            WHERE hour = ? AND service = ? AND trace_id = ?
            ORDER BY timestamp
        ''', (hour, service, trace_id))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def query_by_req_sn(self, service: str, hour: str, req_sn: str) -> str:
        """
        通过 REQ_SN 查询 TraceID
        
        Args:
            service: 服务名
            hour: 小时
            req_sn: REQ_SN
        
        Returns:
            TraceID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT trace_id FROM reqsn_mapping
            WHERE hour = ? AND service = ? AND req_sn = ?
        ''', (hour, service, req_sn))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def cleanup_old_data(self, retention_days: int = 2):
        """清理指定天数前的数据"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_hour = cutoff_date.strftime('%Y%m%d%H')
        
        print(f"\n清理 {retention_days} 天前的数据 (截止时间：{cutoff_hour})")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 删除旧数据
        cursor.execute('''
            DELETE FROM trace_index WHERE hour < ?
        ''', (cutoff_hour,))
        trace_deleted = cursor.rowcount
        
        cursor.execute('''
            DELETE FROM reqsn_mapping WHERE hour < ?
        ''', (cutoff_hour,))
        reqsn_deleted = cursor.rowcount
        
        cursor.execute('''
            DELETE FROM sync_meta WHERE hour < ?
        ''', (cutoff_hour,))
        meta_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"  删除 TraceID 记录：{trace_deleted} 条")
        print(f"  删除 REQ_SN 记录：{reqsn_deleted} 条")
        print(f"  删除元数据：{meta_deleted} 条")
    
    def get_db_size(self) -> int:
        """获取数据库文件大小"""
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path)
        return 0


def main():
    parser = argparse.ArgumentParser(description='索引同步工具 - MessagePack → SQLite')
    parser.add_argument('--log-dir', '-d', default='/root/sft/testlogs',
                       help='日志根目录')
    parser.add_argument('--db-path', '-db', default='/root/sft/sftlogapi-v2/data/index/logs_trace.db',
                       help='SQLite 数据库路径')
    parser.add_argument('--service', '-s', help='服务名')
    parser.add_argument('--hour', '-t', help='小时 (YYYYMMDDHH)')
    parser.add_argument('--cleanup', '-c', action='store_true',
                       help='清理模式')
    parser.add_argument('--retention-days', default=2, type=int,
                       help='数据保留天数（默认：2 天）')
    parser.add_argument('--all-services', action='store_true',
                       help='处理所有服务')
    
    args = parser.parse_args()
    
    syncer = IndexSyncer(args.log_dir, args.db_path)
    
    if args.cleanup:
        syncer.cleanup_old_data(args.retention_days)
    
    elif args.hour:
        if args.all_services:
            # 处理所有服务
            services = [d for d in os.listdir(args.log_dir) 
                       if os.path.isdir(os.path.join(args.log_dir, d))]
            
            for service in services:
                syncer.sync_hour(service, args.hour)
        else:
            # 单个服务
            services = [args.service] if args.service else ['sft-aipg']
            
            for service in services:
                syncer.sync_hour(service, args.hour)
    
    else:
        parser.print_help()
        sys.exit(1)
    
    # 打印统计
    print(f"\n{'='*60}")
    print(f"数据库大小：{syncer.get_db_size() / 1024 / 1024:.1f}MB")


if __name__ == '__main__':
    main()
