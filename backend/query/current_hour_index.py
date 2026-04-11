#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
当前小时索引生成器

用于处理未压缩的当前小时日志：
1. 流式读取 .log 文件
2. 构建内存索引（不保存文件）
3. 提供查询接口
4. 自动过期清理

内存占用估算：
- 单小时日志：50MB (.log)
- 索引数据：约 50-60MB
- 缓存 3 小时：~180MB（安全范围）
"""

import os
import re
import time
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import threading


class CurrentHourIndex:
    """当前小时索引（内存）"""
    
    def __init__(self, service: str, hour: str):
        self.service = service
        self.hour = hour
        self.req_sn_to_trace: Dict[str, str] = {}
        self.trace_index: Dict[str, List[Dict]] = {}
        self.built_at = time.time()
        self.access_count = 0
    
    def add_entry(self, req_sn: Optional[str], trace_id: str, 
                  file: str, block: int, timestamp: str, level: str):
        """添加一条索引记录"""
        # REQ_SN → TraceID 映射（仅 sft-aipg）
        if req_sn and self.service == 'sft-aipg':
            self.req_sn_to_trace[req_sn] = trace_id
        
        # TraceID → 日志位置
        if trace_id not in self.trace_index:
            self.trace_index[trace_id] = []
        
        self.trace_index[trace_id].append({
            'file': file,
            'block': block,
            'timestamp': timestamp,
            'level': level
        })
    
    def get_trace_id(self, req_sn: str) -> Optional[str]:
        """通过 REQ_SN 查询 TraceID"""
        self.access_count += 1
        return self.req_sn_to_trace.get(req_sn)
    
    def get_entries(self, trace_id: str) -> List[Dict]:
        """通过 TraceID 查询日志位置"""
        self.access_count += 1
        return self.trace_index.get(trace_id, [])
    
    def is_expired(self, timeout_minutes: int = 120) -> bool:
        """检查是否过期（默认 2 小时）"""
        return (time.time() - self.built_at) > (timeout_minutes * 60)


class CurrentHourIndexManager:
    """当前小时索引管理器（LRU 缓存）"""
    
    def __init__(self, log_base_dir: str, max_hours: int = 3):
        self.log_base_dir = log_base_dir
        self.max_hours = max_hours
        self.cache: Dict[str, CurrentHourIndex] = {}  # key: service:hour
        self.lock = threading.Lock()
    
    def get_or_build(self, service: str, hour: str) -> Optional[CurrentHourIndex]:
        """
        获取或构建索引
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
        
        Returns:
            索引对象，失败返回 None
        """
        key = f"{service}:{hour}"
        
        with self.lock:
            # 检查缓存
            if key in self.cache:
                index = self.cache[key]
                
                # 检查是否过期
                if not index.is_expired():
                    return index
                else:
                    # 过期，删除
                    del self.cache[key]
            
            # 构建新索引
            index = self._build_index(service, hour)
            
            if index:
                # 添加到缓存
                self.cache[key] = index
                
                # 清理过期缓存
                self._cleanup()
                
                return index
            
            return None
    
    def _build_index(self, service: str, hour: str) -> Optional[CurrentHourIndex]:
        """构建当前小时索引"""
        service_dir = os.path.join(self.log_base_dir, service)
        
        if not os.path.exists(service_dir):
            print(f"[DEBUG] 服务目录不存在：{service_dir}")
            return None
        
        # 查找当前小时的 .log 文件（未压缩）
        log_files = []
        for filename in os.listdir(service_dir):
            if hour not in filename:
                continue
            if filename.endswith('.log') and not filename.endswith('.log.gz'):
                log_files.append(os.path.join(service_dir, filename))
        
        if not log_files:
            print(f"[DEBUG] 未找到当前小时日志：{service} {hour}")
            return None
        
        print(f"[DEBUG] 构建当前小时索引：{service} {hour} ({len(log_files)} 个文件)")
        
        start_time = time.time()
        index = CurrentHourIndex(service, hour)
        
        total_blocks = 0
        
        # 流式处理每个日志文件
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    block_num = 0
                    current_lines = []
                    
                    for line in f:
                        # 检查是否为新日志块开头
                        if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
                            # 处理上一个块
                            if current_lines:
                                self._process_block(current_lines, block_num, log_file, index)
                                total_blocks += 1
                            
                            current_lines = [line]
                            block_num += 1
                        else:
                            current_lines.append(line)
                    
                    # 处理最后一个块
                    if current_lines:
                        self._process_block(current_lines, block_num, log_file, index)
                        total_blocks += 1
                
                print(f"[DEBUG] 处理文件：{os.path.basename(log_file)} ({total_blocks} 条)")
                
            except Exception as e:
                print(f"[ERROR] 处理文件失败 {log_file}: {e}")
                continue
        
        build_time = (time.time() - start_time) * 1000
        
        print(f"[DEBUG] 索引构建完成:")
        print(f"  总日志块：{total_blocks}")
        print(f"  TraceID 数：{len(index.trace_index)}")
        print(f"  REQ_SN 数：{len(index.req_sn_to_trace)}")
        print(f"  耗时：{build_time:.0f}ms")
        
        return index
    
    def _process_block(self, lines: List[str], block_num: int, file: str, index: CurrentHourIndex):
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
        
        # 提取 REQ_SN
        content = ''.join(lines)
        req_sn = self._extract_req_sn(content)
        
        # 添加到索引
        index.add_entry(
            req_sn=req_sn,
            trace_id=trace_id,
            file=os.path.basename(file),
            block=block_num,
            timestamp=timestamp,
            level=level
        )
    
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
    
    def _cleanup(self):
        """清理过期缓存"""
        expired_keys = [
            key for key, index in self.cache.items()
            if index.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        # 如果超出最大缓存数，删除最旧的
        while len(self.cache) > self.max_hours:
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k].built_at)
            del self.cache[oldest_key]
    
    def clear(self):
        """清空所有缓存"""
        with self.lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return {
                'cache_size': len(self.cache),
                'max_hours': self.max_hours,
                'items': [
                    {
                        'key': key,
                        'trace_ids': len(index.trace_index),
                        'req_sn': len(index.req_sn_to_trace),
                        'access_count': index.access_count,
                        'age_minutes': (time.time() - index.built_at) / 60
                    }
                    for key, index in self.cache.items()
                ]
            }


# 全局管理器实例
_current_hour_manager = None

def get_current_hour_manager(log_base_dir: str = '/root/sft/testlogs') -> CurrentHourIndexManager:
    """获取全局管理器实例"""
    global _current_hour_manager
    if _current_hour_manager is None or _current_hour_manager.log_base_dir != log_base_dir:
        _current_hour_manager = CurrentHourIndexManager(log_base_dir)
    return _current_hour_manager
