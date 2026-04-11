#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智多星 AI - sftlogapi v2 客户端
模拟智多星 AI 助手，通过自然语言理解调用 sftlogapi 接口
"""

import re
import json
import requests
from datetime import datetime


class ZhiduoxingLogClient:
    """智多星日志查询客户端"""
    
    def __init__(self, 
                 base_url: str = "http://172.16.2.164:8091/sftlogapi/api/zdx",
                 api_key: str = "zhiduoxing-2026-secret-key"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def parse_user_query(self, user_input: str):
        """解析用户自然语言查询"""
        result = {
            "intent": "unknown",
            "req_sn": None,
            "log_time": None,
            "transaction_type": None,
            "service": None,
        }
        
        # 1. 提取时间（优先，避免 REQ_SN 干扰）
        # 匹配"时间是 XXXX"
        time_match = re.search(r'时间是 (\d+)', user_input)
        if time_match:
            time_str = time_match.group(1)
            if len(time_str) == 10:
                result["log_time"] = time_str
            elif len(time_str) == 8:
                result["log_time"] = time_str + "09"
        
        # 2. 提取 REQ_SN
        req_sn_match = re.search(r'交易 [：:\s]*([A-Za-z0-9\-]+)', user_input, re.IGNORECASE)
        if req_sn_match:
            result["req_sn"] = req_sn_match.group(1)
        
        # 3. 提取服务名
        service_match = re.search(r'(sft-[a-z]+)', user_input, re.IGNORECASE)
        if service_match:
            result["service"] = service_match.group(1)
        
        # 4. 判断意图
        if result["req_sn"] and result["log_time"]:
            if "链路" in user_input or "追踪" in user_input:
                result["intent"] = "trace"
            elif "分析" in user_input or "为什么" in user_input:
                result["intent"] = "analyze"
            else:
                result["intent"] = "query"
        elif result["req_sn"]:
            result["intent"] = "query"
            result["log_time"] = datetime.now().strftime('%Y%m%d%H')
        
        return result
    
    def query_logs(self, req_sn, log_time, service="sft-aipg"):
        """查询单日志"""
        resp = requests.get(
            f"{self.base_url}/log-query",
            headers=self.headers,
            params={"req_sn": req_sn, "log_time": log_time, "service": service},
            timeout=30
        )
        return resp.json()
    
    def trace_transaction(self, req_sn, log_time, transaction_type="310011"):
        """追踪交易链路"""
        resp = requests.get(
            f"{self.base_url}/transaction-trace",
            headers=self.headers,
            params={"req_sn": req_sn, "log_time": log_time, "transaction_type": transaction_type},
            timeout=60
        )
        return resp.json()
    
    def analyze_transaction(self, req_sn, log_time, transaction_type=None):
        """AI 智能分析"""
        resp = requests.post(
            f"{self.base_url}/transaction-analyze",
            headers=self.headers,
            json={"req_sn": req_sn, "log_time": log_time, "transaction_type": transaction_type, "analysis_type": "full"},
            timeout=60
        )
        return resp.json()
    
    def format_response(self, parsed, api_result):
        """格式化 API 响应为智多星回复"""
        intent = parsed.get("intent")
        
        if intent == "query":
            return self._format_query(parsed, api_result)
        elif intent == "trace":
            return self._format_trace(parsed, api_result)
        elif intent == "analyze":
            return self._format_analyze(parsed, api_result)
        else:
            return "抱歉，请提供 REQ_SN 和日志时间，例如：帮我查一下交易 LX260408090024C80C82F3，时间是 2026040809"
    
    def _format_query(self, parsed, api_result):
        """格式化单日志查询响应"""
        if not api_result.get("success"):
            return f"❌ 查询失败：{api_result.get('message', '未知错误')}"
        
        logs = api_result.get("logs", [])
        total = api_result.get("total", 0)
        
        if total == 0:
            return "⚠️ 未找到相关日志，请检查 REQ_SN 和日志时间是否正确。"
        
        reply = f"""✅ 已为您找到 **{total}** 条日志

**关键信息：**
- 📋 REQ_SN: `{parsed['req_sn']}`
- ⏰ 日志时间：{parsed['log_time']}
- 🏷️ TraceID: `{logs[0].get('trace_id', 'N/A')}`
- 🏪 服务：{parsed.get('service', 'sft-aipg')}

**日志内容（前 5 条）：**
"""
        for i, log in enumerate(logs[:5], 1):
            ts = log.get('timestamp', 'N/A')
            level = log.get('level', 'N/A')
            content = log.get('content', '')[:200]
            reply += f"\n{i}. [{ts}] [{level}]\n   {content}..."
        
        reply += f"\n\n需要我帮您分析这笔交易的完整链路吗？😊"
        return reply
    
    def _format_trace(self, parsed, api_result):
        """格式化交易链路追踪响应"""
        if not api_result.get("success"):
            return f"❌ 追踪失败：{api_result.get('message', '未知错误')}"
        
        trace_groups = api_result.get("trace_groups", [])
        total_logs = api_result.get("total_logs", 0)
        apps = api_result.get("apps", [])
        
        if total_logs == 0:
            return "⚠️ 未找到交易链路，请检查 REQ_SN 和日志时间是否正确。"
        
        group = trace_groups[0] if trace_groups else {}
        trace_id = group.get("trace_id", "N/A")
        app_logs = group.get("app_logs", {})
        
        reply = f"""✅ 已为您追踪到完整的交易链路

**关键信息：**
- 📋 REQ_SN: `{parsed['req_sn']}`
- ⏰ 日志时间：{parsed['log_time']}
- 🏷️ TraceID: `{trace_id}`
- 📊 总日志数：{total_logs} 条
- 🏢 涉及应用：{len(apps)} 个

**交易流程：**
"""
        for i, app in enumerate(apps, 1):
            logs = app_logs.get(app, [])
            count = len(logs)
            if count > 0:
                reply += f"\n{i}. ✅ **{app}** ({count} 条日志)"
                if logs:
                    content = logs[0].get('content', '')[:150]
                    reply += f"\n   摘要：{content}..."
            else:
                reply += f"\n{i}. ⚪ **{app}** - 无日志"
        
        reply += f"\n\n需要我帮您分析交易状态吗？😊"
        return reply
    
    def _format_analyze(self, parsed, api_result):
        """格式化 AI 智能分析响应"""
        if not api_result.get("success"):
            return f"❌ 分析失败：{api_result.get('message', '未知错误')}"
        
        analysis = api_result.get("analysis", {})
        summary = analysis.get("summary", {})
        extracted = analysis.get("extracted_info", {})
        flow = analysis.get("flow", [])
        issues = analysis.get("issues", [])
        suggestions = analysis.get("suggestions", [])
        
        status_emoji = "✅" if summary.get("status") == "成功" else "⚠️"
        
        reply = f"""{status_emoji} **交易分析报告**

**基本信息：**
- 📋 REQ_SN: `{summary.get('req_sn', 'N/A')}`
- 🏷️ TraceID: `{summary.get('trace_id', 'N/A')}`
- ✅ 交易状态：{summary.get('status', 'N/A')}
- 📊 日志总数：{summary.get('total_logs', 0)} 条
- 🏢 涉及服务：{summary.get('services_count', 0)} 个
- ⏱️ 总耗时：约 {summary.get('total_time_ms', 0)}ms
"""
        if extracted:
            reply += "\n**提取信息：**"
            if extracted.get('amount'):
                reply += f"\n- 💰 金额：{extracted['amount']} 元"
            if extracted.get('merchant_no'):
                reply += f"\n- 🏪 商户号：{extracted['merchant_no']}"
            if extracted.get('error_message'):
                reply += f"\n- ⚠️ 错误：{extracted['error_message']}"
        
        if flow:
            reply += "\n\n**交易流程：**"
            for i, step in enumerate(flow, 1):
                emoji = "❌" if step.get('has_error') else "✅"
                reply += f"\n{i}. {emoji} **{step['service']}** ({step['log_count']} 条)"
        
        if issues:
            reply += "\n\n**发现问题：**"
            for issue in issues:
                reply += f"\n- ⚠️ {issue}"
        
        if suggestions:
            reply += "\n\n**建议：**"
            for suggestion in suggestions:
                reply += f"\n- 💡 {suggestion}"
        
        reply += "\n\n需要我查看详细日志吗？😊"
        return reply
    
    def chat(self, user_input: str) -> str:
        """智多星聊天接口 - 主入口"""
        print(f"\n🤖 智多星收到：{user_input}\n")
        
        # 1. 解析意图
        parsed = self.parse_user_query(user_input)
        print(f"🔍 解析结果：{json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
        
        # 2. 调用 API
        if parsed["intent"] == "unknown":
            return self.format_response(parsed, {"success": False})
        
        elif parsed["intent"] == "query":
            print("📝 调用单日志查询接口...")
            api_result = self.query_logs(parsed["req_sn"], parsed["log_time"], parsed.get("service"))
        
        elif parsed["intent"] == "trace":
            print("🔗 调用交易链路追踪接口...")
            api_result = self.trace_transaction(parsed["req_sn"], parsed["log_time"])
        
        elif parsed["intent"] == "analyze":
            print("🤖 调用 AI 智能分析接口...")
            api_result = self.analyze_transaction(parsed["req_sn"], parsed["log_time"])
        
        else:
            return self.format_response(parsed, {"success": False})
        
        # 3. 格式化响应
        print("💬 生成回复...\n")
        return self.format_response(parsed, api_result)


if __name__ == "__main__":
    print("="*80)
    print("🤖 智多星 AI - sftlogapi v2 接口调用演示")
    print("="*80)
    
    zdx = ZhiduoxingLogClient()
    
    # 测试用例
    test_input = "帮我查一下交易 2widscma-1491361962608050176，时间是 2026040809"
    print(f"\n用户问：{test_input}\n")
    
    reply = zdx.chat(test_input)
    print(reply)
