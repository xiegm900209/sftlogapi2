# 智多星专用 API 接口文档

> 完整接口说明 · API Key 认证 · 返回完整日志

## 📋 接口列表

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/zdx/log-query` | GET | ✅ | 单日志查询 |
| `/api/zdx/transaction-trace` | GET | ✅ | 交易链路追踪 |
| `/api/zdx/transaction-analyze` | POST | ✅ | AI 智能分析 |

---

## 1️⃣ 单日志查询

**接口**: `GET /api/zdx/log-query`

**用途**: 根据 REQ_SN 查询单笔交易的完整日志

**请求**:

```bash
curl "http://172.16.2.164:8091/sftlogapi/api/zdx/log-query?req_sn=LX260408090024C80C82F3&log_time=2026040809&service=sft-aipg" \
  -H "Authorization: Bearer zhiduoxing-2026-secret-key"
```

**响应**:

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
      "content": "[2026-04-08 09:00:00.222][http-apr-8195-exec-2301][TCEsVt60][INFO][C02][sft][sft-aipg][]-[<?xml version=\"1.0\" encoding=\"GBK\"?><AIPG><INFO><TRX_CODE>310011</TRX_CODE><REQ_SN>LX260408090024C80C82F3</REQ_SN>...]"
    }
  ],
  "trace_groups": [{"trace_id": "TCEsVt60", "log_count": 22}],
  "total": 22,
  "trace_count": 1,
  "query_time_ms": 2.5
}
```

---

## 2️⃣ 交易链路追踪

**接口**: `GET /api/zdx/transaction-trace`

**用途**: 追踪完整交易链路，返回所有应用的完整日志

**请求**:

```bash
curl "http://172.16.2.164:8091/sftlogapi/api/zdx/transaction-trace?req_sn=LX260408090024C80C82F3&log_time=2026040809&transaction_type=310011" \
  -H "Authorization: Bearer zhiduoxing-2026-secret-key"
```

**响应**:

```json
{
  "success": true,
  "transaction_type": "310011",
  "transaction_name": "协议支付",
  "trace_groups": [{
    "trace_id": "TCEsVt60",
    "total_logs": 93,
    "app_logs": {
      "sft-aipg": [
        {
          "timestamp": "2026-04-08 09:00:00.222",
          "level": "INFO",
          "service": "sft-aipg",
          "content": "完整的日志内容（包含 XML、异常堆栈等）...",
          "thread": "http-apr-8195-exec-2301"
        },
        ... 最多 100 条
      ],
      "sft-trxcharge": [...],
      "sft-merapi": [...],
      "sft-chnlagent": [...],
      "sft-rtresult-http": [...],
      "sft-rtresult-listener": [...]
    },
    "apps": ["sft-aipg", "sft-trxcharge", "sft-merapi", "sft-chnlagent", "sft-rtresult-http", "sft-rtresult-listener"]
  }],
  "total_logs": 93,
  "query_time_ms": 15.3
}
```

---

## 3️⃣ AI 智能分析

**接口**: `POST /api/zdx/transaction-analyze`

**用途**: AI 智能分析交易，返回结构化分析结果 + 可选完整日志

**请求**:

```bash
curl -X POST "http://172.16.2.164:8091/sftlogapi/api/zdx/transaction-analyze" \
  -H "Authorization: Bearer zhiduoxing-2026-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "req_sn": "LX260408090024C80C82F3",
    "log_time": "2026040809",
    "transaction_type": "310011",
    "analysis_type": "full"
  }'
```

**analysis_type 说明**:
- `summary` - 只返回摘要，不返回完整日志
- `full` - 返回完整日志（默认）

**响应**:

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
      "query_time_ms": 25.3
    },
    "extracted_info": {
      "amount": "100.00",
      "merchant_no": "200604000011967",
      "bank_name": "中国银行广州天文苑支行",
      "error_message": null
    },
    "flow": [
      {
        "service": "sft-aipg",
        "log_count": 22,
        "first_timestamp": "2026-04-08 09:00:00.222",
        "last_timestamp": "2026-04-08 09:00:00.267",
        "has_error": false,
        "logs": [...]  // 完整日志（analysis_type=full 时返回）
      },
      {
        "service": "sft-trxcharge",
        "log_count": 41,
        "first_timestamp": "2026-04-08 09:00:00.268",
        "last_timestamp": "2026-04-08 09:00:00.588",
        "has_error": false,
        "logs": [...]
      },
      ... 所有应用
    ],
    "issues": [],
    "suggestions": ["交易正常，无需处理"]
  },
  "query_time_ms": 25.3
}
```

---

## 🔐 认证示例

### Python

```python
import requests

API_KEY = "zhiduoxing-2026-secret-key"
BASE_URL = "http://172.16.2.164:8091/sftlogapi/api/zdx"

headers = {"Authorization": f"Bearer {API_KEY}"}

# 查询交易
resp = requests.get(f"{BASE_URL}/log-query", headers=headers, params={
    "req_sn": "LX260408090024C80C82F3",
    "log_time": "2026040809"
})
result = resp.json()

# 追踪链路
resp = requests.get(f"{BASE_URL}/transaction-trace", headers=headers, params={
    "req_sn": "LX260408090024C80C82F3",
    "log_time": "2026040809",
    "transaction_type": "310011"
})
trace = resp.json()

# AI 分析
resp = requests.post(f"{BASE_URL}/transaction-analyze", headers=headers, json={
    "req_sn": "LX260408090024C80C82F3",
    "log_time": "2026040809",
    "transaction_type": "310011",
    "analysis_type": "full"
})
analysis = resp.json()
```

---

## 📊 错误响应

**认证失败**:
```json
{
  "success": false,
  "error_code": 401,
  "message": "认证失败：无效的 API Key"
}
```

**参数错误**:
```json
{
  "success": false,
  "error_code": 400,
  "message": "缺少必填参数：req_sn, log_time"
}
```

**未找到日志**:
```json
{
  "success": true,
  "analysis": {
    "summary": {
      "status": "未找到",
      "req_sn": "LX260408090024C80C82F3",
      "message": "未找到相关日志"
    }
  }
}
```

---

## 🔧 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_KEY` | `zhiduoxing-2026-secret-key` | API Key |
| `ENABLE_AUTH` | `false` | 是否启用认证 |

### Docker 启动

```bash
docker run -d \
  --name sftlogapi-v2 \
  -p 5001:5000 \
  -e API_KEY=zhiduoxing-2026-secret-key \
  -e ENABLE_AUTH=true \
  ...
```

---

## 📞 技术支持

- **接口地址**: http://172.16.2.164:8091/sftlogapi/api/zdx/*
- **文档地址**: http://172.16.2.164:8091/sftlogapi/
- **GitHub**: https://github.com/xiegm900209/sftlogapi2

---

**版本**: 2.0.0  
**更新时间**: 2026-04-12  
**作者**: xiegm900209
