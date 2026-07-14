"""章程字段合并与风险条目限制。"""

from __future__ import annotations

import json
from pathlib import Path

from pm_agent.agent.session import (
    MAX_RISK_ITEMS,
    PLACEHOLDER,
    CharterDraft,
    SessionState,
)
from pm_agent.config import REPO_ROOT
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.bootstrap import build_registry


def test_charter_merge_keeps_placeholder_and_overrides() -> None:
    draft = CharterDraft()
    assert draft.project_name == PLACEHOLDER
    merged = draft.merge_patch(
        {
            "project_name": "学习型 PM Agent",
            "sponsor": "自己",
            "budget": None,
            "unknown_field": "ignore",
        }
    )
    assert merged.project_name == "学习型 PM Agent"
    assert merged.sponsor == "自己"
    assert merged.budget == PLACEHOLDER
    assert "budget" in merged.missing_fields()
    assert "project_name" not in merged.missing_fields()


def test_draft_project_charter_tool_merges_into_session() -> None:
    state = SessionState()
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=REPO_ROOT / "output",
        include_demo_tools=False,
    )
    raw = registry.execute(
        "draft_project_charter",
        {"project_name": "Demo", "business_case": "练手"},
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert state.charter_draft is not None
    assert state.charter_draft.project_name == "Demo"
    assert state.charter_draft.business_case == "练手"
    assert state.charter_draft.sponsor == PLACEHOLDER

    raw2 = registry.execute(
        "draft_project_charter",
        {"sponsor": "张三"},
    )
    assert json.loads(raw2)["ok"] is True
    assert state.charter_draft.project_name == "Demo"
    assert state.charter_draft.sponsor == "张三"


def test_risk_register_rejects_more_than_three(tmp_path: Path) -> None:
    state = SessionState()
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    items = [
        {"risk_id": f"R{i:02d}", "description": f"风险{i}"}
        for i in range(1, MAX_RISK_ITEMS + 2)
    ]
    raw = registry.execute(
        "draft_risk_register",
        {"replace_all": True, "items": items},
    )
    payload = json.loads(raw)
    assert state.risk_draft is not None
    assert len(state.risk_draft.items) == MAX_RISK_ITEMS
    assert "1～3" in payload["warning"] or "截断" in payload["warning"]
