# sftlogapi v2 - 智多星 AI 接口对接文档

> 为智多星 AI 助手提供日志查询和交易链路追踪能力

## 📖 文档概述

本文档面向智多星 AI 开发者，说明如何调用 sftlogapi v2 的 API 接口，实现交易日志查询、链路追踪、问题分析等功能。

---

## 🎯 接口能力

智多星可通过以下接口实现：

| 能力 | 接口 | 认证 | 说明 |
|------|------|------|------|
| 🔍 交易查询 | `/api/zdx/log-query` | ✅ | 根据 REQ_SN 查询日志（返回完整日志） |
| 🔗 链路追踪 | `/api/zdx/transaction-trace` | ✅ | 追踪完整交易链路（返回完整日志） |
| 📊 AI 分析 | `/api/zdx/transaction-analyze` | ✅ | AI 智能分析交易（结构化 + 完整日志） |
| 📋 服务列表 | `/api/services` | ❌ | 获取所有服务 |
| ⚙️ 配置管理 | `/api/config/*` | ❌ | 管理配置信息 |

---

## 🔐 认证方式

### 方式 1: API Key（推荐，默认启用）

**请求头**:
```http
Authorization: Bearer zhiduoxing-2026-secret-key
```

**URL 参数**:
```
?api_key=zhiduoxing-2026-secret-key
```

**自定义 API Key**:
```bash
# Docker 环境变量
-e API_KEY=your-custom-api-key
-e ENABLE_AUTH=true
```

### 方式 2: 关闭认证（内网测试）

```bash
-e ENABLE_AUTH=false
```

### 方式 3: IP 白名单

将智多星服务器 IP 加入 Nginx 白名单，无需认证。

---

## 📡 接口详情

### 1. 交易日志查询

**接口**: `GET /api/log-query`

**用途**: 根据 REQ_SN 查询单笔交易的日志

**请求参数**:

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| req_sn | string | 是 | 交易序列号 | `LX260408090024C80C82F3` |
| log_time | string | 是 | 日志时间 (YYYYMMDDHH) | `2026040809` |
| service | string | 否 | 服务名称 | `sft-aipg` |
| page | int | 否 | 页码 (默认 1) | `1` |
| page_size | int | 否 | 每页数量 (默认 100) | `100` |

**请求示例**:

```bash
curl "http://172.16.2.164:8091/sftlogapi/api/log-query?req_sn=LX260408090024C80C82F3&log_time=2026040809&service=sft-aipg"
```

**响应示例**:

```json
{
  "success": true,
  "logs": [
    {
      "timestamp": "2026-04-08 09:00:00.222",
      "thread": "http-apr-8195-exec-2301",
      "trace_id": "TCEsVt60",
      "level": "INFO",
      "service": "sft-aipg",
      "content": "[2026-04-08 09:00:00.222]...[<?xml version=\"1.0\" encoding=\"GBK\"?><AIPG><INFO><TRX_CODE>310011</TRX_CODE>...]"
    }
  ],
  "trace_groups": [
    {"trace_id": "TCEsVt60", "log_count": 22}
  ],
  "total": 22,
  "trace_count": 1,
  "query_time_ms": 2.5
}
```

---

### 2. 交易链路追踪

**接口**: `GET /api/transaction-trace`

**用途**: 追踪完整交易链路，返回所有应用的日志

**请求参数**:

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| req_sn | string | 是 | 交易序列号 | `LX260408090024C80C82F3` |
| log_time | string | 是 | 日志时间 (YYYYMMDDHH) | `2026040809` |
| transaction_type | string | 是 | 交易类型代码 | `310011` |

**请求示例**:

```bash
curl "http://172.16.2.164:8091/sftlogapi/api/transaction-trace?req_sn=LX260408090024C80C82F3&log_time=2026040809&transaction_type=310011"
```

**响应示例**:

```json
{
  "success": true,
  "transaction_type": "310011",
  "transaction_name": "协议支付",
  "trace_groups": [
    {
      "trace_id": "TCEsVt60",
      "req_sn_count": 1,
      "total_logs": 93,
      "first_timestamp": "2026-04-08 09:00:00.222",
      "app_logs": {
        "sft-aipg": [
          {
            "timestamp": "2026-04-08 09:00:00.222",
            "level": "INFO",
            "content": "..."
          }
        ],
        "sft-trxcharge": [...],
        "sft-merapi": [...],
        "sft-chnlagent": [...],
        "sft-rtresult-http": [...],
        "sft-rtresult-listener": [...]
      },
      "apps": [
        "sft-aipg",
        "sft-trxcharge",
        "sft-merapi",
        "sft-chnlagent",
        "sft-rtresult-http",
        "sft-rtresult-listener"
      ]
    }
  ],
  "total_logs": 93,
  "apps": [...],
  "query_time_ms": 15.3
}
```

---

### 3. AI 智能分析（新增）

**接口**: `POST /api/transaction-analyze`

**用途**: AI 智能分析交易，返回结构化分析结果

**请求参数**:

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| req_sn | string | 是 | 交易序列号 | `LX260408090024C80C82F3` |
| log_time | string | 是 | 日志时间 | `2026040809` |
| transaction_type | string | 否 | 交易类型 | `310011` |
| analysis_type | string | 否 | 分析类型 | `summary/error/performance` |

**请求示例**:

```bash
curl -X POST "http://172.16.2.164:8091/sftlogapi/api/transaction-analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "req_sn": "LX260408090024C80C82F3",
    "log_time": "2026040809",
    "transaction_type": "310011",
    "analysis_type": "summary"
  }'
```

**响应示例**:

```json
{
  "success": true,
  "analysis": {
    "summary": {
      "status": "成功",
      "req_sn": "LX260408090024C80C82F3",
      "trace_id": "TCEsVt60",
      "transaction_type": "310011",
      "transaction_name": "协议支付",
      "total_logs": 93,
      "services_count": 6,
      "total_time_ms": 642,
      "start_time": "2026-04-08 09:00:00.222",
      "end_time": "2026-04-08 09:00:00.864"
    },
    "extracted_info": {
      "amount": "100.00",
      "currency": "CNY",
      "merchant_no": "200604000011967",
      "bank_name": "中国银行广州天文苑支行",
      "error_message": null
    },
    "flow": [
      {
        "service": "sft-aipg",
        "log_count": 22,
        "description": "接收请求，验证商户配置",
        "time_ms": 45,
        "status": "success"
      },
      {
        "service": "sft-trxcharge",
        "log_count": 41,
        "description": "交易处理，计费，风控检查",
        "time_ms": 320,
        "status": "success"
      },
      {
        "service": "sft-merapi",
        "log_count": 6,
        "description": "商户 API 处理",
        "time_ms": 85,
        "status": "success"
      },
      {
        "service": "sft-chnlagent",
        "log_count": 8,
        "description": "渠道代理转发",
        "time_ms": 120,
        "status": "success"
      },
      {
        "service": "sft-rtresult-http",
        "log_count": 2,
        "description": "实时结果返回",
        "time_ms": 35,
        "status": "success"
      },
      {
        "service": "sft-rtresult-listener",
        "log_count": 14,
        "description": "结果通知，日志分析",
        "time_ms": 37,
        "status": "success"
      }
    ],
    "issues": [],
    "suggestions": []
  }
}
```

---

### 4. 获取服务列表

**接口**: `GET /api/services`

**用途**: 获取所有可用的服务名称

**响应示例**:

```json
{
  "success": true,
  "services": [
    "sft-aipg",
    "sft-merapi",
    "sft-trxcharge",
    "sft-chnlagent",
    ...
  ]
}
```

---

### 5. 获取交易类型列表

**接口**: `GET /api/transaction-types`

**用途**: 获取所有交易类型配置

**响应示例**:

```json
{
  "success": true,
  "transaction_types": {
    "310011": {
      "name": "协议支付",
      "apps": ["sft-aipg", "sft-merapi", ...]
    },
    "100001": {
      "name": "代收",
      "apps": [...]
    }
  }
}
```

---

## 🤖 智多星集成指南

### 1. Python 调用示例

```python
import requests
from datetime import datetime

class SFTLogAPI:
    """sftlogapi v2 客户端"""
    
    def __init__(self, base_url="http://172.16.2.164:8091/sftlogapi/api"):
        self.base_url = base_url
    
    def query_transaction(self, req_sn, log_time=None):
        """查询交易日志"""
        if not log_time:
            log_time = datetime.now().strftime('%Y%m%d%H')
        
        resp = requests.get(f"{self.base_url}/log-query", params={
            'req_sn': req_sn,
            'log_time': log_time
        })
        return resp.json()
    
    def trace_transaction(self, req_sn, transaction_type, log_time=None):
        """追踪交易链路"""
        if not log_time:
            log_time = datetime.now().strftime('%Y%m%d%H')
        
        resp = requests.get(f"{self.base_url}/transaction-trace", params={
            'req_sn': req_sn,
            'log_time': log_time,
            'transaction_type': transaction_type
        })
        return resp.json()
    
    def analyze_transaction(self, req_sn, transaction_type=None, log_time=None):
        """AI 智能分析交易"""
        if not log_time:
            log_time = datetime.now().strftime('%Y%m%d%H')
        
        resp = requests.post(f"{self.base_url}/transaction-analyze", json={
            'req_sn': req_sn,
            'log_time': log_time,
            'transaction_type': transaction_type,
            'analysis_type': 'summary'
        })
        return resp.json()


# 使用示例
api = SFTLogAPI()

# 查询交易
result = api.query_transaction("LX260408090024C80C82F3", "2026040809")
print(f"找到 {result['total']} 条日志")

# 追踪链路
trace = api.trace_transaction("LX260408090024C80C82F3", "310011", "2026040809")
print(f"涉及 {len(trace['apps'])} 个应用，共 {trace['total_logs']} 条日志")

# AI 分析
analysis = api.analyze_transaction("LX260408090024C80C82F3", "310011", "2026040809")
print(f"交易状态：{analysis['analysis']['summary']['status']}")
```

---

### 2. 智多星回复模板

```python
def format_transaction_response(analysis):
    """格式化交易分析结果为智多星回复"""
    
    summary = analysis['analysis']['summary']
    flow = analysis['analysis']['flow']
    issues = analysis['analysis']['issues']
    
    # 构建回复
    reply = f"""您好！已为您找到这笔 {summary['transaction_name']} ({summary['transaction_type']}) 交易的完整日志，共 {summary['total_logs']} 条，涉及 {summary['services_count']} 个服务。

**关键信息：**
- ✅ 交易状态：{summary['status']}
- 📋 REQ_SN: `{summary['req_sn']}`
- 🏷️ TraceID: `{summary['trace_id']}`
- 💰 交易金额：{analysis['analysis']['extracted_info'].get('amount', 'N/A')} 元
- 🏪 商户号：{analysis['analysis']['extracted_info'].get('merchant_no', 'N/A')}
- 🏦 银行：{analysis['analysis']['extracted_info'].get('bank_name', 'N/A')}
- ⏱️ 总耗时：约 {summary['total_time_ms']}ms

**交易流程：**
"""
    
    for i, step in enumerate(flow, 1):
        reply += f"\n{i}. **{step['service']}** ({step['log_count']} 条) - {step['description']}"
    
    if issues:
        reply += "\n\n**发现问题：**\n"
        for issue in issues:
            reply += f"- ⚠️ {issue}\n"
    
    reply += "\n\n所有日志已按服务分组完整打印，您可以查看上面的详细信息！"
    reply += "\n\n需要我帮您分析某个特定服务的日志，或者查询其他交易吗？😊"
    
    return reply
```

---

### 3. 智多星对话示例

**用户**: 帮我查一下交易 LX260408090024C80C82F3 的日志

**智多星**: 
```
您好！已为您找到这笔 协议支付 (310011) 交易的完整日志，共 93 条，涉及 6 个服务。

关键信息：
- ✅ 交易状态：成功
- 📋 REQ_SN: LX260408090024C80C82F3
- 🏷️ TraceID: TCEsVt60
- 💰 交易金额：100 元
- 🏪 商户号：200604000011967
- 🏦 银行：中国银行广州天文苑支行
- ⏱️ 总耗时：约 642ms

交易流程：
1. sft-aipg (22 条) - 接收请求，验证商户配置
2. sft-trxcharge (41 条) - 交易处理，计费，风控检查
3. sft-merapi (6 条) - 商户 API 处理
4. sft-chnlagent (8 条) - 渠道代理转发
5. sft-rtresult-http (2 条) - 实时结果返回
6. sft-rtresult-listener (14 条) - 结果通知，日志分析

所有日志已按服务分组完整打印，您可以查看上面的详细信息！

需要我帮您分析某个特定服务的日志，或者查询其他交易吗？😊
```

---

## 📊 错误码说明

| 错误码 | HTTP 状态 | 说明 | 处理建议 |
|--------|----------|------|---------|
| 0 | 200 | 成功 | - |
| 400 | 400 | 请求参数错误 | 检查必填参数 |
| 404 | 404 | 未找到日志 | 检查 REQ_SN 和时间 |
| 500 | 500 | 服务器错误 | 联系运维 |
| 503 | 503 | 服务不可用 | 稍后重试 |

**错误响应示例**:

```json
{
  "success": false,
  "error_code": 404,
  "message": "未找到相关日志，请检查 REQ_SN 和日志时间是否正确"
}
```

---

## 🔧 使用场景

### 场景 1: 用户查询交易状态

```python
# 用户：我的交易成功了吗？
analysis = api.analyze_transaction(req_sn, "310011")
status = analysis['analysis']['summary']['status']
if status == '成功':
    reply = "✅ 您的交易已成功处理！"
else:
    reply = f"⚠️ 您的交易状态：{status}，请稍后重试或联系客服"
```

### 场景 2: 定位交易失败原因

```python
# 用户：交易为什么失败了？
analysis = api.analyze_transaction(req_sn, "310011")
issues = analysis['analysis']['issues']
if issues:
    reply = "交易失败原因：\n" + "\n".join(issues)
else:
    reply = "正在分析日志，请稍候..."
```

### 场景 3: 性能分析

```python
# 用户：这笔交易耗时多久？
analysis = api.analyze_transaction(req_sn, "310011")
flow = analysis['analysis']['flow']
slowest = max(flow, key=lambda x: x['time_ms'])
reply = f"总耗时 {analysis['analysis']['summary']['total_time_ms']}ms，最慢的环节是 {slowest['service']} ({slowest['time_ms']}ms)"
```

---

## 📞 技术支持

- **接口地址**: http://172.16.2.164:8091/sftlogapi/api
- **文档地址**: http://172.16.2.164:8091/sftlogapi/
- **GitHub**: https://github.com/xiegm900209/sftlogapi2

---

**版本**: 2.0.0  
**更新时间**: 2026-04-12  
**作者**: xiegm900209
