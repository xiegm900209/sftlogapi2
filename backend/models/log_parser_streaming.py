#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式日志解析器 - 真正逐行读取，不加载整个文件
内存占用：<1MB
"""

import re
import gzip
from typing import Generator, Optional, Dict
import xml.etree.ElementTree as ET


class LogBlock:
    """日志块数据结构"""
    def __init__(self, timestamp: str, thread: str, trace_id: str, level: str,
                 env: str, company: str, service: str, content: str):
        self.timestamp = timestamp
        self.thread = thread
        self.trace_id = trace_id
        self.level = level
        self.env = env
        self.company = company
        self.service = service
        self.content = content
        self.parsed_content = self._parse_content(content)

    def _parse_content(self, content: str) -> Dict:
        """解析日志内容，提取关键信息"""
        parsed = {'original': content}
        if '<?xml' in content and '</AIPG>' in content:
            try:
                xml_start = content.find('<?xml')
                xml_end = content.rfind('>') + 1
                xml_str = content[xml_start:xml_end]
                root = ET.fromstring(xml_str)
                parsed['type'] = 'xml'
                info_elem = root.find('.//INFO')
                if info_elem is not None:
                    req_sn_elem = info_elem.find('REQ_SN')
                    if req_sn_elem is not None:
                        parsed['req_sn'] = req_sn_elem.text
            except ET.ParseError:
                parsed['type'] = 'malformed_xml'
        else:
            parsed['type'] = 'text'
        return parsed


def read_log_blocks_streaming(file_path: str, target_trace_id: Optional[str] = None, 
                               target_req_sn: Optional[str] = None,
                               max_blocks: int = 100) -> Generator[LogBlock, None, None]:
    """
    流式读取日志块 - 真正逐行读取，不加载整个文件
    
    Args:
        file_path: 日志文件路径
        target_trace_id: 目标 TraceID（可选，用于过滤）
        target_req_sn: 目标 REQ_SN（可选，用于过滤）
        max_blocks: 最大返回块数（防止内存溢出）
    
    Yields:
        LogBlock 对象
    """
    is_gzip_file = file_path.endswith('.gz')
    
    try:
        if is_gzip_file:
            f = gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore')
        else:
            f = open(file_path, 'r', encoding='utf-8', errors='ignore')
        
        current_lines = []
        blocks_yielded = 0
        
        for line in f:  # ← 真正逐行读取
            if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
                if current_lines:
                    log_block = parse_log_block_streaming(''.join(current_lines))
                    
                    # 过滤
                    if log_block:
                        match = True
                        if target_trace_id and log_block.trace_id != target_trace_id:
                            match = False
                        if target_req_sn:
                            req_sn = log_block.parsed_content.get('req_sn')
                            if req_sn != target_req_sn:
                                match = False
                        
                        if match:
                            yield log_block
                            blocks_yielded += 1
                            if blocks_yielded >= max_blocks:
                                f.close()
                                return
                    
                    current_lines = [line]
                else:
                    current_lines = [line]
            else:
                current_lines.append(line)
        
        # 处理最后一个块
        if current_lines:
            log_block = parse_log_block_streaming(''.join(current_lines))
            if log_block:
                match = True
                if target_trace_id and log_block.trace_id != target_trace_id:
                    match = False
                if target_req_sn:
                    req_sn = log_block.parsed_content.get('req_sn')
                    if req_sn != target_req_sn:
                        match = False
                
                if match and blocks_yielded < max_blocks:
                    yield log_block
        
        f.close()
        
    except Exception as e:
        print(f"[ERROR] 流式读取失败 {file_path}: {e}")
        return


def parse_log_block_streaming(block_text: str) -> Optional[LogBlock]:
    """解析单个日志块"""
    lines = block_text.split('\n')
    first_line = lines[0] if lines else ''
    
    pattern = r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[\]-\[(.*)$'
    match = re.match(pattern, first_line.strip())
    
    if not match:
        return None
    
    groups = match.groups()
    timestamp = groups[0]
    thread = groups[1]
    trace_id = groups[2]
    level = groups[3]
    env = groups[4]
    company = groups[5]
    service = groups[6]
    content = groups[7] if len(groups) > 7 else ''
    
    # 合并续行
    if len(lines) > 1:
        content = block_text.strip()
        if content.endswith('?:?]'):
            content = content[:-4]
    
    return LogBlock(timestamp, thread, trace_id, level, env, company, service, content)


def find_trace_ids_by_req_sn_streaming(service_dir: str, req_sn: str, log_time: str, 
                                        max_trace_ids: int = 10) -> set:
    """
    流式查找包含 REQ_SN 的 TraceID
    
    Args:
        service_dir: 服务目录
        req_sn: REQ_SN
        log_time: 日志时间 (YYYYMMDDHH)
        max_trace_ids: 最大 TraceID 数量
    
    Returns:
        TraceID 集合
    """
    import os
    
    trace_ids = set()
    files_checked = 0
    
    for filename in sorted(os.listdir(service_dir)):
        if files_checked >= 3:  # 最多检查 3 个文件
            break
        
        if not (filename.endswith('.log') or filename.endswith('.log.gz')):
            continue
        
        if log_time not in filename:
            continue
        
        file_path = os.path.join(service_dir, filename)
        
        for log_block in read_log_blocks_streaming(file_path, target_req_sn=req_sn, max_blocks=50):
            if log_block.trace_id:
                trace_ids.add(log_block.trace_id)
                if len(trace_ids) >= max_trace_ids:
                    return trace_ids
        
        files_checked += 1
    
    return trace_ids
