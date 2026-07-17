"""章程字段合并与风险条目限制。"""

from __future__ import annotations

import json
from pathlib import Path

from pm_agent.agent.session import (
    MAX_MATRIX_CRITERIA,
    MAX_MATRIX_OPTIONS,
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


def test_decision_matrix_merge_flat_and_lists(tmp_path: Path) -> None:
    state = SessionState()
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    raw = registry.execute(
        "draft_decision_matrix",
        {
            "title": "选型矩阵",
            "replace_criteria": True,
            "criteria": [
                {"criterion_id": "C01", "name": "成本", "weight": "40%"},
                {"criterion_id": "C02", "name": "周期", "weight": "60%"},
            ],
            "replace_options": True,
            "options": [
                {
                    "option_id": "O01",
                    "name": "自研",
                    "scores": {"C01": "7", "C02": "5"},
                    "weighted_total": "5.8",
                },
                {
                    "option_id": "O02",
                    "name": "外采",
                    "scores": {"C01": "8", "C02": "8"},
                    "weighted_total": "8.0",
                },
            ],
            "recommended_option": "外采",
            "rationale": "周期与成本综合更优",
        },
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert state.matrix_draft is not None
    assert state.matrix_draft.title == "选型矩阵"
    assert len(state.matrix_draft.criteria) == 2
    assert len(state.matrix_draft.options) == 2
    assert state.matrix_draft.options[1].weighted_total == "8.0"

    raw2 = registry.execute(
        "draft_decision_matrix",
        {"context": "预算 50 万"},
    )
    assert json.loads(raw2)["ok"] is True
    assert state.matrix_draft.context == "预算 50 万"
    assert state.matrix_draft.title == "选型矩阵"


def test_decision_matrix_truncates_excess_criteria(tmp_path: Path) -> None:
    state = SessionState()
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    criteria = [
        {"criterion_id": f"C{i:02d}", "name": f"准则{i}", "weight": "10%"}
        for i in range(1, MAX_MATRIX_CRITERIA + 2)
    ]
    raw = registry.execute(
        "draft_decision_matrix",
        {"replace_criteria": True, "criteria": criteria},
    )
    payload = json.loads(raw)
    assert state.matrix_draft is not None
    assert len(state.matrix_draft.criteria) == MAX_MATRIX_CRITERIA
    assert "截断" in payload["warning"] or str(MAX_MATRIX_CRITERIA) in payload["warning"]


def test_decision_matrix_rejects_excess_options(tmp_path: Path) -> None:
    state = SessionState()
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    options = [
        {"option_id": f"O{i:02d}", "name": f"方案{i}", "weighted_total": "1"}
        for i in range(1, MAX_MATRIX_OPTIONS + 2)
    ]
    raw = registry.execute(
        "draft_decision_matrix",
        {"replace_options": True, "options": options},
    )
    payload = json.loads(raw)
    assert state.matrix_draft is not None
    assert len(state.matrix_draft.options) == MAX_MATRIX_OPTIONS
    assert "截断" in payload["warning"] or str(MAX_MATRIX_OPTIONS) in payload["warning"]
