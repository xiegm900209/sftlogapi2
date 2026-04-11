#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sftlogapi v2 - Flask 应用主入口
高性能日志查询系统 (完整功能版)
"""

import os
import sys
import json
import time
import gzip
import re
import functools
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_caching import Cache

# 添加 backend 路径
sys.path.insert(0, os.path.dirname(__file__))

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from indexer.sqlite_sync import SQLiteSyncer
from query.sqlite_engine import SQLiteQueryEngine
from query.cache import get_query_cache, QueryCache
from query.index_loader import get_index_loader, IndexLoader
from query.log_reader import get_log_reader, LogReader
from query.current_hour_index import get_current_hour_manager, CurrentHourIndexManager
from models.log_parser import read_log_blocks

# 配置
CONFIG = {
    'DEBUG': os.environ.get('DEBUG', 'false').lower() == 'true',
    'HOST': os.environ.get('HOST', '0.0.0.0'),
    'PORT': int(os.environ.get('PORT', 5000)),
    'DB_PATH': os.environ.get('DB_PATH', '/data/index/logs_index.db'),
    'LOG_BASE_DIR': os.environ.get('LOG_BASE_DIR', '/data/logs'),
    'CONFIG_DIR': '/app/config',
    'FRONTEND_DIR': os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist'),
    'CACHE_TTL': int(os.environ.get('CACHE_TTL', 3600)),
    'CACHE_MAX_SIZE': int(os.environ.get('CACHE_MAX_SIZE', 10000)),
    'API_KEY': os.environ.get('API_KEY', 'zhiduoxing-2026-secret-key'),
    'ENABLE_AUTH': os.environ.get('ENABLE_AUTH', 'false').lower() == 'true'
}

# 创建应用
app = Flask(__name__, static_folder=CONFIG['FRONTEND_DIR'], static_url_path='/sftlogapi-v2/static')
app.config['DEBUG'] = CONFIG['DEBUG']

# 启用 CORS
CORS(app)

# API Key 认证装饰器
def require_api_key(f):
    """API Key 认证装饰器"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not CONFIG['ENABLE_AUTH']:
            return f(*args, **kwargs)
        
        api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not api_key:
            api_key = request.args.get('api_key', '')
        
        if api_key != CONFIG['API_KEY']:
            return jsonify({
                'success': False,
                'error_code': 401,
                'message': '认证失败：无效的 API Key'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# 初始化缓存
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# 初始化组件
query_engine = SQLiteQueryEngine(db_path=CONFIG['DB_PATH'], log_base_dir=CONFIG['LOG_BASE_DIR'])
query_cache = get_query_cache()
index_loader = get_index_loader(CONFIG['LOG_BASE_DIR'])
log_reader = get_log_reader(CONFIG['LOG_BASE_DIR'])
current_hour_manager = get_current_hour_manager(CONFIG['LOG_BASE_DIR'])

# 配置管理 (Docker 容器内路径)
TRANSACTION_TYPES_FILE = os.path.join(CONFIG['CONFIG_DIR'], 'transaction_types.json')
LOG_DIRS_FILE = os.path.join(CONFIG['CONFIG_DIR'], 'log_dirs.json')


def load_transaction_types():
    """加载交易类型配置"""
    if os.path.exists(TRANSACTION_TYPES_FILE):
        with open(TRANSACTION_TYPES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_transaction_types(data):
    """保存交易类型配置"""
    os.makedirs(os.path.dirname(TRANSACTION_TYPES_FILE), exist_ok=True)
    with open(TRANSACTION_TYPES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_log_dirs():
    """加载日志目录配置"""
    if os.path.exists(LOG_DIRS_FILE):
        with open(LOG_DIRS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 默认配置
    return {
        "sft-aipg": "/root/sft/testlogs/sft-aipg",
        "sft-trxqry": "/root/sft/testlogs/sft-trxqry",
        "sft-trxpay": "/root/sft/testlogs/sft-trxpay"
    }


def save_log_dirs(data):
    """保存日志目录配置"""
    os.makedirs(os.path.dirname(LOG_DIRS_FILE), exist_ok=True)
    with open(LOG_DIRS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================
# 前端路由
# ============================================

@app.route('/sftlogapi-v2/')
def index():
    """前端首页"""
    return send_from_directory(CONFIG['FRONTEND_DIR'], 'index.html')


@app.route('/sftlogapi-v2/<path:path>')
def static_files(path):
    """静态文件服务"""
    if os.path.exists(os.path.join(CONFIG['FRONTEND_DIR'], path)):
        return send_from_directory(CONFIG['FRONTEND_DIR'], path)
    return send_from_directory(CONFIG['FRONTEND_DIR'], 'index.html')


# ============================================
# 健康检查
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查（无需认证）"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '2.0.0',
        'auth_enabled': CONFIG['ENABLE_AUTH']
    })


# ============================================
# 智多星 AI 专用接口（带认证）
# ============================================

@app.route('/api/zdx/log-query', methods=['GET'])
@require_api_key
def zdx_log_query():
    """智多星专用 - 单日志查询（返回完整日志）"""
    return log_query()


@app.route('/api/zdx/transaction-trace', methods=['GET'])
@require_api_key
def zdx_transaction_trace():
    """智多星专用 - 交易链路追踪（返回完整日志）"""
    return transaction_trace()


@app.route('/api/zdx/transaction-analyze', methods=['POST'])
@require_api_key
def zdx_transaction_analyze():
    """智多星专用 - AI 智能分析交易（返回结构化分析 + 完整日志）"""
    start_time = time.time()
    
    data = request.get_json() or {}
    req_sn = data.get('req_sn')
    log_time = data.get('log_time')
    transaction_type = data.get('transaction_type')
    analysis_type = data.get('analysis_type', 'summary')
    
    if not req_sn or not log_time:
        return jsonify({
            'success': False,
            'error_code': 400,
            'message': '缺少必填参数：req_sn, log_time'
        }), 400
    
    # 获取交易类型配置
    types_config = load_transaction_types()
    type_info = types_config.get(transaction_type, {}) if transaction_type else {}
    apps = type_info.get('apps', [])
    
    # 步骤 1: 获取 TraceID
    trace_id = index_loader.get_reqsn_to_trace('sft-aipg', log_time, req_sn)
    
    if not trace_id:
        current_index = current_hour_manager.get_or_build('sft-aipg', log_time)
        if current_index:
            trace_id = current_index.get_trace_id(req_sn)
    
    if not trace_id:
        return jsonify({
            'success': True,
            'analysis': {
                'summary': {
                    'status': '未找到',
                    'req_sn': req_sn,
                    'message': '未找到相关日志'
                },
                'extracted_info': {},
                'flow': [],
                'issues': ['未找到交易日志'],
                'suggestions': ['请检查 REQ_SN 和日志时间是否正确']
            },
            'query_time_ms': round((time.time() - start_time) * 1000, 2)
        })
    
    # 步骤 2: 获取所有应用日志
    app_logs = {}
    total_logs = 0
    flow = []
    
    for app in (apps or ['sft-aipg']):
        entries = index_loader.get_trace_entries(app, log_time, trace_id)
        entries = entries[:100]  # 每应用最多 100 条
        
        if entries:
            logs = log_reader.read_logs_by_entries(entries, app)
            app_logs[app] = logs
            total_logs += len(logs)
            
            # 分析该应用的日志
            first_ts = logs[0].get('timestamp', '') if logs else ''
            last_ts = logs[-1].get('timestamp', '') if logs else ''
            
            flow.append({
                'service': app,
                'log_count': len(logs),
                'first_timestamp': first_ts,
                'last_timestamp': last_ts,
                'has_error': any('ERROR' in log.get('level', '') for log in logs),
                'logs': logs if analysis_type == 'full' else []  # 完整日志可选
            })
    
    # 步骤 3: 提取关键信息
    extracted_info = extract_transaction_info(app_logs)
    
    # 步骤 4: 检测问题
    issues = detect_issues(flow, extracted_info)
    suggestions = generate_suggestions(issues)
    
    # 步骤 5: 计算总耗时
    all_timestamps = []
    for app_flow in flow:
        if app_flow['first_timestamp']:
            all_timestamps.append(app_flow['first_timestamp'])
        if app_flow['last_timestamp']:
            all_timestamps.append(app_flow['last_timestamp'])
    
    total_time_ms = 0
    if len(all_timestamps) >= 2:
        try:
            from datetime import datetime as dt
            start = dt.strptime(min(all_timestamps), '%Y-%m-%d %H:%M:%S.%f')
            end = dt.strptime(max(all_timestamps), '%Y-%m-%d %H:%M:%S.%f')
            total_time_ms = int((end - start).total_seconds() * 1000)
        except:
            pass
    
    query_time = (time.time() - start_time) * 1000
    
    return jsonify({
        'success': True,
        'analysis': {
            'summary': {
                'status': '失败' if issues else '成功',
                'req_sn': req_sn,
                'trace_id': trace_id,
                'transaction_type': transaction_type,
                'transaction_name': type_info.get('name', '未知'),
                'total_logs': total_logs,
                'services_count': len(app_logs),
                'total_time_ms': total_time_ms,
                'query_time_ms': round(query_time, 2)
            },
            'extracted_info': extracted_info,
            'flow': flow,
            'issues': issues,
            'suggestions': suggestions
        },
        'query_time_ms': round(query_time, 2)
    })


def extract_transaction_info(app_logs):
    """从日志中提取关键信息"""
    info = {}
    
    for app, logs in app_logs.items():
        for log in logs:
            content = log.get('content', '')
            
            # 提取金额
            if not info.get('amount'):
                import re
                match = re.search(r'TRX_AMT[\">]([0-9.]+)', content)
                if match:
                    info['amount'] = match.group(1)
            
            # 提取商户号
            if not info.get('merchant_no'):
                import re
                match = re.search(r'MER_ID[\">]([A-Za-z0-9]+)', content)
                if match:
                    info['merchant_no'] = match.group(1)
            
            # 提取银行
            if not info.get('bank_name'):
                if '银行' in content:
                    import re
                    match = re.search(r'([^，,]+银行 [^，,]*)', content)
                    if match:
                        info['bank_name'] = match.group(1)
            
            # 提取错误信息
            if not info.get('error_message'):
                import re
                match = re.search(r'<ERR_MSG>([^<]+)</ERR_MSG>', content)
                if match:
                    info['error_message'] = match.group(1)
    
    return info


def detect_issues(flow, extracted_info):
    """检测问题"""
    issues = []
    
    # 检查错误日志
    for app_flow in flow:
        if app_flow.get('has_error'):
            issues.append(f"{app_flow['service']} 存在 ERROR 级别日志")
    
    # 检查错误信息
    if extracted_info.get('error_message'):
        issues.append(f"交易错误：{extracted_info['error_message']}")
    
    # 检查日志缺失
    if len(flow) < 3:
        issues.append("交易链路不完整，可能中途中断")
    
    return issues


def generate_suggestions(issues):
    """生成建议"""
    suggestions = []
    
    if not issues:
        suggestions.append("交易正常，无需处理")
    else:
        if any('ERROR' in issue for issue in issues):
            suggestions.append("请查看 ERROR 日志定位具体问题")
        if any('中断' in issue for issue in issues):
            suggestions.append("建议检查网络和服务状态")
        if any('错误' in issue for issue in issues):
            suggestions.append("根据错误信息联系对应团队处理")
    
    return suggestions


# ============================================
# 单日志追踪查询 (LogQuery.vue)
# ============================================

@app.route('/api/log-query', methods=['GET'])
def log_query():
    """
    综合日志查询 - 支持 REQ_SN、商户号、日志时间组合查询
    优化版：使用 MessagePack 索引文件快速定位 TraceID，然后流式读取日志内容
    
    参数:
    - req_sn: 交易序列号
    - merchant_no: 商户号
    - log_time: 日志时间（必填，YYYYMMDDHH）
    - service: 服务名称
    - page: 页码（默认 1）
    - page_size: 每页数量（默认 100，最大 500）
    """
    start_time = time.time()
    
    req_sn = request.args.get('req_sn')
    merchant_no = request.args.get('merchant_no')
    log_time = request.args.get('log_time')
    service = request.args.get('service')
    
    page = int(request.args.get('page', 1))
    page_size = min(int(request.args.get('page_size', 100)), 500)
    
    if not req_sn and not merchant_no:
        return jsonify({
            'success': False,
            'message': '请输入 REQ_SN 或商户号'
        }), 400
    
    if not log_time:
        return jsonify({
            'success': False,
            'message': '请输入日志时间（必填），格式：YYYYMMDDHH（如：2026040809）'
        }), 400
    
    # 默认服务
    svc = service or 'sft-aipg'
    
    # 步骤 1: 从 REQ_SN 索引找到 TraceID（仅 sft-aipg）
    step1_start = time.time()
    
    # 先尝试压缩索引（SQLite/MessagePack）
    trace_id = index_loader.get_reqsn_to_trace(svc, log_time, req_sn)
    
    # 如果没有，尝试当前小时索引（未压缩）
    if not trace_id:
        current_index = current_hour_manager.get_or_build(svc, log_time)
        if current_index:
            trace_id = current_index.get_trace_id(req_sn)
            print(f"[DEBUG] 使用当前小时索引")
    
    step1_time = (time.time() - step1_start) * 1000
    print(f"[DEBUG] 步骤 1 - REQ_SN → TraceID: {trace_id}, 耗时：{step1_time:.0f}ms")
    
    if not trace_id:
        return jsonify({
            'success': True,
            'logs': [],
            'trace_groups': [],
            'pagination': {'page': page, 'page_size': page_size, 'total_count': 0, 'total_pages': 0, 'has_next': False, 'has_prev': False},
            'total': 0,
            'trace_count': 0,
            'query_time_ms': round((time.time() - start_time) * 1000, 2)
        })
    
    # 步骤 2: 从 TraceID 索引找到日志位置
    step2_start = time.time()
    
    # 先尝试压缩索引
    entries = index_loader.get_trace_entries(svc, log_time, trace_id)
    
    # 如果没有，尝试当前小时索引
    if not entries and current_index:
        entries = current_index.get_entries(trace_id)
        print(f"[DEBUG] 使用当前小时索引找到 {len(entries)} 条")
    
    step2_time = (time.time() - step2_start) * 1000
    print(f"[DEBUG] 步骤 2 - TraceID → {len(entries)} 条日志，耗时：{step2_time:.0f}ms")
    
    if not entries:
        return jsonify({
            'success': True,
            'logs': [],
            'trace_groups': [],
            'pagination': {'page': page, 'page_size': page_size, 'total_count': 0, 'total_pages': 0, 'has_next': False, 'has_prev': False},
            'total': 0,
            'trace_count': 0,
            'query_time_ms': round((time.time() - start_time) * 1000, 2)
        })
    
    # 步骤 3: 流式读取日志内容
    step3_start = time.time()
    all_logs = log_reader.read_logs_by_entries(entries, svc)
    step3_time = (time.time() - step3_start) * 1000
    print(f"[DEBUG] 步骤 3 - 读取 {len(all_logs)} 条日志内容，耗时：{step3_time:.0f}ms")
    
    # 按时间排序
    all_logs.sort(key=lambda x: x.get('timestamp', ''))
    
    # 构建 trace_groups
    trace_groups = {trace_id: all_logs}
    
    query_time = (time.time() - start_time) * 1000
    
    print(f"[DEBUG] 总耗时：{query_time:.0f}ms (步骤 1: {step1_time:.0f}ms, 步骤 2: {step2_time:.0f}ms, 步骤 3: {step3_time:.0f}ms)")
    
    # 返回所有日志，保持与原 API 兼容
    return jsonify({
        'success': True,
        'logs': all_logs,
        'trace_groups': [{'trace_id': tid, 'log_count': len(logs)} for tid, logs in trace_groups.items()],
        'total': len(all_logs),
        'trace_count': len(trace_groups),
        'query_time_ms': round(query_time, 2)
    })


# 旧辅助函数已移至 query/index_loader.py 和 query/log_reader.py 模块


# ============================================
# 交易类型追踪查询 (TransactionTrace.vue)
# ============================================


# ============================================
# 交易类型追踪查询 (TransactionTrace.vue)
# ============================================

@app.route('/api/transaction-trace', methods=['GET'])
def transaction_trace():
    """
    交易类型日志追踪 - 根据交易类型配置的关联应用，依次展示每个应用的日志链路
    优化版：使用 SQLite 索引查询
    """
    start_time = time.time()
    
    transaction_type = request.args.get('transaction_type')
    req_sn = request.args.get('req_sn')
    log_time = request.args.get('log_time')
    
    if not transaction_type:
        return jsonify({
            'success': False,
            'message': '请选择交易类型'
        }), 400
    
    if not req_sn:
        return jsonify({
            'success': False,
            'message': '请输入 REQ_SN'
        }), 400
    
    if not log_time:
        return jsonify({
            'success': False,
            'message': '请输入日志时间（必填），格式：YYYYMMDDHH（如：2026040809）'
        }), 400
    
    # 获取交易类型配置
    types_config = load_transaction_types()
    type_info = types_config.get(transaction_type)
    
    if not type_info:
        return jsonify({
            'success': False,
            'message': f'未找到交易类型 {transaction_type} 的配置'
        }), 404
    
    apps = type_info.get('apps', [])
    if not apps:
        return jsonify({
            'success': False,
            'message': f'交易类型 {transaction_type} 未配置关联应用'
        }), 400
    
    # 步骤 1: 从 sft-aipg 的 REQ_SN 找到 TraceID（使用 SQLite）
    step1_start = time.time()
    trace_id = index_loader.get_reqsn_to_trace('sft-aipg', log_time, req_sn)
    
    # 如果没有，尝试当前小时索引
    if not trace_id:
        current_index = current_hour_manager.get_or_build('sft-aipg', log_time)
        if current_index:
            trace_id = current_index.get_trace_id(req_sn)
    
    step1_time = (time.time() - step1_start) * 1000
    print(f"[DEBUG] 步骤 1 - REQ_SN → TraceID: {trace_id}, 耗时：{step1_time:.0f}ms")
    
    if not trace_id:
        return jsonify({
            'success': True,
            'transaction_type': transaction_type,
            'transaction_name': type_info.get('name', transaction_type),
            'trace_groups': [],
            'total_logs': 0,
            'apps': apps,
            'message': '未找到相关日志',
            'query_time_ms': round((time.time() - start_time) * 1000, 2)
        })
    
    # 步骤 2: 查询所有应用的日志
    step2_start = time.time()
    trace_groups = []
    total_logs = 0
    max_logs_per_app = 50  # 每应用最多 50 条
    
    # 收集所有应用的日志
    app_logs = {app: [] for app in apps}
    
    for app in apps:
        # 从 SQLite 查询该应用的日志位置
        entries = index_loader.get_trace_entries(app, log_time, trace_id)
        
        # 限制数量
        entries = entries[:max_logs_per_app]
        
        # 流式读取日志内容
        if entries:
            logs = log_reader.read_logs_by_entries(entries, app)
            app_logs[app] = logs
            total_logs += len(logs)
            print(f"[DEBUG] {app}: {len(logs)} 条日志")
    
    step2_time = (time.time() - step2_start) * 1000
    print(f"[DEBUG] 步骤 2 - 查询所有应用，耗时：{step2_time:.0f}ms")
    
    # 按时间排序所有日志
    all_logs_sorted = []
    for app, logs in app_logs.items():
        for log in logs:
            log['service'] = app
            all_logs_sorted.append(log)
    
    all_logs_sorted.sort(key=lambda x: x.get('timestamp', ''))
    
    # 构建 trace_group
    first_timestamp = all_logs_sorted[0].get('timestamp', '') if all_logs_sorted else ''
    
    trace_groups = [{
        'trace_id': trace_id,
        'req_sn_count': 1,
        'total_logs': total_logs,
        'first_timestamp': first_timestamp,
        'app_logs': app_logs,
        'apps': apps
    }]
    
    query_time = (time.time() - start_time) * 1000
    
    return jsonify({
        'success': True,
        'transaction_type': transaction_type,
        'transaction_name': type_info.get('name', transaction_type),
        'trace_groups': trace_groups,
        'total_logs': total_logs,
        'apps': apps,
        'query_time_ms': round(query_time, 2)
    })


# ============================================
# 配置管理 API
# ============================================


# ============================================
# 配置管理 API
# ============================================

@app.route('/api/config/transaction-types', methods=['GET', 'POST'])
def config_transaction_types():
    """获取或更新交易类型配置"""
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'transaction_types': load_transaction_types()
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        # 提取 transaction_types 数据（兼容新旧格式）
        types_data = data.get('transaction_types', data)
        save_transaction_types(types_data)
        return jsonify({
            'success': True,
            'message': '交易类型配置已更新'
        })


@app.route('/api/config/log-dirs', methods=['GET', 'POST'])
def config_log_dirs():
    """获取或更新日志目录配置"""
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'log_dirs': load_log_dirs()
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        # 提取 log_dirs 数据（兼容新旧格式）
        log_dirs_data = data.get('log_dirs', data)
        save_log_dirs(log_dirs_data)
        return jsonify({
            'success': True,
            'message': '日志目录配置已更新'
        })


@app.route('/api/config/validate-path', methods=['POST'])
def validate_path():
    """验证路径是否存在"""
    data = request.get_json()
    path = data.get('path')
    
    if not path:
        return jsonify({
            'success': False,
            'message': '缺少路径参数'
        }), 400
    
    exists = os.path.exists(path)
    is_dir = os.path.isdir(path) if exists else False
    readable = os.access(path, os.R_OK) if exists else False
    
    file_count = 0
    if exists and is_dir:
        try:
            file_count = len(os.listdir(path))
        except:
            pass
    
    return jsonify({
        'success': exists and is_dir and readable,
        'exists': exists,
        'is_dir': is_dir,
        'readable': readable,
        'detail': f'目录包含 {file_count} 个文件' if exists and is_dir else ''
    })


# ============================================
# 基础数据 API
# ============================================

@app.route('/api/services', methods=['GET'])
def get_services():
    """获取服务列表"""
    services = []
    
    # 从日志目录获取
    if os.path.exists(CONFIG['LOG_BASE_DIR']):
        for item in os.listdir(CONFIG['LOG_BASE_DIR']):
            item_path = os.path.join(CONFIG['LOG_BASE_DIR'], item)
            if os.path.isdir(item_path):
                services.append(item)
    
    # 前端期望格式：{success: true, services: [...]}
    return jsonify({
        'success': True,
        'services': sorted(services)
    })


@app.route('/api/transaction-types', methods=['GET'])
def get_transaction_types():
    """获取交易类型列表"""
    types = load_transaction_types()
    return jsonify({
        'success': True,
        'transaction_types': types
    })


# ============================================
# 启动
# ============================================


# ============================================
# 新增：按 TraceID 查询（用于交易追踪）
# ============================================

@app.route('/api/query-by-traceid', methods=['GET'])
def query_by_traceid():
    """按 TraceID 查询日志 - 用于交易追踪"""
    start_time = time.time()
    
    trace_id = request.args.get('trace_id')
    log_time = request.args.get('log_time')
    service = request.args.get('service')
    
    if not trace_id or not log_time or not service:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    # 从索引文件快速查询
    service_dir = os.path.join(CONFIG['LOG_BASE_DIR'], service)
    if not os.path.exists(service_dir):
        return jsonify({'success': True, 'logs': [], 'total': 0, 'query_time_ms': 0})
    
    logs = []
    files_checked = 0
    
    for filename in sorted(os.listdir(service_dir)):
        if files_checked >= 2:
            break
        if not (filename.endswith('.log') or filename.endswith('.log.gz')):
            continue
        if log_time not in filename:
            continue
        
        file_path = os.path.join(service_dir, filename)
        index_file = file_path + '.index.json'
        
        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            trace_id_index = index_data.get('trace_id_index', {})
            if trace_id in trace_id_index:
                entries = trace_id_index[trace_id]
                for entry in entries[:50]:
                    if isinstance(entry, dict):
                        content = read_single_block_streaming(entry.get('file', ''), entry.get('block_num', 0))
                        logs.append({
                            'timestamp': entry.get('timestamp', ''),
                            'thread': '',
                            'trace_id': trace_id,
                            'level': entry.get('level', ''),
                            'service': service,
                            'content': content[:2000] if content else ''
                        })
        files_checked += 1
    
    query_time = (time.time() - start_time) * 1000
    
    return jsonify({
        'success': True,
        'logs': logs,
        'total': len(logs),
        'query_time_ms': round(query_time, 2)
    })


if __name__ == '__main__':
    print(f"""
╔═══════════════════════════════════════════════════════╗
║           sftlogapi v2.0 - 高性能日志查询              ║
╠═══════════════════════════════════════════════════════╣
║  启动配置：                                            ║
║  - 端口：{CONFIG['PORT']}                                        ║
║  - 调试：{CONFIG['DEBUG']}                                         ║
║  - 数据库：{CONFIG['DB_PATH']}  ║
║  - 日志目录：{CONFIG['LOG_BASE_DIR']}                                   ║
╚═══════════════════════════════════════════════════════╝
    """)
    
    app.run(host=CONFIG['HOST'], port=CONFIG['PORT'], debug=CONFIG['DEBUG'])
