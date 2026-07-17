"""Agent Loop 过程层可见日志（与最终 ● 回复分层）。"""

from __future__ import annotations

import json
from typing import Any

_INDENT = "  "
_RESPONSE_PREVIEW_LEN = 100
_RESULT_PREVIEW_LEN = 100


def format_args_summary(arguments: dict[str, Any] | Any) -> str:
    if not isinstance(arguments, dict):
        return repr(arguments)
    try:
        return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(arguments)


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def format_response_preview(content: str | None) -> str:
    if content is None or not str(content).strip():
        return "（无文本）"
    return _truncate(_one_line(str(content)), _RESPONSE_PREVIEW_LEN)


def format_tool_result_line(result: str, elapsed_ms: float) -> str:
    status = "err" if str(result).startswith("错误：") else "ok"
    summary = _truncate(_one_line(str(result)), _RESULT_PREVIEW_LEN)
    ms = int(round(elapsed_ms))
    return f"{status}，{summary}，耗时 {ms}ms。"


def format_iteration_header(n: int) -> str:
    return f"── 第{n}轮迭代 ──"


def format_thinking_line() -> str:
    return f"{_INDENT}thinking: LLM调用开始。"


def format_response_line(content: str | None, elapsed_ms: float) -> str:
    preview = format_response_preview(content)
    ms = int(round(elapsed_ms))
    return f"{_INDENT}response: {preview}，耗时 {ms}ms。"


def format_tool_call_line(name: str, arguments: dict[str, Any] | Any) -> str:
    return f"{_INDENT}tool_call: {name}({format_args_summary(arguments)})"


def format_tool_result_event(result: str, elapsed_ms: float) -> str:
    return f"{_INDENT}tool_result: {format_tool_result_line(result, elapsed_ms)}"


def trace_iteration(n: int) -> None:
    print(format_iteration_header(n), flush=True)


def trace_thinking(*, end: str = "\n") -> None:
    print(format_thinking_line(), end=end, flush=True)


def trace_response(content: str | None, elapsed_ms: float) -> None:
    print(format_response_line(content, elapsed_ms), flush=True)


def trace_tool_call(name: str, arguments: dict[str, Any] | Any) -> None:
    print(format_tool_call_line(name, arguments), flush=True)


def trace_tool_result(result: str, elapsed_ms: float) -> None:
    print(format_tool_result_event(result, elapsed_ms), flush=True)
