#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""price-radar-mcp · 模型价格雷达 MCP
让 AI 直接比价：「哪个便宜」「写代码最省的方案」「这个价划算吗」
零依赖 stdio MCP 服务器
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

__version__ = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"
PRICE_PATH = Path.home() / ".price-radar" / "prices.json"

# 内置参考价：美元/百万token，格式 [输入价, 输出价, 质量档(1-5), 标签]
CATALOG = {
    "gpt-4o": [2.5, 10.0, 5, "通用"],
    "gpt-4o-mini": [0.15, 0.6, 3, "通用/便宜"],
    "gpt-4.1": [2.0, 8.0, 5, "通用"],
    "gpt-4.1-mini": [0.4, 1.6, 4, "通用/性价比"],
    "gpt-3.5-turbo": [0.5, 1.5, 2, "老旧"],
    "o3-mini": [1.1, 4.4, 4, "推理"],
    "claude-opus-4": [15.0, 75.0, 5, "高端"],
    "claude-sonnet-4": [3.0, 15.0, 5, "代码/通用"],
    "claude-haiku": [0.8, 4.0, 3, "快速"],
    "deepseek-chat": [0.27, 1.1, 4, "通用/极便宜"],
    "deepseek-reasoner": [0.55, 2.19, 5, "推理/极便宜"],
    "qwen-turbo": [0.05, 0.2, 2, "最便宜"],
    "qwen-plus": [0.4, 1.2, 4, "通用/便宜"],
    "qwen-max": [1.6, 6.4, 5, "高端"],
    "qwen-vl-max": [3.0, 9.0, 4, "视觉"],
    "glm-4": [0.6, 0.6, 3, "通用/便宜"],
    "glm-4-plus": [2.0, 2.0, 4, "通用"],
    "moonshot-v1-8k": [1.68, 1.68, 3, "长文"],
    "gemini-2.0-flash": [0.1, 0.4, 3, "极便宜/快"],
    "gemini-2.5-pro": [1.25, 10.0, 5, "长文/视觉"],
    "kimi-k2": [0.6, 2.5, 4, "长文/中文"],
}

TASK_TAGS = {
    "代码": ["代码", "通用", "推理"],
    "编程": ["代码", "通用", "推理"],
    "推理": ["推理"],
    "数学": ["推理"],
    "翻译": ["通用", "便宜", "极便宜", "最便宜"],
    "总结": ["便宜", "极便宜", "最便宜", "快速"],
    "长文": ["长文"],
    "看图": ["视觉"],
    "便宜": ["最便宜", "极便宜", "便宜"],
    "快": ["快速", "极便宜"],
}


# ================= MCP 内核 =================

class MCPServer:
    def __init__(self, name: str, version: str, tools: list):
        self.name, self.version, self.tools = name, version, tools

    def _send(self, msg: dict) -> None:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _result(self, id_, result) -> None:
        self._send({"jsonrpc": "2.0", "id": id_, "result": result})

    def _error(self, id_, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})

    def handle(self, msg: dict) -> None:
        if not isinstance(msg, dict):
            return
        method, id_ = msg.get("method"), msg.get("id")
        if method == "initialize":
            self._result(id_, {"protocolVersion": PROTOCOL_VERSION,
                               "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": self.name, "version": self.version}})
        elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            return
        elif method == "ping":
            self._result(id_, {})
        elif method == "tools/list":
            self._result(id_, {"tools": [
                {"name": t["name"], "description": t["description"],
                 "inputSchema": t.get("inputSchema") or {"type": "object", "properties": {}}}
                for t in self.tools]})
        elif method == "tools/call":
            params = msg.get("params") or {}
            tool = next((t for t in self.tools if t["name"] == params.get("name")), None)
            if tool is None:
                self._error(id_, -32602, f"未知工具: {params.get('name')}")
                return
            try:
                out = tool["handler"](params.get("arguments") or {})
                self._result(id_, {"content": [{"type": "text", "text": str(out)}], "isError": False})
            except Exception as exc:
                self._result(id_, {"content": [{"type": "text",
                                                "text": f"错误: {type(exc).__name__}: {exc}"}],
                                   "isError": True})
        elif id_ is not None:
            self._error(id_, -32601, f"不支持的方法: {method}")

    def serve(self) -> None:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            for item in (msg if isinstance(msg, list) else [msg]):
                self.handle(item)


# ================= 数据层 =================

def load_overrides() -> dict:
    if PRICE_PATH.exists():
        try:
            data = json.loads(PRICE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_overrides(data: dict) -> None:
    PRICE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRICE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def catalog() -> dict:
    """内置目录 + 用户覆盖（用户价优先）"""
    merged = {name: list(info) for name, info in CATALOG.items()}
    for name, info in load_overrides().items():
        if isinstance(info, list) and len(info) >= 2:
            quality = info[2] if len(info) > 2 else merged.get(name, [0, 0, 3])[2]
            tag = info[3] if len(info) > 3 else "自定义"
            merged[name] = [float(info[0]), float(info[1]), quality, tag]
    return merged


def blended_price(entry: list) -> float:
    """按 3:1 输入输出比估算综合单价"""
    return entry[0] * 0.75 + entry[1] * 0.25


def value_score(entry: list) -> float:
    """性价比 = 质量 / 综合价（越大越划算）"""
    price = blended_price(entry)
    if price <= 0:
        return 999.0
    return entry[2] / price


# ================= 工具 =================

def tool_price_table(args: dict) -> str:
    data = catalog()
    keyword = (args.get("keyword") or "").lower()
    sort_by = (args.get("sort") or "price").lower()
    items = [(k, v) for k, v in data.items() if not keyword or keyword in k.lower()]
    if not items:
        return f"没有匹配「{keyword}」的模型。"
    if sort_by == "value":
        items.sort(key=lambda kv: -value_score(kv[1]))
        title = "按性价比排序（质量/价格，越大越划算）"
    elif sort_by == "quality":
        items.sort(key=lambda kv: (-kv[1][2], blended_price(kv[1])))
        title = "按质量档排序"
    else:
        items.sort(key=lambda kv: blended_price(kv[1]))
        title = "按价格排序（低到高）"
    lines = [f"模型价格表 · {title}", "",
             f"{'模型':<20}{'输入':<10}{'输出':<10}{'质量':<7}{'标签'}", "-" * 66]
    for name, entry in items[:40]:
        lines.append(f"{name:<20}${entry[0]:<9}${entry[1]:<9}{entry[2]:<7}{entry[3]}")
    lines += ["-" * 66, "",
              "单位：美元 / 百万 token",
              "注意：这是内置参考价，中转站实际价格可能不同。",
              f"用 set_price 设置你实际付的价格（保存于 {PRICE_PATH}）。"]
    return "\n".join(lines)


def tool_compare_models(args: dict) -> str:
    models = args.get("models") or []
    if not isinstance(models, list) or len(models) < 2:
        return "需要 models 数组，至少 2 个模型名。"
    data = catalog()
    lines = [f"对比 {len(models)} 个模型：", ""]
    rows = []
    for name in models[:8]:
        entry = data.get(str(name))
        if not entry:
            lines.append(f"- {name}：没有价格数据（可用 set_price 添加）")
            continue
        rows.append((str(name), entry))
    if not rows:
        return "\n".join(lines)
    lines.append(f"{'模型':<20}{'综合单价':<12}{'输入':<10}{'输出':<10}{'质量':<7}")
    lines.append("-" * 62)
    for name, entry in sorted(rows, key=lambda r: blended_price(r[1])):
        lines.append(f"{name:<20}${blended_price(entry):<11.3f}${entry[0]:<9}${entry[1]:<9}{entry[2]}")
    lines.append("-" * 62)
    cheapest = min(rows, key=lambda r: blended_price(r[1]))
    best_value = max(rows, key=lambda r: value_score(r[1]))
    best_quality = max(rows, key=lambda r: r[1][2])
    lines += ["", f"最便宜：{cheapest[0]}（综合 ${blended_price(cheapest[1]):.3f}/百万token）",
              f"最划算：{best_value[0]}（性价比最高）",
              f"质量最高：{best_quality[0]}（质量档 {best_quality[1][2]}/5）",
              "",
              "综合单价按 3:1 的输入输出比例估算，实际以你的用法为准。"]
    return "\n".join(lines)


def tool_recommend_cheap(args: dict) -> str:
    task = (args.get("task") or "").strip()
    if not task:
        return "请说明任务，如「写代码」「翻译」「长文总结」。"
    low = task.lower()
    tags: list[str] = []
    for key, matched in TASK_TAGS.items():
        if key in low or key in task:
            tags = matched
            break
    data = catalog()
    if tags:
        candidates = [(k, v) for k, v in data.items()
                      if any(t in v[3] for t in tags)]
        lines = [f"任务「{task}」的候选模型（按性价比排序）：", ""]
    else:
        candidates = list(data.items())
        lines = [f"没识别出「{task}」的具体类型，给出通用性价比排行：", ""]
    candidates.sort(key=lambda kv: -value_score(kv[1]))
    for name, entry in candidates[:6]:
        lines.append(f"- {name}  ${blended_price(entry):.3f}/百万token  "
                     f"质量{entry[2]}/5  [{entry[3]}]")
    if candidates:
        top = candidates[0]
        lines += ["", f"推荐先试：{top[0]}（性价比最高）",
                  "先用 compare_models 拿它和备选同题比一比，觉得够用就用它。"]
    return "\n".join(lines)


def tool_set_price(args: dict) -> str:
    model = (args.get("model") or "").strip()
    if not model:
        return "需要 model。"
    try:
        pin = float(args.get("input_price"))
        pout = float(args.get("output_price"))
    except (TypeError, ValueError):
        return "需要 input_price 和 output_price（数字，美元/百万token）。"
    quality = int(args.get("quality") or 3)
    overrides = load_overrides()
    overrides[model] = [pin, pout, quality, "自定义"]
    save_overrides(overrides)
    return (f"已设置 {model}：输入 ${pin} / 输出 ${pout}（每百万token，质量档 {quality}）\n"
            f"之后所有比价都会用这个价格。")


def tool_cost_estimate(args: dict) -> str:
    """场景成本估算：给定 token 量，算几个模型各要花多少"""
    try:
        tokens_in = float(args.get("input_tokens") or 0)
        tokens_out = float(args.get("output_tokens") or 0)
    except (TypeError, ValueError):
        return "input_tokens 和 output_tokens 需要是数字。"
    if tokens_in <= 0 and tokens_out <= 0:
        return "请给出 input_tokens 和 output_tokens（单位：token）。"
    models = args.get("models")
    data = catalog()
    if models and isinstance(models, list):
        items = [(str(m), data[str(m)]) for m in models if str(m) in data]
        if not items:
            return "指定的模型都没有价格数据。"
    else:
        items = sorted(data.items(), key=lambda kv: blended_price(kv[1]))[:8]
    lines = [f"用量：输入 {tokens_in:,.0f} + 输出 {tokens_out:,.0f} token", ""]
    rows = []
    for name, entry in items:
        cost = tokens_in / 1_000_000 * entry[0] + tokens_out / 1_000_000 * entry[1]
        rows.append((name, cost, entry))
    for name, cost, entry in sorted(rows, key=lambda r: r[1]):
        lines.append(f"- {name:<22} ${cost:.4f}")
    if rows:
        cheapest = min(rows, key=lambda r: r[1])
        priciest = max(rows, key=lambda r: r[1])
        if priciest[1] > 0:
            lines.append(f"\n最贵比最便宜贵 {priciest[1] / cheapest[1]:.1f} 倍"
                         f"（{priciest[0]} vs {cheapest[0]}）")
    return "\n".join(lines)


TOOLS = [
    {"name": "price_table",
     "description": "查看模型价格表，可按价格/质量/性价比排序。"
                    "用户问「模型都什么价」「有哪些便宜模型」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "keyword": {"type": "string", "description": "按模型名过滤"},
         "sort": {"type": "string", "enum": ["price", "value", "quality"],
                  "description": "排序方式，默认 price"}}},
     "handler": tool_price_table},
    {"name": "compare_models",
     "description": "对比指定模型的单价。用户说「这几个哪个便宜」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "models": {"type": "array", "items": {"type": "string"}}},
         "required": ["models"]},
     "handler": tool_compare_models},
    {"name": "recommend_cheap",
     "description": "按任务类型推荐最划算的模型。用户问「写代码最省钱的方案」"
                    "「翻译用哪个便宜」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "task": {"type": "string"}}, "required": ["task"]},
     "handler": tool_recommend_cheap},
    {"name": "set_price",
     "description": "设置你实际支付的价格（覆盖内置参考价）。"
                    "用户说「我这边 gpt-4o 是 X 块钱」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "model": {"type": "string"},
         "input_price": {"type": "number", "description": "美元/百万token"},
         "output_price": {"type": "number"},
         "quality": {"type": "integer", "description": "质量档 1-5，默认3"}},
         "required": ["model", "input_price", "output_price"]},
     "handler": tool_set_price},
    {"name": "cost_estimate",
     "description": "按给定 token 量估算各模型花费。用户问「这样跑一次要多少钱」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "input_tokens": {"type": "number"}, "output_tokens": {"type": "number"},
         "models": {"type": "array", "items": {"type": "string"}}},
         "required": ["input_tokens", "output_tokens"]},
     "handler": tool_cost_estimate},
]


def main() -> int:
    if os.name == "nt":
        try:
            sys.stdin.reconfigure(encoding="utf-8")
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    MCPServer("price-radar-mcp", __version__, TOOLS).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
