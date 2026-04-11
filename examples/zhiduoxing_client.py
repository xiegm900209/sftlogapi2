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
from typing import Optional, Dict, Any


class ZhiduoxingLogClient:
    """智多星日志查询客户端"""
    
    def __init__(self, 
                 base_url: str = "http://172.16.2.164:8091/sftlogapi/api/zdx",
                 api_key: str = "zhiduoxing-2026-secret-key"):
        """
        初始化客户端
        
        Args:
            base_url: API 基础 URL
            api_key: API Key
        """
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 交易类型映射
        self.transaction_types = {
            "协议支付": "310011",
            "代收": "100001",
            "代付": "100002",
            "实时转账": "100007",
            "实时收款": "100011",
            "实时付款": "100014",
            "交易查询": "200004"
        }
    
    def parse_user_query(self, user_input: str) -> Dict[str, Any]:
        """
        解析用户自然语言查询
        
        Args:
            user_input: 用户输入的自然语言
        
        Returns:
            解析后的参数字典
        """
        result = {
            "intent": "unknown",  # 查询意图
            "req_sn": None,
            "log_time": None,
            "transaction_type": None,
            "service": None,
            "analysis_type": "full"
        }
        
        # 提取时间（支持多种格式）- 先提取时间，避免 REQ_SN 中的数字干扰
        # 优先匹配"时间是 XXXX"这种明确格式
        explicit_time = re.search(r'时间 [是：=]\s*(\d+)', user_input)
        if explicit_time:
            time_str = explicit_time.group(1)
            if len(time_str) == 10:
                result["log_time"] = time_str
            elif len(time_str) == 8:
                result["log_time"] = time_str + "09"
        else:
            # 尝试中文格式
            cn_time = re.search(r'(\d{4}) 年 (0?[1-9]|1[0-2]) 月 (0?[1-9]|[12]\d|3[01]) 日 (0?\d|1\d|2[0-3]) [点时]', user_input)
            if cn_time:
                y, m, d, h = cn_time.groups()
                result["log_time"] = f"{y}{m.zfill(2)}{d.zfill(2)}{h.zfill(2)}"
        
        # 提取 REQ_SN（支持多种格式）
        req_sn_patterns = [
            r'req_sn[=：:\s]+([A-Za-z0-9\-]+)',
            r'交易 [：:\s]*([A-Za-z0-9\-]+)',
            r'([A-Za-z0-9\-]{20,})',  # 长字符串（排除已匹配的时间）
        ]
        
        for pattern in req_sn_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                req_sn = match.group(1)
                # 排除纯数字（可能是时间）
                if not req_sn.isdigit():
                    result["req_sn"] = req_sn
                    break
        
        # 提取交易类型
        for type_name, type_code in self.transaction_types.items():
            if type_name in user_input:
                result["transaction_type"] = type_code
                result["transaction_name"] = type_name
                break
        
        # 提取服务名称
        service_patterns = [
            r'(sft-[a-z]+)',
            r'(?:服务 | 应用)[=：:\s]*(sft-[a-z]+)',
        ]
        
        for pattern in service_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                result["service"] = match.group(1)
                break
        
        # 判断意图
        if result["req_sn"] and result["log_time"]:
            if "链路" in user_input or "追踪" in user_input or "所有应用" in user_input:
                result["intent"] = "trace"
            elif "分析" in user_input or "为什么" in user_input or "状态" in user_input:
                result["intent"] = "analyze"
            else:
                result["intent"] = "query"
        elif result["req_sn"]:
            result["intent"] = "query"
            # 尝试使用当前小时
            result["log_time"] = datetime.now().strftime('%Y%m%d%H')
        
        return result
    
    def query_logs(self, req_sn: str, log_time: str, service: str = "sft-aipg") -> Dict:
        """
        查询单日志
        
        Args:
            req_sn: 交易序列号
            log_time: 日志时间
            service: 服务名称
        
        Returns:
            API 响应
        """
        resp = requests.get(
            f"{self.base_url}/log-query",
            headers=self.headers,
            params={
                "req_sn": req_sn,
                "log_time": log_time,
                "service": service
            },
            timeout=30
        )
        return resp.json()
    
    def trace_transaction(self, req_sn: str, log_time: str, transaction_type: str) -> Dict:
        """
        追踪交易链路
        
        Args:
            req_sn: 交易序列号
            log_time: 日志时间
            transaction_type: 交易类型代码
        
        Returns:
            API 响应
        """
        resp = requests.get(
            f"{self.base_url}/transaction-trace",
            headers=self.headers,
            params={
                "req_sn": req_sn,
                "log_time": log_time,
                "transaction_type": transaction_type
            },
            timeout=60
        )
        return resp.json()
    
    def analyze_transaction(self, req_sn: str, log_time: str, 
                          transaction_type: str = None, 
                          analysis_type: str = "full") -> Dict:
        """
        AI 智能分析交易
        
        Args:
            req_sn: 交易序列号
            log_time: 日志时间
            transaction_type: 交易类型代码
            analysis_type: 分析类型（summary/full）
        
        Returns:
            API 响应
        """
        resp = requests.post(
            f"{self.base_url}/transaction-analyze",
            headers=self.headers,
            json={
                "req_sn": req_sn,
                "log_time": log_time,
                "transaction_type": transaction_type,
                "analysis_type": analysis_type
            },
            timeout=60
        )
        return resp.json()
    
    def format_response(self, parsed: Dict, api_result: Dict) -> str:
        """
        格式化 API 响应为智多星回复
        
        Args:
            parsed: 解析后的参数
            api_result: API 响应结果
        
        Returns:
            格式化的回复文本
        """
        intent = parsed.get("intent")
        
        if intent == "query":
            return self._format_query_response(parsed, api_result)
        elif intent == "trace":
            return self._format_trace_response(parsed, api_result)
        elif intent == "analyze":
            return self._format_analyze_response(parsed, api_result)
        else:
            return "抱歉，我没有理解您的查询。请提供 REQ_SN 和日志时间，例如：\n\"帮我查一下交易 LX260408090024C80C82F3，时间是 2026040809\""
    
    def _format_query_response(self, parsed: Dict, api_result: Dict) -> str:
        """格式化单日志查询响应"""
        if not api_result.get("success"):
            return f"❌ 查询失败：{api_result.get('message', '未知错误')}"
        
        logs = api_result.get("logs", [])
        total = api_result.get("total", 0)
        query_time = api_result.get("query_time_ms", 0)
        
        if total == 0:
            return "⚠️ 未找到相关日志，请检查 REQ_SN 和日志时间是否正确。"
        
        # 构建回复
        reply = f"""✅ 已为您找到 **{total}** 条日志（查询耗时 {query_time}ms）

**关键信息：**
- 📋 REQ_SN: `{parsed['req_sn']}`
- ⏰ 日志时间：{parsed['log_time']}
- 🏷️ TraceID: `{logs[0].get('trace_id', 'N/A')}`
- 🏪 服务：{parsed.get('service', 'sft-aipg')}

**日志内容：**
"""
        
        # 显示前 10 条日志
        for i, log in enumerate(logs[:10], 1):
            timestamp = log.get('timestamp', 'N/A')
            level = log.get('level', 'N/A')
            content = log.get('content', '')[:300]
            
            reply += f"\n{i}. [{timestamp}] [{level}]"
            reply += f"\n   {content}..."
        
        if total > 10:
            reply += f"\n\n（仅显示前 10 条，共 {total} 条）"
        
        reply += "\n\n需要我帮您分析这笔交易的完整链路，或者查看其他时间的日志吗？😊"
        
        return reply
    
    def _format_trace_response(self, parsed: Dict, api_result: Dict) -> str:
        """格式化交易链路追踪响应"""
        if not api_result.get("success"):
            return f"❌ 追踪失败：{api_result.get('message', '未知错误')}"
        
        trace_groups = api_result.get("trace_groups", [])
        total_logs = api_result.get("total_logs", 0)
        apps = api_result.get("apps", [])
        query_time = api_result.get("query_time_ms", 0)
        
        if total_logs == 0:
            return "⚠️ 未找到交易链路，请检查 REQ_SN 和日志时间是否正确。"
        
        group = trace_groups[0] if trace_groups else {}
        trace_id = group.get("trace_id", "N/A")
        app_logs = group.get("app_logs", {})
        
        # 构建回复
        reply = f"""✅ 已为您追踪到完整的交易链路（查询耗时 {query_time}ms）

**关键信息：**
- 📋 REQ_SN: `{parsed['req_sn']}`
- ⏰ 日志时间：{parsed['log_time']}
- 🏷️ TraceID: `{trace_id}`
- 🔗 交易类型：{parsed.get('transaction_name', 'N/A')} ({parsed.get('transaction_type', 'N/A')})
- 📊 总日志数：{total_logs} 条
- 🏢 涉及应用：{len(apps)} 个

**交易流程：**
"""
        
        # 显示每个应用的日志统计
        for i, app in enumerate(apps, 1):
            logs = app_logs.get(app, [])
            log_count = len(logs)
            
            if log_count > 0:
                first_ts = logs[0].get('timestamp', 'N/A') if logs else 'N/A'
                reply += f"\n{i}. **{app}** ({log_count} 条日志)"
                reply += f"\n   第一条：{first_ts}"
                
                # 显示第一条日志的摘要
                if logs:
                    content = logs[0].get('content', '')[:200]
                    reply += f"\n   摘要：{content}..."
            else:
                reply += f"\n{i}. **{app}** - 无日志"
        
        reply += f"\n\n所有应用的完整日志已返回，您可以查看详细数据！"
        reply += f"\n\n需要我帮您分析这笔交易的状态，或者查看某个特定服务的详细日志吗？😊"
        
        return reply
    
    def _format_analyze_response(self, parsed: Dict, api_result: Dict) -> str:
        """格式化 AI 智能分析响应"""
        if not api_result.get("success"):
            return f"❌ 分析失败：{api_result.get('message', '未知错误')}"
        
        analysis = api_result.get("analysis", {})
        summary = analysis.get("summary", {})
        extracted_info = analysis.get("extracted_info", {})
        flow = analysis.get("flow", [])
        issues = analysis.get("issues", [])
        suggestions = analysis.get("suggestions", [])
        
        # 构建回复
        status_emoji = "✅" if summary.get("status") == "成功" else "⚠️"
        
        reply = f"""{status_emoji} **交易分析报告**

**基本信息：**
- 📋 REQ_SN: `{summary.get('req_sn', 'N/A')}`
- 🏷️ TraceID: `{summary.get('trace_id', 'N/A')}`
- 🔗 交易类型：{summary.get('transaction_name', 'N/A')} ({summary.get('transaction_type', 'N/A')})
- ✅ 交易状态：{summary.get('status', 'N/A')}
- 📊 日志总数：{summary.get('total_logs', 0)} 条
- 🏢 涉及服务：{summary.get('services_count', 0)} 个
- ⏱️ 总耗时：约 {summary.get('total_time_ms', 0)}ms
"""
        
        # 提取的信息
        if extracted_info:
            reply += "\n**提取信息：**"
            if extracted_info.get('amount'):
                reply += f"\n- 💰 金额：{extracted_info['amount']} 元"
            if extracted_info.get('merchant_no'):
                reply += f"\n- 🏪 商户号：{extracted_info['merchant_no']}"
            if extracted_info.get('bank_name'):
                reply += f"\n- 🏦 银行：{extracted_info['bank_name']}"
            if extracted_info.get('error_message'):
                reply += f"\n- ⚠️ 错误信息：{extracted_info['error_message']}"
        
        # 交易流程
        if flow:
            reply += "\n\n**交易流程：**"
            for i, step in enumerate(flow, 1):
                emoji = "❌" if step.get('has_error') else "✅"
                reply += f"\n{i}. {emoji} **{step['service']}** ({step['log_count']} 条)"
        
        # 问题和建议
        if issues:
            reply += "\n\n**发现问题：**"
            for issue in issues:
                reply += f"\n- ⚠️ {issue}"
        
        if suggestions:
            reply += "\n\n**建议：**"
            for suggestion in suggestions:
                reply += f"\n- 💡 {suggestion}"
        
        reply += "\n\n需要我帮您查看某个服务的详细日志，或者分析其他交易吗？😊"
        
        return reply
    
    def chat(self, user_input: str) -> str:
        """
        智多星聊天接口 - 主入口
        
        Args:
            user_input: 用户输入的自然语言
        
        Returns:
            智多星的回复
        """
        print(f"\n🤖 智多星收到：{user_input}\n")
        
        # 1. 解析用户意图
        parsed = self.parse_user_query(user_input)
        print(f"🔍 解析结果：{json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
        
        # 2. 根据意图调用相应 API
        if parsed["intent"] == "unknown":
            return self.format_response(parsed, {"success": False, "message": "无法理解查询意图"})
        
        elif parsed["intent"] == "query":
            print("📝 调用单日志查询接口...")
            api_result = self.query_logs(
                parsed["req_sn"],
                parsed["log_time"],
                parsed.get("service", "sft-aipg")
            )
        
        elif parsed["intent"] == "trace":
            print("🔗 调用交易链路追踪接口...")
            api_result = self.trace_transaction(
                parsed["req_sn"],
                parsed["log_time"],
                parsed.get("transaction_type", "310011")
            )
        
        elif parsed["intent"] == "analyze":
            print("🤖 调用 AI 智能分析接口...")
            api_result = self.analyze_transaction(
                parsed["req_sn"],
                parsed["log_time"],
                parsed.get("transaction_type"),
                parsed.get("analysis_type", "full")
            )
        
        else:
            return self.format_response(parsed, {"success": False, "message": "未知意图"})
        
        # 3. 格式化响应
        print("💬 生成回复...\n")
        reply = self.format_response(parsed, api_result)
        
        return reply


# ========== 使用示例 ==========

if __name__ == "__main__":
    # 创建智多星客户端
    zdx = ZhiduoxingLogClient()
    
    # 测试用例
    test_cases = [
        # 单日志查询
        "帮我查一下交易 LX260408090024C80C82F3，时间是 2026040809",
        
        # 带服务名
        "查询 req_sn=LX260408090024C80C82F3 在 sft-aipg 的日志，时间 2026040809",
        
        # 交易链路追踪
        "帮我追踪交易 LX260408090024C80C82F3 的完整链路，时间 2026040809，交易类型是协议支付",
        
        # AI 智能分析
        "分析一下这笔交易 LX260408090024C80C82F3，时间是 2026040809，为什么失败了？",
        
        # 中文日期格式
        "帮我查交易 2widscma-1491361962608050176，时间是 2026 年 4 月 8 日 9 点",
    ]
    
    print("="*80)
    print("🤖 智多星 AI - sftlogapi v2 接口调用测试")
    print("="*80)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试用例 {i}: {test}")
        print("="*80)
        
        reply = zdx.chat(test)
        print(reply)
        print("\n" + "-"*80)
        
        if i < len(test_cases):
            input("\n按 Enter 继续下一个测试...")
    
    print("\n" + "="*80)
    print("✅ 所有测试完成！")
    print("="*80)
