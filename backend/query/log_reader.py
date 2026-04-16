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
import json
from typing import Optional, Dict, List


class LogReader:
    """日志内容流式读取器"""
    
    def __init__(self, log_base_dir: str):
        self.log_base_dir = log_base_dir
    
    def read_log_by_position(self, file: str, block: int, service: str = None, preview: bool = False) -> Optional[str]:
        """
        根据文件位置和块号读取日志内容
        
        Args:
            file: 文件名（可以是相对路径或完整路径）
            block: 日志块号（从 0 开始）
            service: 服务名（用于构建完整路径，如果 file 不是完整路径）
            preview: 是否只读取预览（前 300 字符），用于快速筛选
        
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
                        content = ''.join(current_lines).strip()
                        f.close()
                        # 预览模式：只返回前 300 字符
                        if preview:
                            return content[:300]
                        return content
                    
                    current_block += 1
                    current_lines = [line]
                else:
                    current_lines.append(line)
            
            # 处理最后一个块
            if current_block == block and current_lines:
                content = ''.join(current_lines).strip()
                f.close()
                # 预览模式：只返回前 300 字符
                if preview:
                    return content[:300]
                return content
            
            f.close()
            return None
            
        except Exception as e:
            print(f"[ERROR] 读取日志失败 {file_path}: {e}")
            return None
    
    def read_logs_by_entries(self, entries: List[Dict], service: str = None, filter_key: bool = False) -> List[Dict]:
        """
        批量读取多条日志内容
        
        Args:
            entries: 日志位置列表（来自索引）
            service: 服务名
            filter_key: 是否只读取关键日志（sft-aipg 专用优化）
        
        Returns:
            包含内容的日志列表
        """
        results = []
        
        # 优化：所有应用都使用 length 字段快速筛选，避免读取所有日志
        key_entries = []
        if filter_key:
            print(f"[DEBUG] {service} 快速筛选：{len(entries)} 条 entries")
            # 检查 entries 是否有 length 字段（当前小时内存索引没有 length）
            if entries and 'length' not in entries[0]:
                print(f"[DEBUG] {service} entries 没有 length 字段（当前小时索引），直接读取完整内容")
                # 对没有 length 的 entries，优先使用已缓存的内容
                final_entries = []
                seen_blocks = set()
                for entry in entries:
                    block = entry.get('block', 0)
                    if block in seen_blocks:
                        continue
                    
                    # 优先使用已缓存的内容（当前小时索引专用优化）
                    content = entry.get('content')
                    
                    # 如果没有缓存，才读取文件
                    if not content:
                        file = entry.get('file', '')
                        content = self.read_log_by_position(file, block, service, preview=False)
                    
                    if content and self._is_key_log(content):
                        seen_blocks.add(block)
                        final_entries.append(entry)
                        # 解析并添加到结果
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
                print(f"[DEBUG] 筛选后：{len(entries)} → {len(results)} 条")
                return results
            
            # 按 length 分组去重，只保留每种长度的第一条
            seen = {}
            for entry in entries:
                length = entry.get('length', 0)
                timestamp = entry.get('timestamp', '')
                
                # 关键日志特征：
                # 1. XML 请求：length 1000-1200，最早的时间戳
                # 2. XML 响应：length 1000-1200，最晚的时间戳
                # 3. 请求完成：length 150-250，最晚的时间戳
                key = f"{length}"
                
                # 长日志（XML 请求/响应）
                if 500 <= length <= 1200:
                    if key not in seen:
                        seen[key] = []
                    seen[key].append(entry)
                # 中等长度（可能是请求完成/RPC 调用）
                elif 100 <= length <= 300:
                    if 'medium' not in seen:
                        seen['medium'] = []
                    seen['medium'].append(entry)
            
            # 每种长度只取第一条和最后一条
            for length_key, entry_list in seen.items():
                if len(entry_list) == 1:
                    key_entries.append(entry_list[0])
                elif len(entry_list) > 1:
                    # 按时间排序，取第一条和最后一条
                    sorted_entries = sorted(entry_list, key=lambda x: x.get('timestamp', ''))
                    key_entries.append(sorted_entries[0])  # 最早
                    key_entries.append(sorted_entries[-1])  # 最晚
            
            # 去重（相同 block）+ 内容预览确认
            final_entries = []
            seen_blocks = set()
            for entry in key_entries:
                block = entry.get('block', 0)
                if block in seen_blocks:
                    continue
                
                # 快速预览确认是否是关键日志
                file = entry.get('file', '')
                preview = self.read_log_by_position(file, block, service, preview=True)
                
                if preview and self._is_key_log(preview):
                    seen_blocks.add(block)
                    final_entries.append(entry)
            
            # 如果筛选后还是太多，进一步限制
            if len(final_entries) > 10:
                # 按时间排序，取前 3 条和最后 3 条
                sorted_entries = sorted(final_entries, key=lambda x: x.get('timestamp', ''))
                final_entries = sorted_entries[:3] + sorted_entries[-3:]
                # 去重
                seen_blocks = set()
                unique_entries = []
                for e in final_entries:
                    block = e.get('block', 0)
                    if block not in seen_blocks:
                        seen_blocks.add(block)
                        unique_entries.append(e)
                final_entries = unique_entries
            
            print(f"[DEBUG] 筛选后：{len(entries)} → {len(final_entries)} 条（基于 length+preview）")
            entries = final_entries
        
        # 读取筛选后的日志完整内容
        for entry in entries:
            file = entry.get('file', '')
            block = entry.get('block', 0)
            
            content = self.read_log_by_position(file, block, service, preview=False)
            
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
    
    def _is_key_log(self, content: str) -> bool:
        """
        判断是否是关键日志（用于所有应用快速筛选）
        
        Args:
            content: 日志内容（预览）
        
        Returns:
            是否关键日志
        """
        # 1. 交易发起日志（XML 请求）
        if '<?xml' in content and '<AIPG>' in content:
            if '<RET_CODE>' not in content:
                return True
        
        # 2. 交易返回结果（XML 响应）
        if '<RET_CODE>' in content:
            return True
        
        # 3. 请求完成（含 IP）
        if '请求处理完成' in content:
            return True
        
        # 4. RPC 调用开始/结束（其他应用）
        if 'rpc.from' in content or 'rpc.to' in content:
            return True
        
        # 5. 请求标记
        if '请求>>' in content or '响应>>' in content:
            return True
        
        return False
    
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
        
        # 尝试从 log_dirs.json 加载服务目录配置
        service_dir = None
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        log_dirs_file = os.path.join(config_dir, 'log_dirs.json')
        
        if os.path.exists(log_dirs_file):
            try:
                with open(log_dirs_file, 'r', encoding='utf-8') as f:
                    log_dirs = json.load(f)
                service_path = log_dirs.get(service)
                if service_path:
                    # 路径转换：宿主机路径 -> 容器内路径
                    if service_path.startswith('/root/sft/testlogs'):
                        service_dir = service_path.replace('/root/sft/testlogs', '/data/logs')
                    else:
                        service_dir = service_path
                    print(f"[DEBUG] 使用 log_dirs.json 配置：{service} -> {service_dir}")
            except Exception as e:
                print(f"[WARN] 加载 log_dirs.json 失败：{e}")
        
        # 如果没有配置，使用默认路径
        if not service_dir:
            service_dir = os.path.join(self.log_base_dir, service)
        
        if not os.path.exists(service_dir):
            print(f"[WARN] 服务目录不存在：{service_dir}")
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
