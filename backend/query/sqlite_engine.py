#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 查询引擎 v2
支持高性能日志查询
"""

import os
import sys
import sqlite3
import gzip
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.log_parser import read_log_blocks


class SQLiteQueryEngine:
    """SQLite 查询引擎"""
    
    def __init__(self, db_path: str = '/root/sft/sftlogapi-v2/data/index/logs_index.db',
                 log_base_dir: str = '/root/sft/testlogs'):
        self.db_path = db_path
        self.log_base_dir = log_base_dir
    
    def _get_table_name(self, log_hour: str) -> str:
        """获取小时表名"""
        return f'logs_{log_hour}'
    
    def _get_all_log_tables(self) -> List[str]:
        """获取所有日志表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'logs_%'
            ORDER BY name DESC
        ''')
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    
    def query_by_trace_id(self, trace_id: str, 
                          log_hour: str = None,
                          service: str = None,
                          limit: int = 1000) -> List[Dict]:
        """
        通过 TraceID 查询
        
        Args:
            trace_id: TraceID
            log_hour: 小时 (YYYYMMDDHH)，不指定则查询所有
            service: 服务名称过滤
            limit: 最大返回数量
        
        Returns:
            日志记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        
        if log_hour:
            # 查询指定小时
            tables = [self._get_table_name(log_hour)]
        else:
            # 查询所有小时表
            tables = self._get_all_log_tables()
        
        for table in tables:
            if service:
                cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE trace_id = ? AND service = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (trace_id, service, limit - len(results)))
            else:
                cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE trace_id = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (trace_id, limit - len(results)))
            
            rows = cursor.fetchall()
            results.extend([dict(row) for row in rows])
            
            if len(results) >= limit:
                break
        
        conn.close()
        return results[:limit]
    
    def query_by_req_sn(self, req_sn: str,
                        log_hour: str = None,
                        service: str = None,
                        limit: int = 1000) -> List[Dict]:
        """
        通过 REQ_SN 查询
        
        注意：当前实现中 req_sn 字段可能为空，需要优化
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        
        if log_hour:
            tables = [self._get_table_name(log_hour)]
        else:
            tables = self._get_all_log_tables()
        
        for table in tables:
            if service:
                cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE req_sn = ? AND service = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (req_sn, service, limit - len(results)))
            else:
                cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE req_sn = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (req_sn, limit - len(results)))
            
            rows = cursor.fetchall()
            results.extend([dict(row) for row in rows])
            
            if len(results) >= limit:
                break
        
        conn.close()
        return results[:limit]
    
    def query_by_time_range(self, start_hour: str, end_hour: str,
                            service: str = None,
                            trace_id: str = None,
                            limit: int = 1000) -> List[Dict]:
        """
        按时间范围查询
        
        Args:
            start_hour: 开始小时 (YYYYMMDDHH)
            end_hour: 结束小时 (YYYYMMDDHH)
            service: 服务过滤
            trace_id: TraceID 过滤
            limit: 最大返回数量
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取范围内的所有表
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'logs_%'
            AND name >= ? AND name <= ?
            ORDER BY name
        ''', (f'logs_{start_hour}', f'logs_{end_hour}'))
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        results = []
        
        for table in tables:
            temp_conn = sqlite3.connect(self.db_path)
            temp_conn.row_factory = sqlite3.Row
            temp_cursor = temp_conn.cursor()
            
            if service and trace_id:
                temp_cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE service = ? AND trace_id = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (service, trace_id, limit - len(results)))
            elif service:
                temp_cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE service = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (service, limit - len(results)))
            elif trace_id:
                temp_cursor.execute(f'''
                    SELECT * FROM {table} 
                    WHERE trace_id = ?
                    ORDER BY timestamp
                    LIMIT ?
                ''', (trace_id, limit - len(results)))
            
            rows = temp_cursor.fetchall()
            results.extend([dict(row) for row in rows])
            temp_conn.close()
            
            if len(results) >= limit:
                break
        
        return results[:limit]
    
    def get_services(self) -> List[str]:
        """获取所有服务列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT service FROM stats ORDER BY service')
        services = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return services
    
    def get_hours(self, service: str = None) -> List[str]:
        """获取所有有数据的小时"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if service:
            cursor.execute('SELECT DISTINCT stat_hour FROM stats WHERE service = ? ORDER BY stat_hour DESC', (service,))
        else:
            cursor.execute('SELECT DISTINCT stat_hour FROM stats ORDER BY stat_hour DESC')
        
        hours = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return hours
    
    def get_stats(self, log_hour: str = None, service: str = None) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM stats WHERE 1=1'
        params = []
        
        if log_hour:
            query += ' AND stat_hour = ?'
            params.append(log_hour)
        
        if service:
            query += ' AND service = ?'
            params.append(service)
        
        query += ' ORDER BY stat_hour DESC'
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def read_full_log_content(self, log_file: str, block_num: int = None) -> Optional[str]:
        """
        从原始日志文件读取完整内容
        
        Args:
            log_file: 日志文件路径 (.gz 或 .log)
            block_num: 日志块编号 (如果提供，只读取该块)
        
        Returns:
            日志内容
        """
        if not os.path.exists(log_file):
            return None
        
        try:
            if log_file.endswith('.gz'):
                with gzip.open(log_file, 'rt', encoding='utf-8', errors='ignore') as f:
                    if block_num is not None:
                        # 读取指定块
                        for i, block in enumerate(self._iter_log_blocks(f)):
                            if i == block_num:
                                return block
                    else:
                        return f.read()
            else:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    if block_num is not None:
                        for i, block in enumerate(self._iter_log_blocks(f)):
                            if i == block_num:
                                return block
                    else:
                        return f.read()
        except Exception as e:
            print(f"读取日志文件失败 {log_file}: {e}")
            return None
    
    def _iter_log_blocks(self, file_handle):
        """迭代日志块"""
        import re
        current_block = []
        
        for line in file_handle:
            if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
                if current_block:
                    yield ''.join(current_block)
                current_block = [line]
            else:
                current_block.append(line)
        
        if current_block:
            yield ''.join(current_block)


# 全局查询引擎实例
_query_engine = None

def get_query_engine() -> SQLiteQueryEngine:
    """获取全局查询引擎实例"""
    global _query_engine
    if _query_engine is None:
        _query_engine = SQLiteQueryEngine()
    return _query_engine
