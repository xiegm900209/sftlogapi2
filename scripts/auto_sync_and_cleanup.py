#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动同步 + 清理脚本

功能：
1. 同步 1 小时前的小时索引到 SQLite
2. 清理 7 天前的 SQLite 数据
3. 清理 7 天前的 MessagePack 索引文件
4. VACUUM 数据库释放空间

使用方法：
    # 自动模式（推荐，定时任务每小时执行）
    python3 auto_sync_and_cleanup.py --auto
    
    # 手动同步指定小时
    python3 auto_sync_and_cleanup.py --hour 2026041314 --service sft-aipg
    
    # 仅清理
    python3 auto_sync_and_cleanup.py --cleanup --retention-days 7
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime, timedelta
from typing import Tuple

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from indexer.sqlite_sync import SQLiteSyncer


class AutoSyncAndCleanup:
    """自动同步 + 清理管理器"""
    
    def __init__(self, log_dir: str, db_path: str):
        self.log_dir = log_dir
        self.db_path = db_path
        self.syncer = SQLiteSyncer(db_path)
    
    def sync_hour(self, service: str, hour: str) -> Tuple[bool, int]:
        """同步指定小时到 SQLite"""
        return self.syncer.sync_index_file(
            os.path.join(self.log_dir, service, f'{service}_{hour}.log.trace_index.msgpack')
        )
    
    def cleanup_sqlite(self, retention_days: int = 7) -> int:
        """
        清理 SQLite 中 7 天前的数据
        
        Returns:
            删除的记录数
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_hour = cutoff_date.strftime('%Y%m%d%H')
        
        print(f"\n清理 SQLite 数据 (保留 {retention_days} 天，截止：{cutoff_hour})")
        
        if not os.path.exists(self.db_path):
            print("  数据库不存在，跳过")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        total_deleted = 0
        
        # 1. 删除 trace_index 表旧数据
        try:
            cursor.execute('DELETE FROM trace_index WHERE hour < ?', (cutoff_hour,))
            deleted = cursor.rowcount
            total_deleted += deleted
            print(f"  删除 trace_index: {deleted} 条")
        except sqlite3.OperationalError:
            print("  trace_index 表不存在，跳过")
        
        # 2. 删除 reqsn_mapping 表旧数据
        try:
            cursor.execute('DELETE FROM reqsn_mapping WHERE hour < ?', (cutoff_hour,))
            deleted = cursor.rowcount
            total_deleted += deleted
            print(f"  删除 reqsn_mapping: {deleted} 条")
        except sqlite3.OperationalError:
            print("  reqsn_mapping 表不存在，跳过")
        
        # 3. 删除 sync_meta 表旧数据
        try:
            cursor.execute('DELETE FROM sync_meta WHERE hour < ?', (cutoff_hour,))
            deleted = cursor.rowcount
            total_deleted += deleted
            print(f"  删除 sync_meta: {deleted} 条")
        except sqlite3.OperationalError:
            print("  sync_meta 表不存在，跳过")
        
        # 4. 删除 stats 表旧数据
        try:
            cursor.execute('DELETE FROM stats WHERE stat_hour < ?', (cutoff_hour,))
            deleted = cursor.rowcount
            total_deleted += deleted
            print(f"  删除 stats: {deleted} 条")
        except sqlite3.OperationalError:
            print("  stats 表不存在，跳过")
        
        # 5. 删除旧的小时表 (logs_YYYYMMDDHH)
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'logs_%'
        ''')
        
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            # 从表名提取小时
            hour_str = table.replace('logs_', '')
            if len(hour_str) == 10 and hour_str < cutoff_hour:
                cursor.execute(f'DROP TABLE {table}')
                print(f"  删除表：{table}")
                total_deleted += 1
        
        conn.commit()
        
        # 6. VACUUM 释放空间
        print("  执行 VACUUM 释放空间...")
        cursor.execute('VACUUM')
        
        conn.close()
        
        # 7. 计算数据库大小
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        print(f"\n  数据库大小：{db_size / 1024 / 1024:.1f}MB")
        
        return total_deleted
    
    def cleanup_msgpack(self, retention_days: int = 7) -> int:
        """清理 7 天前的 MessagePack 索引文件"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_hour = cutoff_date.strftime('%Y%m%d%H')
        
        print(f"\n清理 MessagePack 索引文件 (保留 {retention_days} 天，截止：{cutoff_hour})")
        
        import re
        deleted_count = 0
        
        for service_dir in os.listdir(self.log_dir):
            service_path = os.path.join(self.log_dir, service_dir)
            
            if not os.path.isdir(service_path):
                continue
            
            for filename in os.listdir(service_path):
                # 只处理索引文件
                if not (filename.endswith('.reqsn_index.msgpack') or 
                       filename.endswith('.trace_index.msgpack')):
                    continue
                
                # 从文件名提取小时
                match = re.search(r'(\d{10})', filename)
                if not match:
                    continue
                
                file_hour = match.group(1)
                
                # 判断是否超过保留期限
                if file_hour < cutoff_hour:
                    file_path = os.path.join(service_path, filename)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        print(f"  删除：{service_path}/{filename}")
                    except Exception as e:
                        print(f"  删除失败 {file_path}: {e}")
        
        print(f"\n  删除索引文件：{deleted_count} 个")
        return deleted_count
    
    def auto_sync(self):
        """自动同步 1 小时前的小时"""
        target_time = datetime.now() - timedelta(hours=1)
        target_hour = target_time.strftime('%Y%m%d%H')
        
        print(f"\n自动同步：{target_hour} 小时")
        
        # 获取所有服务
        services = [d for d in os.listdir(self.log_dir) 
                   if os.path.isdir(os.path.join(self.log_dir, d))]
        
        total_records = 0
        
        for service in services:
            index_file = os.path.join(
                self.log_dir, service,
                f'{service}_{target_hour}.log.trace_index.msgpack'
            )
            
            if os.path.exists(index_file):
                success, records = self.sync_hour(service, target_hour)
                if success:
                    total_records += records
                    print(f"  ✓ {service}: {records} 条记录")
            else:
                print(f"  ⚠ {service}: 索引文件不存在")
        
        print(f"\n同步完成：{total_records} 条记录")
        return total_records


def main():
    parser = argparse.ArgumentParser(description='自动同步 + 清理脚本')
    parser.add_argument('--log-dir', '-d', default='/data/logs',
                       help='日志根目录（容器内路径）')
    parser.add_argument('--db-path', '-db', default='/data/index/logs_index.db',
                       help='SQLite 数据库路径')
    parser.add_argument('--auto', '-a', action='store_true',
                       help='自动模式：同步 1 小时前的小时 + 清理')
    parser.add_argument('--hour', '-t', help='手动同步指定小时')
    parser.add_argument('--service', '-s', help='服务名')
    parser.add_argument('--cleanup', '-c', action='store_true',
                       help='仅清理模式')
    parser.add_argument('--retention-days', default=7, type=int,
                       help='保留天数（默认 7 天）')
    
    args = parser.parse_args()
    
    manager = AutoSyncAndCleanup(args.log_dir, args.db_path)
    
    if args.auto:
        # 自动模式：同步 + 清理
        manager.auto_sync()
        manager.cleanup_sqlite(args.retention_days)
        manager.cleanup_msgpack(args.retention_days)
    
    elif args.cleanup:
        # 仅清理
        manager.cleanup_sqlite(args.retention_days)
        manager.cleanup_msgpack(args.retention_days)
    
    elif args.hour:
        # 手动同步指定小时
        if not args.service:
            print("错误：--hour 需要指定 --service")
            sys.exit(1)
        
        manager.sync_hour(args.service, args.hour)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
