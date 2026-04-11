#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 索引同步器
将 MessagePack 索引文件增量同步到 SQLite 数据库
"""

import os
import sys
import sqlite3
import msgpack
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class SQLiteSyncer:
    """SQLite 索引同步器"""
    
    def __init__(self, db_path: str = '/root/sft/sftlogapi-v2/data/index/logs_index.db'):
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """确保数据库和表存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 读取 schema
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                cursor.executescript(f.read())
        
        conn.commit()
        conn.close()
    
    def _get_table_name(self, log_hour: str) -> str:
        """获取小时表名"""
        return f'logs_{log_hour}'
    
    def _create_hour_table(self, cursor, log_hour: str):
        """创建小时表（如果不存在）"""
        table_name = self._get_table_name(log_hour)
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                req_sn TEXT,
                service TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT,
                thread TEXT,
                log_file TEXT NOT NULL,
                block_num INTEGER,
                content_length INTEGER,
                indexed_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        
        # 创建索引
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_trace_{log_hour} ON {table_name}(trace_id)')
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_req_sn_{log_hour} ON {table_name}(req_sn)')
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_ts_{log_hour} ON {table_name}(timestamp)')
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_service_{log_hour} ON {table_name}(service)')
    
    def sync_index_file(self, index_file: str) -> Tuple[bool, int]:
        """
        同步单个索引文件到 SQLite
        
        Returns:
            (success, record_count)
        """
        print(f"同步索引文件：{index_file}")
        
        try:
            # 加载索引 (支持 msgpack 和 JSON)
            if index_file.endswith('.msgpack'):
                with open(index_file, 'rb') as f:
                    index_data = msgpack.unpack(f, raw=False)
            else:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            
            # 提取元数据
            meta = index_data.get('meta', {})
            stats = meta.get('stats', {})
            
            # 从文件名提取小时和服务
            # 格式：xxx_2026040809.log.index.msgpack 或 index_2026040809.msgpack
            filename = os.path.basename(index_file)
            log_hour = self._extract_hour_from_filename(filename)
            
            if not log_hour:
                print(f"  ⚠️ 无法从文件名提取小时：{filename}")
                return False, 0
            
            # 从文件路径提取服务名（更可靠）
            # 路径格式：/root/sft/testlogs/{service}/{filename}
            service = self._extract_service_from_path(index_file)
            if not service:
                service = self._extract_service_from_filename(filename)
            if not service:
                # 从索引数据中推断
                trace_id_index = index_data.get('trace_id_index', {})
                if trace_id_index:
                    first_entries = next(iter(trace_id_index.values()), [])
                    if first_entries:
                        # 从 file 路径提取 service
                        file_path = first_entries[0].get('file', '')
                        service = self._extract_service_from_path(file_path)
                        if not service:
                            service = first_entries[0].get('service', 'unknown')
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建小时表
            self._create_hour_table(cursor, log_hour)
            table_name = self._get_table_name(log_hour)
            
            # 检查是否已同步
            cursor.execute(
                'SELECT COUNT(*) FROM sync_meta WHERE index_file = ?',
                (index_file,)
            )
            if cursor.fetchone()[0] > 0:
                print(f"  ✓ 已同步，跳过")
                conn.close()
                return True, 0
            
            # 插入索引数据
            trace_id_index = index_data.get('trace_id_index', {})
            total_records = 0
            
            # 批量插入 (每 1000 条提交一次)
            batch_size = 1000
            batch = []
            
            for trace_id, entries in trace_id_index.items():
                for entry in entries:
                    # 兼容新旧格式
                    if isinstance(entry, str):
                        # 旧格式：只是文件路径
                        file_path = entry
                        block_num = 0
                        timestamp = ''
                        level = ''
                        thread = ''
                        length = 0
                    elif isinstance(entry, dict):
                        # 新格式：包含详细信息
                        file_path = entry.get('file', '')
                        block_num = entry.get('block_num', 0)
                        timestamp = entry.get('timestamp', '')
                        level = entry.get('level', '')
                        thread = entry.get('thread', '')
                        length = entry.get('length', 0)
                    else:
                        continue
                    
                    batch.append((
                        trace_id,
                        None,  # req_sn
                        service,
                        timestamp,
                        level,
                        thread,
                        file_path,
                        block_num,
                        length
                    ))
                    
                    total_records += 1
                    
                    if len(batch) >= batch_size:
                        cursor.executemany(f'''
                            INSERT INTO {table_name} 
                            (trace_id, req_sn, service, timestamp, level, thread, log_file, block_num, content_length)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', batch)
                        batch = []
            
            # 插入剩余数据
            if batch:
                cursor.executemany(f'''
                    INSERT INTO {table_name} 
                    (trace_id, req_sn, service, timestamp, level, thread, log_file, block_num, content_length)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch)
            
            # 记录同步元数据
            cursor.execute('''
                INSERT OR REPLACE INTO sync_meta 
                (log_file, index_file, log_hour, service, synced_at, log_size, index_size, record_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                '',  # log_file (压缩文件路径，从索引中获取)
                index_file,
                log_hour,
                service,
                datetime.now().isoformat(),
                0,  # log_size
                os.path.getsize(index_file),
                total_records,
                'synced'
            ))
            
            # 更新统计
            cursor.execute('''
                INSERT OR REPLACE INTO stats 
                (stat_date, stat_hour, service, total_records, total_trace_ids, total_req_sn)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                log_hour[:8],  # YYYYMMDD
                log_hour,
                service,
                total_records,
                len(trace_id_index),
                len(index_data.get('req_sn_index', {}))
            ))
            
            conn.commit()
            conn.close()
            
            print(f"  ✓ 同步完成：{total_records} 条记录")
            return True, total_records
            
        except Exception as e:
            print(f"  ✗ 同步失败：{e}")
            import traceback
            traceback.print_exc()
            return False, 0
    
    def sync_directory(self, index_dir: str) -> Tuple[int, int]:
        """
        同步目录下所有索引文件
        
        Returns:
            (success_count, total_records)
        """
        print(f"\n同步目录：{index_dir}")
        
        success_count = 0
        total_records = 0
        
        for filename in os.listdir(index_dir):
            if not (filename.endswith('.msgpack') or filename.endswith('.index.json')):
                continue
            
            index_file = os.path.join(index_dir, filename)
            success, records = self.sync_index_file(index_file)
            
            if success:
                success_count += 1
                total_records += records
        
        print(f"\n同步完成：{success_count} 个文件，{total_records} 条记录")
        return success_count, total_records
    
    def _extract_hour_from_filename(self, filename: str) -> Optional[str]:
        """从文件名提取小时 (YYYYMMDDHH)"""
        import re
        match = re.search(r'(\d{10})', filename)
        if match:
            return match.group(1)
        return None
    
    def _extract_service_from_path(self, file_path: str) -> Optional[str]:
        """从文件路径提取服务名"""
        # 路径格式：/root/sft/testlogs/{service}/{filename}
        # 或：/data/logs/{service}/{filename}
        parts = file_path.strip('/').split('/')
        # 找到 testlogs 或 logs 后面的部分
        for i, part in enumerate(parts):
            if part in ['testlogs', 'logs'] and i + 1 < len(parts):
                return parts[i + 1]
        return None
    
    def _extract_service_from_filename(self, filename: str) -> Optional[str]:
        """从文件名提取服务名"""
        # 格式：sft-aipg-sft-aipg-59c947b9c9-cj6fm_zb_2026040809.log.index.msgpack
        parts = filename.split('_')
        if len(parts) >= 2:
            return parts[0]  # sft-aipg
        return None
    
    def query_by_trace_id(self, trace_id: str, log_hour: str = None) -> List[Dict]:
        """通过 TraceID 查询"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if log_hour:
            table_name = self._get_table_name(log_hour)
            cursor.execute(f'SELECT * FROM {table_name} WHERE trace_id = ?', (trace_id,))
        else:
            # 查询所有小时表 (需要动态构建)
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'logs_%'
            ''')
            tables = [row[0] for row in cursor.fetchall()]
            
            results = []
            for table in tables:
                cursor.execute(f'SELECT * FROM {table} WHERE trace_id = ?', (trace_id,))
                results.extend(cursor.fetchall())
            
            conn.close()
            return [dict(row) for row in results]
        
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    def query_by_req_sn(self, req_sn: str, log_hour: str = None) -> List[Dict]:
        """通过 REQ_SN 查询"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if log_hour:
            table_name = self._get_table_name(log_hour)
            cursor.execute(f'SELECT * FROM {table_name} WHERE req_sn = ?', (req_sn,))
        else:
            # 查询所有小时表
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'logs_%'
            ''')
            tables = [row[0] for row in cursor.fetchall()]
            
            results = []
            for table in tables:
                cursor.execute(f'SELECT * FROM {table} WHERE req_sn = ?', (req_sn,))
                results.extend(cursor.fetchall())
            
            conn.close()
            return [dict(row) for row in results]
        
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    def get_stats(self, log_hour: str = None) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if log_hour:
            cursor.execute('SELECT * FROM stats WHERE stat_hour = ?', (log_hour,))
        else:
            cursor.execute('SELECT * FROM stats ORDER BY stat_hour DESC')
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]


def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SQLite 索引同步器')
    parser.add_argument('--index-dir', default='/root/sft/sftlogapi-v2/data/index', help='索引文件目录')
    parser.add_argument('--db-path', default='/root/sft/sftlogapi-v2/data/index/logs_index.db', help='数据库路径')
    parser.add_argument('--file', help='单个索引文件路径')
    
    args = parser.parse_args()
    
    syncer = SQLiteSyncer(args.db_path)
    
    if args.file:
        syncer.sync_index_file(args.file)
    else:
        syncer.sync_directory(args.index_dir)


if __name__ == '__main__':
    main()
