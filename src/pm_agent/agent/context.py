"""API 前上下文视图：tool 压缩、滑动窗口、SessionState 快照。"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from pm_agent.agent.session import SessionState

DEFAULT_WINDOW_TURNS = 15

_DRAFT_TOOL_NAMES = frozenset(
    {
        "draft_project_charter",
        "draft_risk_register",
        "draft_decision_record",
        "draft_decision_matrix",
    }
)


@dataclass(frozen=True)
class ContextPolicy:
    """上下文裁剪策略（可由 Settings 或测试显式传入）。"""

    enabled: bool = True
    window_turns: int = DEFAULT_WINDOW_TURNS


def context_policy_from_settings(
    *,
    context_compact: bool,
    context_window_turns: int,
) -> ContextPolicy:
    return ContextPolicy(
        enabled=context_compact,
        window_turns=max(1, context_window_turns),
    )


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    for sep in ("。", "；", ".", "\n"):
        idx = stripped.find(sep)
        if idx >= 0:
            return stripped[: idx + 1]
    return stripped


def _compact_recommend_tools(data: dict[str, Any]) -> dict[str, Any]:
    tools_in = data.get("tools")
    compact_tools: list[dict[str, Any]] = []
    if isinstance(tools_in, list):
        for item in tools_in:
            if not isinstance(item, dict):
                continue
            compact_tools.append(
                {
                    k: item[k]
                    for k in ("slug", "name", "reason")
                    if k in item
                }
            )
    out: dict[str, Any] = {"_compacted": True}
    if "match_strength" in data:
        out["match_strength"] = data["match_strength"]
    if compact_tools:
        out["tools"] = compact_tools
    instruction = data.get("instruction")
    if isinstance(instruction, str) and instruction.strip():
        out["instruction"] = _first_sentence(instruction)
    return out


def _compact_get_tool_detail(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "_compacted": True,
        "slug": data.get("slug"),
        "name": data.get("name"),
        "summary": data.get("summary"),
        "draftable": data.get("draftable"),
    }


def _compact_start_consulting(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "_compacted": True,
        "ok": data.get("ok"),
        "slug": data.get("slug"),
        "name": data.get("name"),
        "mode": data.get("mode"),
    }


def _compact_search_tools(data: dict[str, Any]) -> dict[str, Any]:
    tools_in = data.get("tools")
    compact_tools: list[dict[str, Any]] = []
    if isinstance(tools_in, list):
        for item in tools_in:
            if not isinstance(item, dict):
                continue
            compact_tools.append(
                {
                    k: item[k]
                    for k in ("slug", "name")
                    if k in item
                }
            )
    out: dict[str, Any] = {"_compacted": True, "query": data.get("query")}
    if compact_tools:
        out["tools"] = compact_tools
    return out


def _compact_draft_tool(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"_compacted": True, "ok": data.get("ok")}
    for key in ("preview", "missing_fields", "note"):
        if key in data:
            out[key] = data[key]
    return out


def _compact_export_markdown(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "_compacted": True,
        "ok": data.get("ok"),
        "path": data.get("path"),
        "doc_type": data.get("doc_type"),
    }


def compact_tool_message(name: str, content: str) -> str:
    """压缩已完成回合内的 tool 返回；解析失败则原样返回。"""
    if name in {"note_consulting_fact", "echo", "add"}:
        return content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return content
    if not isinstance(data, dict):
        return content

    if name == "recommend_tools":
        compacted = _compact_recommend_tools(data)
    elif name == "get_tool_detail":
        compacted = _compact_get_tool_detail(data)
    elif name == "start_consulting":
        compacted = _compact_start_consulting(data)
    elif name == "search_tools":
        compacted = _compact_search_tools(data)
    elif name in _DRAFT_TOOL_NAMES:
        compacted = _compact_draft_tool(data)
    elif name == "export_markdown":
        compacted = _compact_export_markdown(data)
    else:
        return content

    return json.dumps(compacted, ensure_ascii=False)


def _compact_turn_tools(turn: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in turn:
        if msg.get("role") != "tool":
            out.append(copy.copy(msg))
            continue
        name = str(msg.get("name") or "")
        content = msg.get("content")
        if not isinstance(content, str):
            out.append(copy.copy(msg))
            continue
        compacted = compact_tool_message(name, content)
        out.append({**msg, "content": compacted})
    return out


def split_turns(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    """切分前缀 system 与以 user 开头的回合列表。"""
    if not messages:
        return [], []

    prefix: list[dict[str, Any]] = []
    index = 0
    if messages[0].get("role") == "system":
        prefix.append(messages[0])
        index = 1

    turns: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] | None = None
    for msg in messages[index:]:
        if msg.get("role") == "user":
            if current is not None:
                turns.append(current)
            current = [msg]
        elif current is not None:
            current.append(msg)
        else:
            prefix.append(msg)

    if current is not None:
        turns.append(current)
    return prefix, turns


def apply_sliding_window(
    turns: list[list[dict[str, Any]]],
    *,
    window_turns: int,
) -> tuple[list[list[dict[str, Any]]], int]:
    """保留最近 window_turns 个回合，返回 (可见回合, 丢弃数量)。"""
    if not turns:
        return [], 0
    limit = max(1, window_turns)
    if len(turns) <= limit:
        return turns, 0
    dropped = len(turns) - limit
    return turns[-limit:], dropped


def build_state_snapshot(state: SessionState) -> str | None:
    """从 SessionState 生成结构化快照；无实质内容时返回 None。"""
    lines: list[str] = []

    has_notes = bool(state.consulting_notes)
    has_charter = state.charter_draft is not None
    has_risk = state.risk_draft is not None and bool(state.risk_draft.items)
    has_decision = state.decision_draft is not None
    has_matrix = state.matrix_draft is not None

    if not (has_notes or has_charter or has_risk or has_decision or has_matrix):
        return None

    lines.append("【会话状态快照】（较早对话已省略，请以此为准）")
    lines.append(f"- 模式：{state.mode.value}")
    consulting = state.consulting_tool_slug or "无"
    lines.append(f"- 陪跑工具：{consulting}")

    if has_notes:
        lines.append("- 已沉淀事实：")
        for idx, fact in enumerate(state.consulting_notes, start=1):
            lines.append(f"  {idx}. {fact}")

    if has_charter and state.charter_draft is not None:
        preview = "; ".join(state.charter_draft.preview_lines())
        lines.append(f"- 章程草稿：{preview}")

    if has_risk and state.risk_draft is not None:
        preview = "; ".join(state.risk_draft.preview_lines())
        lines.append(f"- 风险草稿：{preview}")

    if has_decision and state.decision_draft is not None:
        preview = "; ".join(state.decision_draft.preview_lines())
        lines.append(f"- 决策记录：{preview}")

    if has_matrix and state.matrix_draft is not None:
        preview = "; ".join(state.matrix_draft.preview_lines())
        lines.append(f"- 决策矩阵：{preview}")

    return "\n".join(lines)


def _flatten_turns(turns: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for turn in turns:
        flat.extend(turn)
    return flat


def prepare_messages_for_api(
    state: SessionState,
    *,
    policy: ContextPolicy | None = None,
) -> list[dict[str, Any]]:
    """生成发给 LLM 的只读消息视图，不修改 state.messages。"""
    active = policy or ContextPolicy()
    if not active.enabled:
        return [copy.copy(m) for m in state.messages]

    prefix, turns = split_turns(state.messages)
    visible_turns, dropped_count = apply_sliding_window(
        turns,
        window_turns=active.window_turns,
    )

    processed: list[list[dict[str, Any]]] = []
    for idx, turn in enumerate(visible_turns):
        is_current = idx == len(visible_turns) - 1
        if is_current:
            processed.append([copy.copy(m) for m in turn])
        else:
            processed.append(_compact_turn_tools(turn))

    result: list[dict[str, Any]] = [copy.copy(m) for m in prefix]

    if dropped_count > 0:
        snapshot = build_state_snapshot(state)
        if snapshot:
            if result and result[0].get("role") == "system":
                result.insert(1, {"role": "system", "content": snapshot})
            else:
                result.insert(0, {"role": "system", "content": snapshot})

    result.extend(_flatten_turns(processed))
    return result
