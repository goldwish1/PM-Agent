"""LLM 调试观测：L1 终端摘要 + L2 每 turn 一个 JSON 落盘。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONTENT_PREVIEW_LEN = 120


def estimate_messages_chars(messages: list[dict[str, Any]]) -> int:
    """粗估 messages 序列化字符数（非 token）。"""
    try:
        return len(json.dumps(messages, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return sum(len(str(m)) for m in messages)


def _preview_content(content: str | None) -> str:
    if content is None or not str(content).strip():
        return "∅"
    text = str(content).replace("\n", " ").strip()
    if len(text) > _CONTENT_PREVIEW_LEN:
        return text[:_CONTENT_PREVIEW_LEN] + "…"
    return text


def _format_usage_line(
    usage: dict[str, int] | None,
    *,
    llm_is_fake: bool,
) -> str:
    if llm_is_fake:
        return "   usage: fake"
    if not usage:
        return "   usage: n/a"
    prompt = usage.get("prompt_tokens", "?")
    completion = usage.get("completion_tokens", "?")
    total = usage.get("total_tokens", "?")
    parts = [f"prompt={prompt}", f"completion={completion}", f"total={total}"]
    if "prompt_cache_hit_tokens" in usage:
        parts.append(f"cache_hit={usage['prompt_cache_hit_tokens']}")
    if "prompt_cache_miss_tokens" in usage:
        parts.append(f"cache_miss={usage['prompt_cache_miss_tokens']}")
    return "   usage: " + " ".join(parts)


def format_llm_round(
    *,
    user_turn: int,
    iteration: int,
    messages: list[dict[str, Any]],
    tools_count: int,
    content: str | None,
    tool_calls: list[dict[str, Any]] | None,
    usage: dict[str, int] | None,
    llm_is_fake: bool = False,
) -> str:
    """组装 L1 多行摘要（不含末尾多余空行）。"""
    chars = estimate_messages_chars(messages)
    calls = tool_calls or []
    if calls:
        names = ", ".join(str(tc.get("name") or "?") for tc in calls)
        out_calls = f"tool_calls=[{names}]"
    else:
        out_calls = "tool_calls=[]"
    lines = [
        f"──────── [llm] turn={user_turn} iter={iteration} ────────",
        f"→ in: msgs={len(messages)} tools={tools_count} ~chars={chars}",
        f"← out: {out_calls} content={_preview_content(content)}",
        _format_usage_line(usage, llm_is_fake=llm_is_fake),
    ]
    return "\n".join(lines)


def print_llm_round(
    *,
    user_turn: int,
    iteration: int,
    messages: list[dict[str, Any]],
    tools_count: int,
    content: str | None,
    tool_calls: list[dict[str, Any]] | None,
    usage: dict[str, int] | None,
    llm_is_fake: bool = False,
) -> None:
    text = format_llm_round(
        user_turn=user_turn,
        iteration=iteration,
        messages=messages,
        tools_count=tools_count,
        content=content,
        tool_calls=tool_calls,
        usage=usage,
        llm_is_fake=llm_is_fake,
    )
    print(text, flush=True)


def debug_dir(output_dir: Path) -> Path:
    return Path(output_dir) / "debug"


def sum_usage(
    iterations: list[dict[str, Any]],
) -> dict[str, int] | None:
    """对 iterations 中有值的 prompt/completion/total/cache 分别求和；全无则 None。"""
    prompt = 0
    completion = 0
    total = 0
    cache_hit = 0
    cache_miss = 0
    saw_any = False
    saw_cache_hit = False
    saw_cache_miss = False
    for item in iterations:
        usage = item.get("usage")
        if not isinstance(usage, dict):
            continue
        if "prompt_tokens" in usage:
            prompt += int(usage["prompt_tokens"])
            saw_any = True
        if "completion_tokens" in usage:
            completion += int(usage["completion_tokens"])
            saw_any = True
        if "total_tokens" in usage:
            total += int(usage["total_tokens"])
            saw_any = True
        if "prompt_cache_hit_tokens" in usage:
            cache_hit += int(usage["prompt_cache_hit_tokens"])
            saw_cache_hit = True
            saw_any = True
        if "prompt_cache_miss_tokens" in usage:
            cache_miss += int(usage["prompt_cache_miss_tokens"])
            saw_cache_miss = True
            saw_any = True
    if not saw_any:
        return None
    out: dict[str, int] = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }
    if saw_cache_hit:
        out["prompt_cache_hit_tokens"] = cache_hit
    if saw_cache_miss:
        out["prompt_cache_miss_tokens"] = cache_miss
    return out


class TurnDebugDump:
    """同一用户回合聚合到 turn-NNN.json；迭代中重写，结束时写入 messages 快照。"""

    def __init__(
        self,
        output_dir: Path,
        *,
        turn: int,
        user_text: str,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._turn = turn
        self._user_text = user_text
        self._iterations: list[dict[str, Any]] = []
        self._final_assistant: str | None = None
        self._messages: list[dict[str, Any]] | None = None
        self._path = debug_dir(self._output_dir) / f"turn-{turn:03d}.json"

    @property
    def path(self) -> Path:
        return self._path

    def record_iteration(
        self,
        *,
        iteration: int,
        messages: list[dict[str, Any]],
        tools_count: int,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None,
        usage: dict[str, int] | None,
    ) -> Path:
        self._iterations.append(
            {
                "iter": iteration,
                "msgs": len(messages),
                "tools_count": tools_count,
                "chars": estimate_messages_chars(messages),
                "response": {
                    "content": content,
                    "tool_calls": tool_calls,
                },
                "usage": usage,
            }
        )
        return self._flush()

    def finalize(
        self,
        final_assistant: str,
        messages: list[dict[str, Any]],
    ) -> Path:
        self._final_assistant = final_assistant
        self._messages = list(messages)
        return self._flush()

    def _flush(self) -> Path:
        target_dir = debug_dir(self._output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "turn": self._turn,
            "user": self._user_text,
            "iterations": self._iterations,
        }
        if self._final_assistant is not None:
            payload["final_assistant"] = self._final_assistant
        if self._messages is not None:
            payload["messages"] = self._messages
            payload["usage_total"] = sum_usage(self._iterations)
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return self._path
