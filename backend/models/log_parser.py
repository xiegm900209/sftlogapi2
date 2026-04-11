import re
import gzip
from datetime import datetime
from typing import Generator, Dict, List, Optional
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

        # 尝试解析 XML 内容
        if '<?xml' in content and '</AIPG>' in content:
            try:
                xml_start = content.find('<?xml')
                xml_end = content.rfind('>') + 1
                xml_str = content[xml_start:xml_end]

                root = ET.fromstring(xml_str)
                parsed['type'] = 'xml'
                parsed['data'] = self._xml_to_dict(root)

                info_elem = root.find('.//INFO')
                if info_elem is not None:
                    req_sn_elem = info_elem.find('REQ_SN')
                    if req_sn_elem is not None:
                        parsed['req_sn'] = req_sn_elem.text

                    trx_code_elem = info_elem.find('TRX_CODE')
                    if trx_code_elem is not None:
                        parsed['trx_code'] = trx_code_elem.text

            except ET.ParseError:
                parsed['type'] = 'malformed_xml'
        else:
            parsed['type'] = 'text'

        return parsed

    def _xml_to_dict(self, element):
        """将 XML 元素转换为字典"""
        result = {}
        if element.text and element.text.strip():
            if len(element) == 0:
                return element.text.strip()

        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        return result


def read_log_blocks(file_path: str) -> Generator[LogBlock, None, None]:
    """
    使用生成器逐块读取日志文件
    每条完整的日志记录以时间戳 [YYYY-MM-DD HH:mm:ss.SSS] 开头
    如果一行不以时间戳开头，它属于上一条日志的延续（多行日志）
    
    支持:
    - 普通日志文件 (.log)
    - Gzip 压缩文件 (.log.gz)
    - GBK 和 UTF-8 编码
    """
    # 检查是否为 gzip 文件
    is_gzip_file = file_path.endswith('.gz')
    
    # 尝试不同编码读取文件 - GBK 在前因为中文日志通常是 GBK
    encodings = ['gbk', 'gb18030', 'utf-8']
    content = None
    used_encoding = 'utf-8'
    
    try:
        if is_gzip_file:
            # 使用 gzip 读取压缩文件
            for encoding in encodings:
                try:
                    with gzip.open(file_path, 'rt', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except (UnicodeDecodeError, gzip.BadGzipFile, EOFError, OSError):
                    continue
            
            if content is None:
                # 如果编码都失败，尝试二进制读取
                with gzip.open(file_path, 'rb') as f:
                    raw_bytes = f.read()
                try:
                    content = raw_bytes.decode('gbk', errors='replace')
                    used_encoding = 'gbk (from gzip)'
                except:
                    content = raw_bytes.decode('latin-1')
                    used_encoding = 'latin-1'
        else:
            # 普通文件读取
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            
            if content is None:
                with open(file_path, 'rb') as f:
                    raw_bytes = f.read()
                try:
                    content = raw_bytes.decode('gbk', errors='replace')
                    used_encoding = 'gbk (from binary)'
                except:
                    content = raw_bytes.decode('latin-1')
                    used_encoding = 'latin-1'
    except Exception as e:
        # 如果文件读取失败，返回空内容
        print(f"Warning: Failed to read {file_path}: {e}")
        return
    
    # 按行处理
    lines = content.split('\n')
    current_block_lines = []

    for line in lines:
        # 检查是否为新的日志块开头（以时间戳开始）
        if re.match(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\]', line):
            if current_block_lines:
                # 解析上一个日志块
                yield parse_log_block(''.join(current_block_lines))

            current_block_lines = [line]
        else:
            # 续行内容，添加到当前块
            current_block_lines.append(line)

    # 处理最后一个块
    if current_block_lines:
        yield parse_log_block(''.join(current_block_lines))


def parse_log_block(block_text: str) -> Optional[LogBlock]:
    """
    解析单个日志块的文本，提取各个字段
    格式：[timestamp][thread][trace_id][level][env][company][service][]-[content]
    
    支持多行日志：第一行包含头部信息，后续行是 content 的延续
    """
    lines = block_text.split('\n')
    first_line = lines[0] if lines else ''
    
    # 正则表达式匹配日志头部格式
    # [2026-04-08 09:00:00.335][http-apr-8195-exec-2284][TC5PCfGK][DEBUG][C02][sft][sft-aipg][]-[content]
    pattern = r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[\]-\[(.*)$'
    
    match = re.match(pattern, first_line.strip())
    if not match:
        # 如果无法解析，返回基本结构
        return LogBlock(
            timestamp='',
            thread='',
            trace_id='',
            level='',
            env='',
            company='',
            service='',
            content=block_text
        )

    groups = match.groups()
    timestamp = groups[0]
    thread = groups[1]
    trace_id = groups[2]
    level = groups[3]
    env = groups[4]
    company = groups[5]
    service = groups[6]
    
    # 第一行的 content 部分（可能不完整）
    first_content = groups[7] if len(groups) > 7 else ''
    
    # 合并所有行作为完整内容（包括续行）
    # 移除末尾的 ?:?] 标记
    full_content = block_text.strip()
    if full_content.endswith('?:?]'):
        full_content = full_content[:-4]
    
    # 第一行 content 移除末尾的 ?:?]
    content_start = first_content
    if content_start.endswith('?:?]'):
        content_start = content_start[:-4]
    
    # 如果有续行，合并所有内容
    if len(lines) > 1:
        content = full_content
    else:
        content = content_start

    return LogBlock(timestamp, thread, trace_id, level, env, company, service, content)


def find_index_file_for_log(log_file: str) -> Optional[str]:
    """
    查找日志文件对应的索引文件
    
    索引文件命名规则：
    - 压缩文件：xxx.log.gz -> xxx.log.index.json
    - 普通文件：xxx.log -> xxx.log.index.json (如果存在)
    """
    import os
    
    # 尝试查找同名的索引文件（注意：不要链式 replace）
    if log_file.endswith('.log.gz'):
        index_file = log_file[:-3] + '.index.json'  # .log.gz -> .log.index.json
    elif log_file.endswith('.log'):
        index_file = log_file + '.index.json'  # .log -> .log.index.json
    else:
        index_file = log_file + '.index.json'
    
    if os.path.exists(index_file):
        return index_file
    
    # 尝试在 logs_index 目录查找
    log_dir = os.path.dirname(os.path.dirname(log_file))
    index_dir = os.path.join(log_dir, 'logs_index')
    basename = os.path.basename(log_file)
    
    # 可能的索引文件名
    possible_names = []
    if basename.endswith('.log.gz'):
        possible_names.append(f'{basename[:-3]}.index.json')
    elif basename.endswith('.log'):
        possible_names.append(f'{basename}.index.json')
    
    for name in possible_names:
        path = os.path.join(index_dir, name)
        if os.path.exists(path):
            return path
    
    return None


def load_index(index_file: str) -> Dict:
    """加载索引文件"""
    import json
    
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载索引失败 {index_file}: {e}")
        return {'trace_id_index': {}, 'req_sn_index': {}}


def find_files_by_req_sn_from_index(index_data: Dict, req_sn: str) -> List[str]:
    """从索引中查找包含 REQ_SN 的文件"""
    req_sn_index = index_data.get('req_sn_index', {})
    return list(req_sn_index.get(req_sn, []))


def find_files_by_trace_id_from_index(index_data: Dict, trace_id: str) -> List[str]:
    """从索引中查找包含 TraceID 的文件"""
    trace_id_index = index_data.get('trace_id_index', {})
    return list(trace_id_index.get(trace_id, []))


def find_logs_by_req_sn(service_name: str, req_sn: str, log_dir: str = '/app/logs', 
                        use_index: bool = True, build_index_if_missing: bool = False) -> List[LogBlock]:
    """
    根据 REQ_SN 在指定服务的日志中查找对应的日志块
    
    Args:
        service_name: 服务名称
        req_sn: REQ_SN
        log_dir: 日志目录
        use_index: 是否使用索引加速（默认 True）
        build_index_if_missing: 如果索引不存在是否构建（默认 False，仅对未压缩日志）
    
    Returns:
        匹配的日志块列表
    """
    import os

    service_dir = os.path.join(log_dir, service_name)
    if not os.path.exists(service_dir):
        return []

    result = []
    target_files = []
    
    # 步骤 1: 尝试使用索引查找
    if use_index:
        for filename in os.listdir(service_dir):
            if not (filename.endswith('.log') or filename.endswith('.log.gz')):
                continue
            
            file_path = os.path.join(service_dir, filename)
            index_file = find_index_file_for_log(file_path)
            
            if index_file:
                # 有索引文件，直接使用
                index_data = load_index(index_file)
                matched_files = find_files_by_req_sn_from_index(index_data, req_sn)
                target_files.extend(matched_files)
            elif build_index_if_missing and filename.endswith('.log'):
                # 未压缩日志且需要构建索引
                from models.indexer import IndexBuilder
                indexer = IndexBuilder()
                indexer._index_file(file_path)
                
                # 保存索引
                index_path = file_path + '.index.json'
                indexer.save_index(index_path)
                
                # 使用刚构建的索引
                if req_sn in indexer.req_sn_index:
                    target_files.append(file_path)
            else:
                # 无索引，标记为需要扫描
                target_files.append(file_path)
    else:
        # 不使用索引，扫描所有文件
        for filename in os.listdir(service_dir):
            if filename.endswith('.log') or filename.endswith('.log.gz'):
                target_files.append(os.path.join(service_dir, filename))
    
    # 步骤 2: 在目标文件中查找
    for file_path in target_files:
        if not os.path.exists(file_path):
            continue
        
        for log_block in read_log_blocks(file_path):
            if 'req_sn' in log_block.parsed_content and log_block.parsed_content['req_sn'] == req_sn:
                result.append(log_block)

    return result


def find_logs_by_trace_id(service_name: str, trace_id: str, log_dir: str = '/app/logs', 
                          max_logs: int = 500, use_index: bool = True, 
                          build_index_if_missing: bool = False) -> List[LogBlock]:
    """
    根据 TraceID 在指定服务的日志中查找对应的日志块（带数量限制）
    
    Args:
        service_name: 服务名称
        trace_id: TraceID
        log_dir: 日志目录
        max_logs: 最大返回日志数（默认 500）
        use_index: 是否使用索引加速（默认 True）
        build_index_if_missing: 如果索引不存在是否构建（默认 False，仅对未压缩日志）
    
    Returns:
        匹配的日志块列表
    """
    import os

    service_dir = os.path.join(log_dir, service_name)
    if not os.path.exists(service_dir):
        return []

    result = []
    target_files = []
    
    # 步骤 1: 尝试使用索引查找
    if use_index:
        for filename in sorted(os.listdir(service_dir)):
            if not (filename.endswith('.log') or filename.endswith('.log.gz')):
                continue
            
            file_path = os.path.join(service_dir, filename)
            index_file = find_index_file_for_log(file_path)
            
            if index_file:
                # 有索引文件，直接使用
                index_data = load_index(index_file)
                matched_files = find_files_by_trace_id_from_index(index_data, trace_id)
                target_files.extend(matched_files)
            elif build_index_if_missing and filename.endswith('.log'):
                # 未压缩日志且需要构建索引
                from models.indexer import IndexBuilder
                indexer = IndexBuilder()
                indexer._index_file(file_path)
                
                # 保存索引
                index_path = file_path + '.index.json'
                indexer.save_index(index_path)
                
                # 使用刚构建的索引
                if trace_id in indexer.trace_id_index:
                    target_files.append(file_path)
            else:
                # 无索引，标记为需要扫描
                target_files.append(file_path)
    else:
        # 不使用索引，扫描所有文件
        for filename in sorted(os.listdir(service_dir)):
            if filename.endswith('.log') or filename.endswith('.log.gz'):
                target_files.append(os.path.join(service_dir, filename))
    
    # 步骤 2: 在目标文件中查找
    for file_path in target_files:
        if not os.path.exists(file_path):
            continue
        
        # 使用 max_blocks 参数限制读取数量
        for log_block in read_log_blocks(file_path, max_blocks=max(100, (max_logs - len(result)) * 2)):
            if log_block.trace_id == trace_id:
                result.append(log_block)
                if len(result) >= max_logs:
                    return result  # 达到限制，提前返回

    return result
