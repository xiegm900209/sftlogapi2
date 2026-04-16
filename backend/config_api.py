# -*- coding: utf-8 -*-
"""
配置管理 API 扩展
支持增删改查和导出功能
"""

import os
import json
import shutil
from datetime import datetime
from flask import jsonify, request

# 配置文件路径
CONFIG_DIR = os.environ.get('CONFIG_DIR', '/app/config')
LOG_DIRS_FILE = os.path.join(CONFIG_DIR, 'log_dirs.json')
SERVICES_FILE = os.path.join(CONFIG_DIR, 'services.json')
TRANSACTION_TYPES_FILE = os.path.join(CONFIG_DIR, 'transaction_types.json')

# 本地开发环境路径映射
DEV_PATH_MAP = {
    '/root/sft/sftlogapi-v2/config/log_dirs.json': LOG_DIRS_FILE,
    '/root/sft/sftlogapi-v2/config/services.json': SERVICES_FILE,
    '/root/sft/sftlogapi-v2/config/transaction_types.json': TRANSACTION_TYPES_FILE,
}


def load_json_file(filepath):
    """加载 JSON 文件"""
    # 尝试本地开发路径
    if filepath.startswith('/root/sft/'):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    # 尝试容器内路径
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json_file(filepath, data):
    """保存 JSON 文件"""
    # 尝试本地开发路径
    if filepath.startswith('/root/sft/'):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    # 尝试容器内路径
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def check_path_exists(path):
    """检查路径是否存在"""
    # 路径转换：宿主机路径 -> 容器内路径
    container_path = path
    if path.startswith('/root/sft/testlogs'):
        container_path = path.replace('/root/sft/testlogs', '/data/logs')
    
    exists = os.path.exists(container_path)
    is_dir = os.path.isdir(container_path) if exists else False
    readable = os.access(container_path, os.R_OK) if exists else False
    
    file_count = 0
    if exists and is_dir:
        try:
            file_count = len(os.listdir(container_path))
        except:
            pass
    
    return {
        'exists': exists,
        'is_dir': is_dir,
        'readable': readable,
        'file_count': file_count,
        'checked_path': container_path
    }


# ============================================
# 日志目录配置 API
# ============================================

def get_log_dirs():
    """获取日志目录配置"""
    data = load_json_file(LOG_DIRS_FILE)
    return data if isinstance(data, dict) else {}


def save_log_dirs(data):
    """保存日志目录配置"""
    return save_json_file(LOG_DIRS_FILE, data)


def add_log_dir(service, path):
    """添加日志目录"""
    data = get_log_dirs()
    data[service] = path
    save_log_dirs(data)
    return True


def update_log_dir(service, new_path):
    """更新日志目录"""
    data = get_log_dirs()
    if service in data:
        data[service] = new_path
        save_log_dirs(data)
        return True
    return False


def delete_log_dir(service):
    """删除日志目录"""
    data = get_log_dirs()
    if service in data:
        del data[service]
        save_log_dirs(data)
        return True
    return False


def export_log_dirs():
    """导出日志目录配置"""
    data = get_log_dirs()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'log_dirs_export_{timestamp}.json'
    return filename, data


def batch_check_paths(paths):
    """批量检查路径"""
    results = {}
    for service, path in paths.items():
        results[service] = {
            'path': path,
            **check_path_exists(path)
        }
    return results


# ============================================
# 服务配置 API
# ============================================

def get_services():
    """获取服务配置"""
    data = load_json_file(SERVICES_FILE)
    return data if isinstance(data, dict) else {'services': []}


def save_services(data):
    """保存服务配置"""
    return save_json_file(SERVICES_FILE, data)


def add_service(service_name):
    """添加服务"""
    data = get_services()
    if 'services' not in data:
        data['services'] = []
    if service_name not in data['services']:
        data['services'].append(service_name)
        save_services(data)
        return True
    return False


def update_service(old_name, new_name):
    """更新服务名称"""
    data = get_services()
    if 'services' not in data:
        return False
    if old_name in data['services']:
        idx = data['services'].index(old_name)
        data['services'][idx] = new_name
        save_services(data)
        return True
    return False


def delete_service(service_name):
    """删除服务"""
    data = get_services()
    if 'services' not in data:
        return False
    if service_name in data['services']:
        data['services'].remove(service_name)
        save_services(data)
        return True
    return False


def export_services():
    """导出服务配置"""
    data = get_services()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'services_export_{timestamp}.json'
    return filename, data


# ============================================
# 交易类型配置 API
# ============================================

def get_transaction_types():
    """获取交易类型配置"""
    data = load_json_file(TRANSACTION_TYPES_FILE)
    return data if isinstance(data, dict) else {}


def save_transaction_types(data):
    """保存交易类型配置"""
    return save_json_file(TRANSACTION_TYPES_FILE, data)


def add_transaction_type(code, name, apps=None):
    """添加交易类型"""
    data = get_transaction_types()
    data[code] = {
        'name': name,
        'apps': apps or []
    }
    save_transaction_types(data)
    return True


def update_transaction_type(code, name=None, apps=None):
    """更新交易类型"""
    data = get_transaction_types()
    if code in data:
        if name:
            data[code]['name'] = name
        if apps is not None:
            data[code]['apps'] = apps
        save_transaction_types(data)
        return True
    return False


def delete_transaction_type(code):
    """删除交易类型"""
    data = get_transaction_types()
    if code in data:
        del data[code]
        save_transaction_types(data)
        return True
    return False


def export_transaction_types():
    """导出交易类型配置"""
    data = get_transaction_types()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'transaction_types_export_{timestamp}.json'
    return filename, data
