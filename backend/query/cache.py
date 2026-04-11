#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存缓存层 v2
LRU 缓存热点 TraceID 和 REQ_SN 查询结果
"""

import os
import sys
import time
from typing import Dict, List, Optional, Any
from collections import OrderedDict
from datetime import datetime
import threading

class LRUCache:
    """LRU 缓存实现"""
    
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.lock = threading.Lock()
        
        # 统计
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            # 检查 TTL
            if time.time() - self.timestamps[key] > self.ttl_seconds:
                del self.cache[key]
                del self.timestamps[key]
                self.misses += 1
                return None
            
            # 移到末尾 (最近使用)
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
    
    def put(self, key: str, value: Any):
        """设置缓存"""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    # 删除最旧的
                    oldest = next(iter(self.cache))
                    del self.cache[oldest]
                    del self.timestamps[oldest]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def delete(self, key: str):
        """删除缓存"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'ttl_seconds': self.ttl_seconds
        }


class QueryCache:
    """查询缓存封装"""
    
    def __init__(self, 
                 trace_cache_size: int = 5000,
                 req_sn_cache_size: int = 5000,
                 ttl_seconds: int = 3600):
        
        # TraceID 缓存
        self.trace_cache = LRUCache(max_size=trace_cache_size, ttl_seconds=ttl_seconds)
        
        # REQ_SN 缓存
        self.req_sn_cache = LRUCache(max_size=req_sn_cache_size, ttl_seconds=ttl_seconds)
        
        # 其他缓存
        self.services_cache = LRUCache(max_size=100, ttl_seconds=300)  # 5 分钟
        self.hours_cache = LRUCache(max_size=100, ttl_seconds=300)
        self.stats_cache = LRUCache(max_size=1000, ttl_seconds=60)  # 1 分钟
    
    def get_trace(self, trace_id: str, log_hour: str = None) -> Optional[List[Dict]]:
        """获取 TraceID 缓存"""
        key = f"{trace_id}:{log_hour or 'all'}"
        return self.trace_cache.get(key)
    
    def put_trace(self, trace_id: str, log_hour: str, results: List[Dict]):
        """设置 TraceID 缓存"""
        key = f"{trace_id}:{log_hour or 'all'}"
        self.trace_cache.put(key, results)
    
    def get_req_sn(self, req_sn: str, log_hour: str = None) -> Optional[List[Dict]]:
        """获取 REQ_SN 缓存"""
        key = f"{req_sn}:{log_hour or 'all'}"
        return self.req_sn_cache.get(key)
    
    def put_req_sn(self, req_sn: str, log_hour: str, results: List[Dict]):
        """设置 REQ_SN 缓存"""
        key = f"{req_sn}:{log_hour or 'all'}"
        self.req_sn_cache.put(key, results)
    
    def get_services(self) -> Optional[List[str]]:
        """获取服务列表缓存"""
        return self.services_cache.get('services')
    
    def put_services(self, services: List[str]):
        """设置服务列表缓存"""
        self.services_cache.put('services', services)
    
    def get_hours(self, service: str = None) -> Optional[List[str]]:
        """获取小时列表缓存"""
        key = f"hours:{service or 'all'}"
        return self.hours_cache.get(key)
    
    def put_hours(self, service: str, hours: List[str]):
        """设置小时列表缓存"""
        key = f"hours:{service or 'all'}"
        self.hours_cache.put(key, hours)
    
    def get_stats(self, log_hour: str = None, service: str = None) -> Optional[List[Dict]]:
        """获取统计缓存"""
        key = f"stats:{log_hour or 'all'}:{service or 'all'}"
        return self.stats_cache.get(key)
    
    def put_stats(self, log_hour: str, service: str, stats: List[Dict]):
        """设置统计缓存"""
        key = f"stats:{log_hour or 'all'}:{service or 'all'}"
        self.stats_cache.put(key, stats)
    
    def invalidate_hour(self, log_hour: str):
        """使某个小时的缓存失效"""
        # 清理所有包含该小时的缓存键
        for cache in [self.trace_cache, self.req_sn_cache]:
            keys_to_delete = [k for k in cache.cache.keys() if log_hour in k]
            for key in keys_to_delete:
                cache.delete(key)
    
    def get_all_stats(self) -> Dict:
        """获取所有缓存统计"""
        return {
            'trace_cache': self.trace_cache.get_stats(),
            'req_sn_cache': self.req_sn_cache.get_stats(),
            'services_cache': self.services_cache.get_stats(),
            'hours_cache': self.hours_cache.get_stats(),
            'stats_cache': self.stats_cache.get_stats()
        }
    
    def clear_all(self):
        """清空所有缓存"""
        self.trace_cache.clear()
        self.req_sn_cache.clear()
        self.services_cache.clear()
        self.hours_cache.clear()
        self.stats_cache.clear()


# 全局缓存实例
_query_cache = None

def get_query_cache() -> QueryCache:
    """获取全局缓存实例"""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache


# 测试
if __name__ == '__main__':
    cache = QueryCache()
    
    # 测试缓存
    cache.put_trace('TCJMHVle', '2026040809', [{'id': 1}])
    result = cache.get_trace('TCJMHVle', '2026040809')
    print(f"缓存测试：{result}")
    
    # 测试统计
    cache.put_stats('2026040809', 'sft-aipg', [{'total': 1000}])
    stats = cache.get_stats('2026040809', 'sft-aipg')
    print(f"统计缓存：{stats}")
    
    # 打印统计
    print("\n缓存统计:")
    for name, stat in cache.get_all_stats().items():
        print(f"  {name}: {stat['size']} 项，命中率 {stat['hit_rate']}")
