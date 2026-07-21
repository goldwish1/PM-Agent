"""上下文视图：tool 压缩、滑动窗口、状态快照。"""

from __future__ import annotations

import json

import pytest

from pm_agent.agent.context import (
    ContextPolicy,
    compact_tool_message,
    prepare_messages_for_api,
)
from pm_agent.agent.session import SessionState


def _tool_msg(name: str, payload: dict) -> dict:
    return {
        "role": "tool",
        "tool_call_id": "t1",
        "name": name,
        "content": json.dumps(payload, ensure_ascii=False),
    }


def _detail_payload() -> dict:
    return {
        "slug": "project-charter",
        "name": "项目章程",
        "summary": "正式授权项目",
        "description": "长描述",
        "steps": ["步骤一", "步骤二"],
        "scenarios": ["场景一"],
        "draftable": True,
    }


def test_policy_disabled_returns_full_messages() -> None:
    state = SessionState()
    state.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        _tool_msg("get_tool_detail", _detail_payload()),
    ]
    out = prepare_messages_for_api(
        state,
        policy=ContextPolicy(enabled=False),
    )
    assert len(out) == len(state.messages)
    assert out[2]["content"] == state.messages[2]["content"]


def test_compact_old_turn_get_tool_detail() -> None:
    state = SessionState()
    state.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "turn1"},
        _tool_msg("get_tool_detail", _detail_payload()),
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "turn2"},
    ]
    out = prepare_messages_for_api(state, policy=ContextPolicy(window_turns=15))
    old_tool = out[2]
    assert old_tool["role"] == "tool"
    data = json.loads(old_tool["content"])
    assert data["_compacted"] is True
    assert "steps" not in data
    assert "scenarios" not in data
    assert data["slug"] == "project-charter"


def test_current_turn_get_tool_detail_kept_full() -> None:
    state = SessionState()
    state.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "turn1"},
        _tool_msg("get_tool_detail", _detail_payload()),
    ]
    out = prepare_messages_for_api(state, policy=ContextPolicy(window_turns=15))
    data = json.loads(out[2]["content"])
    assert "_compacted" not in data
    assert "steps" in data


def test_sliding_window_keeps_last_fifteen_user_turns() -> None:
    state = SessionState()
    state.messages = [{"role": "system", "content": "sys"}]
    for i in range(20):
        state.messages.append({"role": "user", "content": f"u{i}"})
        state.messages.append({"role": "assistant", "content": f"a{i}"})

    out = prepare_messages_for_api(state, policy=ContextPolicy(window_turns=15))
    user_contents = [m["content"] for m in out if m.get("role") == "user"]
    assert len(user_contents) == 15
    assert user_contents[0] == "u5"
    assert user_contents[-1] == "u19"


def test_snapshot_injected_when_turns_dropped() -> None:
    state = SessionState()
    state.consulting_notes.append("预算约 50 万")
    state.messages = [{"role": "system", "content": "sys"}]
    for i in range(20):
        state.messages.append({"role": "user", "content": f"u{i}"})
        state.messages.append({"role": "assistant", "content": f"a{i}"})

    out = prepare_messages_for_api(state, policy=ContextPolicy(window_turns=15))
    snapshots = [
        m for m in out if m.get("role") == "system" and "会话状态快照" in m["content"]
    ]
    assert len(snapshots) == 1
    assert "预算约 50 万" in snapshots[0]["content"]


def test_no_snapshot_when_nothing_dropped() -> None:
    state = SessionState()
    state.consulting_notes.append("某事实")
    state.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u0"},
        {"role": "assistant", "content": "a0"},
    ]
    out = prepare_messages_for_api(state, policy=ContextPolicy(window_turns=15))
    assert not any("会话状态快照" in m.get("content", "") for m in out)


def test_compact_draft_removes_consulting_notes_array() -> None:
    payload = {
        "ok": True,
        "preview": ["- 项目名称：待补充"],
        "missing_fields": ["project_name"],
        "note": "请确认",
        "consulting_notes": ["长笔记一", "长笔记二"],
        "consulting_notes_available": True,
    }
    state = SessionState()
    state.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "起草"},
        _tool_msg("draft_project_charter", payload),
        {"role": "user", "content": "继续"},
    ]
    out = prepare_messages_for_api(state, policy=ContextPolicy(window_turns=15))
    data = json.loads(out[2]["content"])
    assert data["_compacted"] is True
    assert "preview" in data
    assert "consulting_notes" not in data


def test_invalid_json_tool_content_passthrough() -> None:
    raw = "not-json"
    assert compact_tool_message("get_tool_detail", raw) == raw


@pytest.mark.parametrize(
    ("name", "payload", "expected_keys"),
    [
        (
            "recommend_tools",
            {
                "match_strength": "strong",
                "tools": [{"slug": "a", "name": "A", "reason": "r", "summary": "x"}],
                "instruction": "第一句。第二句",
            },
            {"match_strength", "tools", "instruction", "_compacted"},
        ),
        (
            "search_tools",
            {
                "query": "立项",
                "tools": [{"slug": "a", "name": "A", "summary": "长摘要"}],
            },
            {"query", "tools", "_compacted"},
        ),
        (
            "export_markdown",
            {"ok": True, "path": "/tmp/x.md", "doc_type": "charter", "bytes": 100},
            {"ok", "path", "doc_type", "_compacted"},
        ),
    ],
)
def test_compact_tool_message_shapes(
    name: str,
    payload: dict,
    expected_keys: set[str],
) -> None:
    out = json.loads(compact_tool_message(name, json.dumps(payload, ensure_ascii=False)))
    assert expected_keys <= set(out.keys())
    if name == "search_tools":
        assert "summary" not in out["tools"][0]
