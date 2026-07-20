"""阶段 5：PRD 边界与 Fake 验收路径。"""

from __future__ import annotations

from pathlib import Path

import pytest

from pm_agent.agent.llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.session import SessionState
from pm_agent.cli import EMPTY_INPUT_HINT
from pm_agent.config import REPO_ROOT
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.bootstrap import build_registry, build_registry_from_path


def test_empty_input_hint_matches_prd() -> None:
    assert "下周要立项还没授权" in EMPTY_INPUT_HINT


def test_fake_rejects_unsupported_draft() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    state = SessionState()
    registry = build_registry(
        repo,
        session=state,
        output_dir=REPO_ROOT / "output",
    )
    text = "帮我起草干系人登记册"
    reply = handle_user_turn(
        text,
        state,
        FakeLlmClient(demo_script_for_user_text(text)),
        registry,
        max_iterations=10,
    )
    assert "仅支持" in reply or "不支持" in reply
    assert "项目章程" in reply
    assert "风险登记册" in reply
    tool_names = [m.get("name") for m in state.messages if m.get("role") == "tool"]
    assert "get_tool_detail" in tool_names
    assert "draft_project_charter" not in tool_names


def test_fake_charter_export_path(tmp_path: Path) -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    state = SessionState()
    registry = build_registry(repo, session=state, output_dir=tmp_path)
    handle_user_turn(
        "帮我起草项目章程",
        state,
        FakeLlmClient(demo_script_for_user_text("帮我起草项目章程")),
        registry,
    )
    reply = handle_user_turn(
        "确认导出",
        state,
        FakeLlmClient(demo_script_for_user_text("确认导出")),
        registry,
    )
    assert "导出" in reply
    files = list(tmp_path.glob("*.md"))
    assert files
    assert "学习型 PM Agent" in files[0].read_text(encoding="utf-8")


def test_missing_tools_json_raises(tmp_path: Path) -> None:
    missing = tmp_path / "no-tools.json"
    with pytest.raises(FileNotFoundError):
        build_registry_from_path(
            missing,
            session=SessionState(),
            output_dir=tmp_path,
        )
