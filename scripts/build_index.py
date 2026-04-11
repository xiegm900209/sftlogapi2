#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志索引构建工具 v2
支持 JSON 和 MessagePack 两种格式

使用方法：
    python build_index.py /path/to/file.log.gz
    python build_index.py --service sft-aipg --hour 2026040809
    python build_index.py --rebuild-all
    python build_index.py /path/to/file.log.gz --format msgpack
"""

import os
import sys
import json
import argparse
import gzip
from datetime import datetime
from typing import Dict, List, Set, Optional, Any

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models.log_parser import read_log_blocks

# 尝试导入 msgpack
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    print("警告：msgpack 未安装，将使用 JSON 格式")


class LogIndexer:
    """日志索引构建器 v2"""
    
    def __init__(self, log_dir: str = '/root/sft/testlogs'):
        self.log_dir = log_dir
        self.trace_id_index: Dict[str, List[Dict]] = {}
        self.req_sn_index: Dict[str, List[Dict]] = {}
        self.stats = {
            'total_blocks': 0,
            'total_trace_ids': 0,
            'total_req_sn': 0,
            'files_processed': 0
        }
        
    def index_file(self, file_path: str) -> bool:
        """为单个文件构建索引"""
        print(f"索引文件：{file_path}")
        
        try:
            block_num = 0
            for log_block in read_log_blocks(file_path):
                self.stats['total_blocks'] += 1
                
                # 构建索引条目
                entry = {
                    'file': file_path,
                    'offset': 0,  # gzip 文件不支持直接 seek，暂设为 0
                    'length': len(log_block.content.encode('utf-8')),
                    'timestamp': log_block.timestamp,
                    'block_num': block_num,
                    'trace_id': log_block.trace_id,
                    'level': log_block.level,
                    'service': log_block.service
                }
                
                # 索引 TraceID
                if log_block.trace_id:
                    if log_block.trace_id not in self.trace_id_index:
                        self.trace_id_index[log_block.trace_id] = []
                    self.trace_id_index[log_block.trace_id].append(entry)
                
                # 索引 REQ_SN
                if isinstance(log_block.parsed_content, dict):
                    req_sn = log_block.parsed_content.get('req_sn')
                    if req_sn:
                        if req_sn not in self.req_sn_index:
                            self.req_sn_index[req_sn] = []
                        self.req_sn_index[req_sn].append(entry)
                        self.stats['total_req_sn'] += 1
                
                block_num += 1
            
            self.stats['files_processed'] += 1
            self.stats['total_trace_ids'] = len(self.trace_id_index)
            return True
            
        except Exception as e:
            print(f"索引失败 {file_path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False
    
    def save_index(self, index_file: str, format: str = 'json') -> bool:
        """保存索引到文件"""
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        
        index_data = {
            'trace_id_index': self.trace_id_index,
            'req_sn_index': self.req_sn_index,
            'meta': {
                'created_at': datetime.now().isoformat(),
                'format': format,
                'stats': self.stats
            }
        }
        
        try:
            if format == 'msgpack' and MSGPACK_AVAILABLE:
                # MessagePack 格式 (二进制)
                with open(index_file, 'wb') as f:
                    msgpack.pack(index_data, f, use_bin_type=True, default=str)
                file_size = os.path.getsize(index_file)
            else:
                # JSON 格式 (文本)
                if format == 'msgpack':
                    print("警告：msgpack 不可用，回退到 JSON 格式")
                with open(index_file, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, ensure_ascii=False, indent=2)
                file_size = os.path.getsize(index_file)
            
            print(f"索引已保存：{index_file}")
            print(f"  格式：{format}")
            print(f"  文件大小：{self._format_size(file_size)}")
            print(f"  TraceID 数量：{len(self.trace_id_index)}")
            print(f"  REQ_SN 数量：{len(self.req_sn_index)}")
            print(f"  总日志块数：{self.stats['total_blocks']}")
            return True
            
        except Exception as e:
            print(f"保存索引失败：{e}", file=sys.stderr)
            return False
    
    def load_index(self, index_file: str) -> bool:
        """加载索引文件"""
        if not os.path.exists(index_file):
            print(f"索引文件不存在：{index_file}")
            return False
        
        try:
            if index_file.endswith('.msgpack') and MSGPACK_AVAILABLE:
                with open(index_file, 'rb') as f:
                    index_data = msgpack.unpack(f, raw=False)
            else:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
            
            self.trace_id_index = index_data.get('trace_id_index', {})
            self.req_sn_index = index_data.get('req_sn_index', {})
            
            print(f"索引已加载：{index_file}")
            print(f"  TraceID 数量：{len(self.trace_id_index)}")
            print(f"  REQ_SN 数量：{len(self.req_sn_index)}")
            return True
            
        except Exception as e:
            print(f"加载索引失败：{e}", file=sys.stderr)
            return False
    
    def find_by_trace_id(self, trace_id: str) -> List[Dict]:
        """通过 TraceID 查找"""
        return self.trace_id_index.get(trace_id, [])
    
    def find_by_req_sn(self, req_sn: str) -> List[Dict]:
        """通过 REQ_SN 查找"""
        return self.req_sn_index.get(req_sn, [])
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


def build_index_for_file(log_file: str, output_index: str = None, format: str = 'json'):
    """为指定文件构建索引"""
    indexer = LogIndexer()
    indexer.index_file(log_file)
    
    if not output_index:
        ext = '.msgpack' if format == 'msgpack' else '.index.json'
        if log_file.endswith('.log.gz'):
            output_index = log_file.replace('.log.gz', '.log' + ext)
        elif log_file.endswith('.log'):
            output_index = log_file + ext
    
    indexer.save_index(output_index, format=format)
    return output_index


def build_index_for_service(service_dir: str, hour: str, format: str = 'json'):
    """为指定服务的小时日志构建索引"""
    indexer = LogIndexer()
    
    # 查找匹配小时的日志文件
    for filename in os.listdir(service_dir):
        if not (filename.endswith('.log') or filename.endswith('.log.gz')):
            continue
        
        # 检查文件名是否包含小时
        if hour not in filename:
            continue
        
        file_path = os.path.join(service_dir, filename)
        indexer.index_file(file_path)
    
    # 保存索引
    service_name = os.path.basename(service_dir)
    ext = '.msgpack' if format == 'msgpack' else '.index.json'
    index_file = os.path.join(os.path.dirname(service_dir), f'{service_name}_{hour}.log' + ext)
    
    indexer.save_index(index_file, format=format)
    return index_file


def rebuild_all_indexes(log_base_dir: str, format: str = 'json'):
    """重建所有服务的索引"""
    print(f"重建所有索引，日志目录：{log_base_dir}")
    
    master_indexer = LogIndexer(log_dir=log_base_dir)
    
    for service_dir in os.listdir(log_base_dir):
        service_path = os.path.join(log_base_dir, service_dir)
        if not os.path.isdir(service_path):
            continue
        
        print(f"\n处理服务：{service_dir}")
        
        for filename in os.listdir(service_path):
            if not (filename.endswith('.log') or filename.endswith('.log.gz')):
                continue
            
            file_path = os.path.join(service_path, filename)
            master_indexer.index_file(file_path)
    
    # 保存主索引
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = '.msgpack' if format == 'msgpack' else '.json'
    index_file = os.path.join(log_base_dir, f'index_{timestamp}{ext}')
    master_indexer.save_index(index_file, format=format)
    
    return index_file


def compare_formats(log_file: str):
    """对比 JSON 和 MessagePack 格式"""
    print(f"\n=== 格式对比测试：{log_file} ===\n")
    
    # 构建 JSON 索引
    print("1. 构建 JSON 索引...")
    json_file = log_file + '.test.index.json'
    indexer_json = LogIndexer()
    indexer_json.index_file(log_file)
    
    import time
    start = time.time()
    indexer_json.save_index(json_file, format='json')
    json_time = time.time() - start
    json_size = os.path.getsize(json_file)
    
    # 构建 MessagePack 索引
    print("\n2. 构建 MessagePack 索引...")
    msgpack_file = log_file + '.test.index.msgpack'
    indexer_msgpack = LogIndexer()
    indexer_msgpack.index_file(log_file)
    
    start = time.time()
    indexer_msgpack.save_index(msgpack_file, format='msgpack')
    msgpack_time = time.time() - start
    msgpack_size = os.path.getsize(msgpack_file)
    
    # 加载性能对比
    print("\n3. 加载性能对比...")
    start = time.time()
    with open(json_file, 'r') as f:
        json.load(f)
    json_load_time = time.time() - start
    
    start = time.time()
    with open(msgpack_file, 'rb') as f:
        msgpack.unpack(f)
    msgpack_load_time = time.time() - start
    
    # 输出对比结果
    print("\n=== 对比结果 ===")
    print(f"{'指标':<15} {'JSON':<15} {'MessagePack':<15} {'提升':<10}")
    print(f"{'文件大小':<15} {json_size/1024/1024:.2f}MB      {msgpack_size/1024/1024:.2f}MB       {100 - msgpack_size*100/json_size:.1f}%")
    print(f"{'保存时间':<15} {json_time:.3f}s        {msgpack_time:.3f}s        {json_time/msgpack_time:.2f}x")
    print(f"{'加载时间':<15} {json_load_time:.3f}s        {msgpack_load_time:.3f}s        {json_load_time/msgpack_load_time:.2f}x")
    
    # 清理测试文件
    os.remove(json_file)
    os.remove(msgpack_file)
    print("\n测试文件已清理")


def main():
    parser = argparse.ArgumentParser(description='日志索引构建工具 v2')
    parser.add_argument('file', nargs='?', help='要索引的日志文件路径')
    parser.add_argument('--service', '-s', help='服务名称')
    parser.add_argument('--hour', '-t', help='小时 (YYYYMMDDHH 格式)')
    parser.add_argument('--rebuild-all', action='store_true', help='重建所有索引')
    parser.add_argument('--log-dir', default='/root/sft/testlogs', help='日志根目录')
    parser.add_argument('--output', '-o', help='输出索引文件路径')
    parser.add_argument('--format', '-f', choices=['json', 'msgpack'], default='json', help='索引格式')
    parser.add_argument('--compare', action='store_true', help='对比 JSON 和 MessagePack 性能')
    
    args = parser.parse_args()
    
    if args.compare:
        if not args.file:
            print("错误：--compare 需要指定文件")
            sys.exit(1)
        if not MSGPACK_AVAILABLE:
            print("错误：msgpack 未安装，无法对比")
            sys.exit(1)
        compare_formats(args.file)
    
    elif args.file:
        # 为单个文件构建索引
        build_index_for_file(args.file, args.output, format=args.format)
    
    elif args.service and args.hour:
        # 为指定服务的小时构建索引
        service_dir = os.path.join(args.log_dir, args.service)
        if not os.path.exists(service_dir):
            print(f"服务目录不存在：{service_dir}", file=sys.stderr)
            sys.exit(1)
        
        build_index_for_service(service_dir, args.hour, format=args.format)
    
    elif args.rebuild_all:
        # 重建所有索引
        rebuild_all_indexes(args.log_dir, format=args.format)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
