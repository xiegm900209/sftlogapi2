#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志压缩 + 索引生成工具 v2

功能：
1. 压缩指定小时之前的日志文件
2. 生成两个索引文件：
   - {service}_{hour}.log.reqsn_index.msgpack (仅 sft-aipg)
   - {service}_{hour}.log.trace_index.msgpack (所有应用)
3. 清理 7 天前的索引文件（保留压缩日志）

使用方法：
    # 压缩并生成指定小时的索引
    python3 compress_and_index.py --log-dir /root/sft/testlogs --service sft-aipg --hour 2026040809
    
    # 压缩并生成所有服务指定小时的索引
    python3 compress_and_index.py --log-dir /root/sft/testlogs --hour 2026040809
    
    # 清理 7 天前的索引
    python3 compress_and_index.py --log-dir /root/sft/testlogs --cleanup --retention-days 7
    
    # 定时任务模式（压缩 1 小时前的小时）
    python3 compress_and_index.py --log-dir /root/sft/testlogs --auto
"""

import os
import sys
import gzip
import argparse
import re
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from pathlib import Path

# 尝试导入 msgpack
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    print("错误：msgpack 未安装，请先运行：pip install msgpack")
    sys.exit(1)


class LogCompressorIndexer:
    """日志压缩 + 索引生成器"""
    
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.stats = {
            'files_compressed': 0,
            'files_skipped': 0,
            'indexes_created': 0,
            'indexes_deleted': 0,
            'total_trace_ids': 0,
            'total_req_sn': 0,
            'total_blocks': 0
        }
    
    def compress_log_file(self, log_file: str) -> Optional[str]:
        """
        压缩单个日志文件
        
        Args:
            log_file: 日志文件路径 (.log)
        
        Returns:
            压缩后的文件路径 (.log.gz)，失败返回 None
        """
        if not log_file.endswith('.log'):
            print(f"跳过非 .log 文件：{log_file}")
            self.stats['files_skipped'] += 1
            return None
        
        gz_file = log_file + '.gz'
        
        if os.path.exists(gz_file):
            print(f"压缩文件已存在，跳过：{gz_file}")
            self.stats['files_skipped'] += 1
            return gz_file
        
        try:
            print(f"压缩文件：{log_file}")
            
            # 流式压缩，避免内存溢出（二进制模式，不关心编码）
            with open(log_file, 'rb') as f_in:
                with gzip.open(gz_file, 'wb', compresslevel=6) as f_out:
                    # 分块读取压缩
                    chunk_size = 1024 * 1024  # 1MB
                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
            
            # 验证压缩文件
            with gzip.open(gz_file, 'rt') as f:
                f.read(1024)  # 读取一小段验证
            
            print(f"  ✓ 压缩完成：{self._format_size(os.path.getsize(gz_file))}")
            self.stats['files_compressed'] += 1
            return gz_file
            
        except Exception as e:
            print(f"  ✗ 压缩失败：{e}")
            # 清理失败的压缩文件
            if os.path.exists(gz_file):
                os.remove(gz_file)
            return None
    
    def build_indexes(self, service: str, hour: str, log_file: str = None) -> bool:
        """
        为指定服务的小时构建索引
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
            log_file: 日志文件路径（可选，不指定则自动查找）
        
        Returns:
            是否成功
        """
        service_dir = os.path.join(self.log_dir, service)
        
        if not os.path.exists(service_dir):
            print(f"服务目录不存在：{service_dir}")
            return False
        
        # 查找日志文件
        if log_file:
            files = [log_file]
        else:
            # 自动查找匹配小时的日志文件（优先 .log，其次 .log.gz）
            files = []
            for filename in sorted(os.listdir(service_dir)):
                if hour not in filename:
                    continue
                if filename.endswith('.log') and not filename.endswith('.log.gz'):
                    files.insert(0, os.path.join(service_dir, filename))  # .log 优先
                elif filename.endswith('.log.gz'):
                    files.append(os.path.join(service_dir, filename))
        
        if not files:
            print(f"未找到 {service} {hour} 的日志文件")
            return False
        
        print(f"\n构建索引：{service} {hour}")
        print(f"  日志文件：{len(files)} 个")
        
        # 索引数据结构
        req_sn_to_trace = {}  # REQ_SN → TraceID (仅 sft-aipg)
        trace_index = {}      # TraceID → [日志位置列表]
        
        total_blocks = 0
        total_trace_ids = set()
        total_req_sn = set()
        
        # 处理每个日志文件
        for file_path in files:
            print(f"  处理文件：{os.path.basename(file_path)}")
            
            try:
                # 打开文件（支持 .log 和 .log.gz）
                if file_path.endswith('.gz'):
                    f = gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore')
                else:
                    f = open(file_path, 'r', encoding='utf-8', errors='ignore')
                
                block_num = 0
                current_lines = []
                
                for line in f:
                    # 检查是否为新日志块开头
                    if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
                        # 处理上一个块
                        if current_lines:
                            self._process_log_block(
                                current_lines, block_num, file_path,
                                req_sn_to_trace, trace_index,
                                total_trace_ids, total_req_sn,
                                service
                            )
                            total_blocks += 1
                        
                        current_lines = [line]
                        block_num += 1
                    else:
                        current_lines.append(line)
                
                # 处理最后一个块
                if current_lines:
                    self._process_log_block(
                        current_lines, block_num, file_path,
                        req_sn_to_trace, trace_index,
                        total_trace_ids, total_req_sn,
                        service
                    )
                    total_blocks += 1
                
                f.close()
                
            except Exception as e:
                print(f"    ✗ 处理失败：{e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 保存索引文件
        success = self._save_indexes(service, hour, req_sn_to_trace, trace_index)
        
        if success:
            print(f"\n  ✓ 索引构建完成")
            print(f"    总日志块：{total_blocks}")
            print(f"    TraceID 数量：{len(total_trace_ids)}")
            if service == 'sft-aipg':
                print(f"    REQ_SN 数量：{len(total_req_sn)}")
        
        self.stats['indexes_created'] += 1 if success else 0
        self.stats['total_blocks'] += total_blocks
        self.stats['total_trace_ids'] += len(total_trace_ids)
        self.stats['total_req_sn'] += len(total_req_sn)
        
        return success
    
    def _process_log_block(self, lines: List[str], block_num: int, file_path: str,
                          req_sn_to_trace: Dict, trace_index: Dict,
                          total_trace_ids: Set, total_req_sn: Set,
                          service: str):
        """处理单个日志块"""
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
        
        # 提取 REQ_SN（从内容中）
        content = ''.join(lines)
        req_sn = self._extract_req_sn(content)
        
        # 构建索引条目
        entry = {
            'file': os.path.basename(file_path),
            'line': block_num + 1,  # 从 1 开始
            'block': block_num,
            'timestamp': timestamp,
            'level': level,
            'thread': thread,
            'length': len(content.encode('utf-8'))
        }
        
        # 索引 TraceID（所有应用）
        if trace_id:
            if trace_id not in trace_index:
                trace_index[trace_id] = []
            trace_index[trace_id].append(entry)
            total_trace_ids.add(trace_id)
        
        # 索引 REQ_SN（仅 sft-aipg）
        if service == 'sft-aipg' and req_sn and trace_id:
            req_sn_to_trace[req_sn] = trace_id
            total_req_sn.add(req_sn)
    
    def _extract_req_sn(self, content: str) -> Optional[str]:
        """从日志内容中提取 REQ_SN"""
        # 尝试从 XML 中提取
        if '<?xml' in content and '</AIPG>' in content:
            match = re.search(r'<REQ_SN>([^<]+)</REQ_SN>', content)
            if match:
                return match.group(1)
        
        # 尝试从普通文本中提取
        match = re.search(r'REQ_SN[=:\s]+([A-Za-z0-9]+)', content)
        if match:
            return match.group(1)
        
        return None
    
    def _save_indexes(self, service: str, hour: str, 
                     req_sn_to_trace: Dict, trace_index: Dict) -> bool:
        """保存索引文件"""
        try:
            # 1. 保存 REQ_SN 索引（仅 sft-aipg）
            if service == 'sft-aipg' and req_sn_to_trace:
                reqsn_index_file = os.path.join(
                    self.log_dir, service,
                    f'{service}_{hour}.log.reqsn_index.msgpack'
                )
                
                reqsn_data = {
                    'meta': {
                        'service': service,
                        'hour': hour,
                        'created_at': datetime.now().isoformat(),
                        'total_req_sn': len(req_sn_to_trace)
                    },
                    'req_sn_to_trace': req_sn_to_trace
                }
                
                with open(reqsn_index_file, 'wb') as f:
                    msgpack.pack(reqsn_data, f, use_bin_type=True, default=str)
                
                print(f"    REQ_SN 索引：{self._format_size(os.path.getsize(reqsn_index_file))}")
            
            # 2. 保存 TraceID 索引（所有应用）
            trace_index_file = os.path.join(
                self.log_dir, service,
                f'{service}_{hour}.log.trace_index.msgpack'
            )
            
            trace_data = {
                'meta': {
                    'service': service,
                    'hour': hour,
                    'created_at': datetime.now().isoformat(),
                    'total_trace_ids': len(trace_index),
                    'total_blocks': sum(len(entries) for entries in trace_index.values())
                },
                'trace_index': trace_index
            }
            
            with open(trace_index_file, 'wb') as f:
                msgpack.pack(trace_data, f, use_bin_type=True, default=str)
            
            print(f"    TraceID 索引：{self._format_size(os.path.getsize(trace_index_file))}")
            
            return True
            
        except Exception as e:
            print(f"    ✗ 保存索引失败：{e}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup_old_indexes(self, retention_days: int = 7):
        """
        清理指定天数前的索引文件
        
        Args:
            retention_days: 保留天数（默认 7 天）
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_hour = cutoff_date.strftime('%Y%m%d%H')
        
        print(f"\n清理 {retention_days} 天前的索引文件 (截止时间：{cutoff_hour})")
        
        deleted_count = 0
        kept_count = 0
        
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
                        print(f"  删除：{service_dir}/{filename}")
                    except Exception as e:
                        print(f"  ✗ 删除失败 {service_dir}/{filename}: {e}")
                else:
                    kept_count += 1
        
        self.stats['indexes_deleted'] = deleted_count
        print(f"\n清理完成：删除 {deleted_count} 个索引文件，保留 {kept_count} 个")
    
    def compress_and_index_hour(self, hour: str, services: List[str] = None):
        """
        压缩并索引指定小时的所有日志
        
        Args:
            hour: 小时 (YYYYMMDDHH)
            services: 服务列表（None 表示所有服务）
        """
        print(f"\n{'='*60}")
        print(f"压缩并索引小时：{hour}")
        print(f"{'='*60}")
        
        # 获取服务列表
        if services is None:
            services = [d for d in os.listdir(self.log_dir) 
                       if os.path.isdir(os.path.join(self.log_dir, d))]
        
        for service in services:
            service_dir = os.path.join(self.log_dir, service)
            
            if not os.path.isdir(service_dir):
                continue
            
            # 查找该小时的 .log 文件（未压缩的）
            log_files = []
            for filename in os.listdir(service_dir):
                if hour not in filename:
                    continue
                if filename.endswith('.log') and not filename.endswith('.log.gz'):
                    log_files.append(os.path.join(service_dir, filename))
            
            if not log_files:
                print(f"\n{service}: 无未压缩日志，跳过")
                continue
            
            # 压缩日志
            for log_file in log_files:
                self.compress_log_file(log_file)
            
            # 构建索引（压缩后）
            self.build_indexes(service, hour)
    
    def auto_compress_and_index(self):
        """
        自动模式：压缩并索引 1 小时前的小时
        适用于定时任务（如每小时执行一次）
        """
        # 计算 1 小时前的小时
        target_time = datetime.now() - timedelta(hours=1)
        target_hour = target_time.strftime('%Y%m%d%H')
        
        print(f"自动模式：处理 {target_hour} 小时的日志")
        
        # 获取所有服务
        services = [d for d in os.listdir(self.log_dir) 
                   if os.path.isdir(os.path.join(self.log_dir, d))]
        
        self.compress_and_index_hour(target_hour, services)
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


def main():
    parser = argparse.ArgumentParser(description='日志压缩 + 索引生成工具 v2')
    parser.add_argument('--log-dir', '-d', default='/root/sft/testlogs',
                       help='日志根目录（默认：/root/sft/testlogs）')
    parser.add_argument('--service', '-s', help='服务名称（可选，不指定则处理所有）')
    parser.add_argument('--hour', '-t', help='小时 (YYYYMMDDHH 格式)')
    parser.add_argument('--file', '-f', help='单个日志文件路径')
    parser.add_argument('--auto', '-a', action='store_true',
                       help='自动模式：处理 1 小时前的小时（适用于定时任务）')
    parser.add_argument('--cleanup', '-c', action='store_true',
                       help='清理模式：删除指定天数前的索引文件')
    parser.add_argument('--retention-days', default=7, type=int,
                       help='索引保留天数（默认：7 天）')
    parser.add_argument('--all-services', action='store_true',
                       help='处理所有服务')
    parser.add_argument('--sync-sqlite', action='store_true',
                       help='同步到 SQLite 数据库')
    parser.add_argument('--db-path', default='/root/sft/sftlogapi-v2/data/index/logs_trace.db',
                       help='SQLite 数据库路径')
    
    args = parser.parse_args()
    
    # 验证日志目录
    if not os.path.exists(args.log_dir):
        print(f"错误：日志目录不存在：{args.log_dir}")
        sys.exit(1)
    
    indexer = LogCompressorIndexer(args.log_dir)
    
    if args.cleanup:
        # 清理模式
        indexer.cleanup_old_indexes(args.retention_days)
    
    elif args.auto:
        # 自动模式
        indexer.auto_compress_and_index()
    
    elif args.file:
        # 单个文件模式
        if not args.hour:
            print("错误：--file 需要指定 --hour")
            sys.exit(1)
        
        service = args.service or 'unknown'
        indexer.build_indexes(service, args.hour, args.file)
    
    elif args.hour:
        # 指定小时模式
        if args.all_services:
            # 处理所有服务
            services = [d for d in os.listdir(args.log_dir) 
                       if os.path.isdir(os.path.join(args.log_dir, d))]
            print(f"\n处理所有服务：{len(services)} 个")
        else:
            # 单个服务
            services = [args.service] if args.service else None
        
        indexer.compress_and_index_hour(args.hour, services)
        
        # 同步到 SQLite
        if args.sync_sqlite:
            print(f"\n同步到 SQLite 数据库...")
            from sync_index_to_sqlite import IndexSyncer
            syncer = IndexSyncer(args.log_dir, args.db_path)
            
            for service in (services or []):
                syncer.sync_hour(service, args.hour)
    
    else:
        parser.print_help()
        sys.exit(1)
    
    # 打印统计
    print(f"\n{'='*60}")
    print("统计信息:")
    print(f"  压缩文件：{indexer.stats['files_compressed']}")
    print(f"  跳过文件：{indexer.stats['files_skipped']}")
    print(f"  创建索引：{indexer.stats['indexes_created']}")
    print(f"  删除索引：{indexer.stats['indexes_deleted']}")
    print(f"  总日志块：{indexer.stats['total_blocks']}")
    print(f"  TraceID 数：{indexer.stats['total_trace_ids']}")
    print(f"  REQ_SN 数：{indexer.stats['total_req_sn']}")


if __name__ == '__main__':
    main()
