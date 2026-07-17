"""陪跑咨询：状态机与 start_consulting / note_consulting_fact。"""

from __future__ import annotations

import json
from pathlib import Path

from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.config import REPO_ROOT
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.bootstrap import build_registry


def _registry(state: SessionState, output_dir: Path | None = None):
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    return build_registry(
        repo,
        session=state,
        output_dir=output_dir or (REPO_ROOT / "output"),
        include_demo_tools=False,
    )


def test_start_consulting_draftable_tools() -> None:
    for slug in ("project-charter", "risk-register", "decision-matrix", "decision-record"):
        state = SessionState()
        registry = _registry(state)
        raw = registry.execute("start_consulting", {"tool_slug": slug})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["slug"] == slug
        assert "steps" in payload and payload["steps"]
        assert "scenarios" in payload
        assert state.mode == SessionMode.CONSULTING
        assert state.consulting_tool_slug == slug


def test_start_consulting_rejects_non_draftable() -> None:
    state = SessionState(mode=SessionMode.RECOMMENDING)
    registry = _registry(state)
    raw = registry.execute("start_consulting", {"tool_slug": "swot-analysis"})
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "draftable" in payload or "error" in payload
    assert state.mode == SessionMode.RECOMMENDING
    assert state.consulting_tool_slug is None


def test_start_consulting_rejects_wbs() -> None:
    state = SessionState(mode=SessionMode.RECOMMENDING)
    registry = _registry(state)
    raw = registry.execute("start_consulting", {"tool_slug": "wbs"})
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "draftable" in payload or "error" in payload
    assert state.mode == SessionMode.RECOMMENDING
    assert state.consulting_tool_slug is None


def test_start_consulting_rejects_unknown_slug() -> None:
    state = SessionState(mode=SessionMode.RECOMMENDING)
    registry = _registry(state)
    raw = registry.execute("start_consulting", {"tool_slug": "not-a-real-tool"})
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert state.mode == SessionMode.RECOMMENDING
    assert state.consulting_tool_slug is None


def test_note_fact_rejected_outside_consulting() -> None:
    state = SessionState(mode=SessionMode.IDLE)
    registry = _registry(state)
    raw = registry.execute(
        "note_consulting_fact",
        {"fact": "预算约 50 万"},
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert state.consulting_notes == []


def test_note_fact_accumulates_in_consulting() -> None:
    state = SessionState()
    registry = _registry(state)
    registry.execute("start_consulting", {"tool_slug": "project-charter"})
    r1 = json.loads(
        registry.execute(
            "note_consulting_fact",
            {"fact": "预算约 50 万，需在 8 月底前完成立项"},
        )
    )
    r2 = json.loads(
        registry.execute(
            "note_consulting_fact",
            {"fact": "发起人为张三，项目经理为李四"},
        )
    )
    assert r1["ok"] is True
    assert r1["notes_count"] == 1
    assert r2["ok"] is True
    assert r2["notes_count"] == 2
    assert state.consulting_notes == [
        "预算约 50 万，需在 8 月底前完成立项",
        "发起人为张三，项目经理为李四",
    ]


def test_draft_after_consulting_notes_in_preview() -> None:
    state = SessionState()
    registry = _registry(state)
    registry.execute("start_consulting", {"tool_slug": "project-charter"})
    registry.execute(
        "note_consulting_fact",
        {"fact": "预算约 50 万，需在 8 月底前完成立项"},
    )
    registry.execute(
        "note_consulting_fact",
        {"fact": "项目名称为学习型 PM Agent，发起人张三"},
    )
    # 模拟 LLM 基于 consulting_notes 提炼后传参
    raw = registry.execute(
        "draft_project_charter",
        {
            "project_name": "学习型 PM Agent",
            "sponsor": "张三",
            "budget": "约 50 万，需在 8 月底前完成立项",
        },
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["consulting_notes_available"] is True
    assert len(payload["consulting_notes"]) == 2
    preview_text = "\n".join(payload["preview"])
    assert "学习型 PM Agent" in preview_text
    assert "张三" in preview_text
    assert "50 万" in preview_text
    assert state.mode == SessionMode.DRAFTING_CHARTER
    assert state.consulting_notes  # 起草后 notes 不丢失


def test_draft_without_consulting_still_works() -> None:
    state = SessionState()
    registry = _registry(state)
    raw = registry.execute(
        "draft_project_charter",
        {"project_name": "Demo", "business_case": "练手"},
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["consulting_notes_available"] is False
    assert "consulting_notes" not in payload
    assert state.charter_draft is not None
    assert state.charter_draft.project_name == "Demo"
