"""导出路径白名单与写盘。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pm_agent.agent.session import CharterDraft, SessionState
from pm_agent.config import REPO_ROOT
from pm_agent.export.path_guard import (
    PathGuardError,
    resolve_safe_output_file,
    sanitize_filename,
)
from pm_agent.export.render import render_charter_markdown
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.bootstrap import build_registry


def test_sanitize_rejects_path_escape() -> None:
    with pytest.raises(PathGuardError):
        sanitize_filename("../etc/passwd.md")
    with pytest.raises(PathGuardError):
        sanitize_filename("/tmp/evil.md")
    with pytest.raises(PathGuardError):
        sanitize_filename("subdir/file.md")


def test_resolve_safe_output_file_under_tmp(tmp_path: Path) -> None:
    path = resolve_safe_output_file(tmp_path, "项目章程-demo.md")
    assert path.parent == tmp_path.resolve()
    assert path.name == "项目章程-demo.md"


def test_export_rejects_escape_filename(tmp_path: Path) -> None:
    state = SessionState()
    state.charter_draft = CharterDraft(project_name="X")
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    raw = registry.execute(
        "export_markdown",
        {
            "doc_type": "charter",
            "confirmed": True,
            "filename": "../../evil.md",
        },
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "路径" in payload["instruction"] or ".." in payload["instruction"]


def test_export_charter_writes_markdown(tmp_path: Path) -> None:
    state = SessionState()
    state.charter_draft = CharterDraft(
        project_name="学习型 PM Agent",
        sponsor="自己",
        business_case="练手造 Agent",
    )
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    raw = registry.execute(
        "export_markdown",
        {
            "doc_type": "charter",
            "confirmed": True,
            "filename": "项目章程-test.md",
        },
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    out = Path(payload["path"])
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "学习型 PM Agent" in text
    assert "练手造 Agent" in text
    assert "# 项目章程" in text


def test_export_requires_confirmation(tmp_path: Path) -> None:
    state = SessionState()
    state.charter_draft = CharterDraft(project_name="X")
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = build_registry(
        repo,
        session=state,
        output_dir=tmp_path,
        include_demo_tools=False,
    )
    raw = registry.execute(
        "export_markdown",
        {"doc_type": "charter", "confirmed": False},
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "确认" in payload["instruction"]


def test_render_charter_contains_fields() -> None:
    md = render_charter_markdown(
        CharterDraft(project_name="P1", sponsor="S1")
    )
    assert "P1" in md
    assert "S1" in md
