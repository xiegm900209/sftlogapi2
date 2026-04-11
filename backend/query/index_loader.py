#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
索引文件加载器 v2

负责加载和查询 MessagePack 格式的索引文件：
- REQ_SN 索引（仅 sft-aipg）：{service}_{hour}.log.reqsn_index.msgpack
- TraceID 索引（所有应用）：{service}_{hour}.log.trace_index.msgpack
"""

import os
import sys
from typing import Dict, List, Optional, Set, Any
from functools import lru_cache
import threading

# 尝试导入 msgpack
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    print("警告：msgpack 未安装，索引查询将不可用")


class IndexLoader:
    """索引文件加载器（带 LRU 缓存）"""
    
    def __init__(self, log_base_dir: str, cache_size: int = 3):
        self.log_base_dir = log_base_dir
        self.cache_size = cache_size  # 缓存最近 N 个小时的索引
        self._lock = threading.Lock()
        self._trace_cache = {}  # {service: {hour: data}}
        self._reqsn_cache = {}  # {service: {hour: data}}
        self._cache_order = []  # LRU 顺序
    
    def _add_to_cache(self, cache: dict, service: str, hour: str, data: dict):
        """添加到缓存（LRU）"""
        if service not in cache:
            cache[service] = {}
        
        # 如果已存在，先移除
        if hour in cache[service]:
            self._cache_order.remove((service, hour))
        
        # 添加到缓存
        cache[service][hour] = data
        self._cache_order.append((service, hour))
        
        # 如果超出缓存大小，移除最旧的
        while len(self._cache_order) > self.cache_size:
            old_service, old_hour = self._cache_order.pop(0)
            if old_hour in cache.get(old_service, {}):
                del cache[old_service][old_hour]
    
    def _get_from_cache(self, cache: dict, service: str, hour: str) -> Optional[dict]:
        """从缓存获取（更新 LRU 顺序）"""
        if service not in cache:
            return None
        
        data = cache[service].get(hour)
        
        if data:
            # 更新 LRU 顺序
            key = (service, hour)
            if key in self._cache_order:
                self._cache_order.remove(key)
                self._cache_order.append(key)
        
        return data
    
    def get_reqsn_to_trace(self, service: str, hour: str, req_sn: str) -> Optional[str]:
        """
        通过 REQ_SN 查询 TraceID
        
        Args:
            service: 服务名（仅 sft-aipg 有 REQ_SN 索引）
            hour: 小时 (YYYYMMDDHH)
            req_sn: REQ_SN
        
        Returns:
            TraceID，未找到返回 None
        """
        if service != 'sft-aipg':
            # 其他应用没有 REQ_SN 索引
            return None
        
        # 检查缓存
        cached = self._get_from_cache(self._reqsn_cache, service, hour)
        if cached is not None:
            req_sn_to_trace = cached.get('req_sn_to_trace', {})
            trace_id = req_sn_to_trace.get(req_sn)
            if trace_id:
                print(f"[DEBUG] REQ_SN → TraceID (缓存命中): {req_sn} → {trace_id}")
                return trace_id
        
        index_file = self._get_reqsn_index_path(service, hour)
        
        if not os.path.exists(index_file):
            print(f"[DEBUG] REQ_SN 索引文件不存在：{index_file}")
            return None
        
        try:
            with open(index_file, 'rb') as f:
                data = msgpack.unpack(f)
            
            # 添加到缓存
            self._add_to_cache(self._reqsn_cache, service, hour, data)
            
            req_sn_to_trace = data.get('req_sn_to_trace', {})
            trace_id = req_sn_to_trace.get(req_sn)
            
            if trace_id:
                print(f"[DEBUG] REQ_SN → TraceID: {req_sn} → {trace_id}")
            else:
                print(f"[DEBUG] 未找到 REQ_SN: {req_sn}")
            
            return trace_id
            
        except Exception as e:
            print(f"[ERROR] 加载 REQ_SN 索引失败：{e}")
            return None
    
    def get_trace_entries(self, service: str, hour: str, trace_id: str) -> List[Dict]:
        """
        通过 TraceID 查询日志位置列表（带缓存）
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
            trace_id: TraceID
        
        Returns:
            日志位置列表
        """
        # 检查缓存
        cached = self._get_from_cache(self._trace_cache, service, hour)
        if cached is not None:
            trace_index = cached.get('trace_index', {})
            entries = trace_index.get(trace_id, [])
            if entries:
                print(f"[DEBUG] TraceID → {len(entries)} 条日志 (缓存命中): {trace_id}")
            return entries
        
        index_file = self._get_trace_index_path(service, hour)
        
        if not os.path.exists(index_file):
            print(f"[DEBUG] TraceID 索引文件不存在：{index_file}")
            return []
        
        try:
            with open(index_file, 'rb') as f:
                data = msgpack.unpack(f)
            
            # 添加到缓存
            self._add_to_cache(self._trace_cache, service, hour, data)
            
            trace_index = data.get('trace_index', {})
            entries = trace_index.get(trace_id, [])
            
            print(f"[DEBUG] TraceID → {len(entries)} 条日志：{trace_id}")
            
            return entries
            
        except Exception as e:
            print(f"[ERROR] 加载 TraceID 索引失败：{e}")
            return []
    
    def get_all_traces_in_hour(self, service: str, hour: str) -> Set[str]:
        """
        获取指定小时内所有 TraceID
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
        
        Returns:
            TraceID 集合
        """
        index_file = self._get_trace_index_path(service, hour)
        
        if not os.path.exists(index_file):
            return set()
        
        try:
            with open(index_file, 'rb') as f:
                data = msgpack.unpack(f)
            
            trace_index = data.get('trace_index', {})
            return set(trace_index.keys())
            
        except Exception as e:
            print(f"[ERROR] 加载 TraceID 索引失败：{e}")
            return set()
    
    def _get_reqsn_index_path(self, service: str, hour: str) -> str:
        """获取 REQ_SN 索引文件路径"""
        return os.path.join(self.log_base_dir, service, f'{service}_{hour}.log.reqsn_index.msgpack')
    
    def _get_trace_index_path(self, service: str, hour: str) -> str:
        """获取 TraceID 索引文件路径"""
        return os.path.join(self.log_base_dir, service, f'{service}_{hour}.log.trace_index.msgpack')
    
    def index_exists(self, service: str, hour: str, index_type: str = 'trace') -> bool:
        """
        检查索引文件是否存在
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
            index_type: 'reqsn' 或 'trace'
        
        Returns:
            是否存在
        """
        if index_type == 'reqsn':
            index_file = self._get_reqsn_index_path(service, hour)
        else:
            index_file = self._get_trace_index_path(service, hour)
        
        return os.path.exists(index_file)
    
    def get_index_meta(self, service: str, hour: str, index_type: str = 'trace') -> Optional[Dict]:
        """
        获取索引文件的元数据
        
        Args:
            service: 服务名
            hour: 小时 (YYYYMMDDHH)
            index_type: 'reqsn' 或 'trace'
        
        Returns:
            元数据字典，失败返回 None
        """
        if index_type == 'reqsn':
            index_file = self._get_reqsn_index_path(service, hour)
        else:
            index_file = self._get_trace_index_path(service, hour)
        
        if not os.path.exists(index_file):
            return None
        
        try:
            with open(index_file, 'rb') as f:
                data = msgpack.unpack(f)
            
            return data.get('meta', {})
            
        except Exception as e:
            print(f"[ERROR] 读取索引元数据失败：{e}")
            return None


# 全局索引加载器实例
_index_loader = None

def get_index_loader(log_base_dir: str = '/root/sft/testlogs') -> IndexLoader:
    """获取全局索引加载器实例"""
    global _index_loader
    if _index_loader is None or _index_loader.log_base_dir != log_base_dir:
        _index_loader = IndexLoader(log_base_dir)
    return _index_loader
