#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志内容流式读取器 v2

根据索引中的位置信息，流式读取日志内容
内存占用：<1MB
"""

import os
import re
import gzip
from typing import Optional, Dict, List


class LogReader:
    """日志内容流式读取器"""
    
    def __init__(self, log_base_dir: str):
        self.log_base_dir = log_base_dir
    
    def read_log_by_position(self, file: str, block: int, service: str = None) -> Optional[str]:
        """
        根据文件位置和块号读取日志内容
        
        Args:
            file: 文件名（可以是相对路径或完整路径）
            block: 日志块号（从 0 开始）
            service: 服务名（用于构建完整路径，如果 file 不是完整路径）
        
        Returns:
            日志内容，失败返回 None
        """
        # 构建完整文件路径
        file_path = self._resolve_file_path(file, service)
        
        if not file_path or not os.path.exists(file_path):
            print(f"[DEBUG] 文件不存在：{file_path}")
            return None
        
        try:
            # 打开文件（支持 .log 和 .log.gz）
            # 优先尝试 GBK 编码（中文日志通常是 GBK），失败则用 UTF-8
            if file_path.endswith('.gz'):
                # 尝试 GBK 编码
                try:
                    f = gzip.open(file_path, 'rt', encoding='gbk', errors='ignore')
                except:
                    f = gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore')
            else:
                # 尝试 GBK 编码
                try:
                    f = open(file_path, 'r', encoding='gbk', errors='ignore')
                except:
                    f = open(file_path, 'r', encoding='utf-8', errors='ignore')
            
            current_block = 0
            current_lines = []
            
            for line in f:
                # 检查是否为新日志块开头
                if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
                    if current_block == block and current_lines:
                        # 找到目标块
                        f.close()
                        return ''.join(current_lines).strip()
                    
                    current_block += 1
                    current_lines = [line]
                else:
                    current_lines.append(line)
            
            # 处理最后一个块
            if current_block == block and current_lines:
                f.close()
                return ''.join(current_lines).strip()
            
            f.close()
            return None
            
        except Exception as e:
            print(f"[ERROR] 读取日志失败 {file_path}: {e}")
            return None
    
    def read_logs_by_entries(self, entries: List[Dict], service: str = None) -> List[Dict]:
        """
        批量读取多条日志内容
        
        Args:
            entries: 日志位置列表（来自索引）
            service: 服务名
        
        Returns:
            包含内容的日志列表
        """
        results = []
        
        for entry in entries:
            file = entry.get('file', '')
            block = entry.get('block', 0)
            
            content = self.read_log_by_position(file, block, service)
            
            if content:
                # 解析日志内容
                parsed = self._parse_log_content(content)
                
                results.append({
                    'timestamp': entry.get('timestamp', '') or parsed.get('timestamp', ''),
                    'thread': entry.get('thread', '') or parsed.get('thread', ''),
                    'trace_id': parsed.get('trace_id', ''),
                    'level': entry.get('level', '') or parsed.get('level', ''),
                    'service': service or '',
                    'content': content,
                    'parsed_content': parsed.get('parsed_content', {})
                })
        
        return results
    
    def _resolve_file_path(self, file: str, service: str = None) -> Optional[str]:
        """
        解析文件路径
        
        Args:
            file: 文件名
            service: 服务名
        
        Returns:
            完整文件路径
        """
        # 如果已经是完整路径，直接返回
        if os.path.isabs(file) and os.path.exists(file):
            return file
        
        # 如果是相对路径，需要服务名
        if not service:
            print(f"[ERROR] 无法解析文件路径，缺少服务名：{file}")
            return None
        
        # 在 service 目录下查找文件
        service_dir = os.path.join(self.log_base_dir, service)
        
        if not os.path.exists(service_dir):
            return None
        
        # 直接拼接
        file_path = os.path.join(service_dir, file)
        
        if os.path.exists(file_path):
            return file_path
        
        # 尝试 .gz 后缀
        if not file.endswith('.gz'):
            gz_path = file_path + '.gz'
            if os.path.exists(gz_path):
                return gz_path
        
        return None
    
    def _parse_log_content(self, content: str) -> Dict:
        """
        解析日志内容
        
        Args:
            content: 日志内容
        
        Returns:
            解析后的字典
        """
        result = {
            'original': content,
            'parsed_content': {}
        }
        
        # 解析日志头部
        pattern = r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[\]-\[(.*)$'
        match = re.match(pattern, content.strip() if content else '')
        
        if match:
            result.update({
                'timestamp': match.group(1),
                'thread': match.group(2),
                'trace_id': match.group(3),
                'level': match.group(4),
                'env': match.group(5),
                'company': match.group(6),
                'service': match.group(7),
                'content_body': match.group(8)
            })
            
            # 尝试提取 REQ_SN
            content_body = match.group(8)
            req_sn = self._extract_req_sn(content_body)
            if req_sn:
                result['parsed_content']['req_sn'] = req_sn
        
        return result
    
    def _extract_req_sn(self, content: str) -> Optional[str]:
        """从日志内容中提取 REQ_SN"""
        # 尝试从 XML 中提取
        if '<?xml' in content and '</AIPG>' in content:
            match = re.search(r'<REQ_SN>([^<]+)</REQ_SN>', content)
            if match:
                return match.group(1)
        
        # 尝试从普通文本中提取
        match = re.search(r'REQ_SN[=:\s]+([A-Za-z0-9-]+)', content)
        if match:
            return match.group(1)
        
        return None


# 全局日志读取器实例
_log_reader = None

def get_log_reader(log_base_dir: str = '/root/sft/testlogs') -> LogReader:
    """获取全局日志读取器实例"""
    global _log_reader
    if _log_reader is None or _log_reader.log_base_dir != log_base_dir:
        _log_reader = LogReader(log_base_dir)
    return _log_reader
