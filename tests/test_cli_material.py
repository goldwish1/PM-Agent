"""cli_material：attach + paste 统一编排。"""

from __future__ import annotations

from pathlib import Path

from pm_agent.cli_material import resolve_user_material
from pm_agent.cli_paste import PasteBlock, format_paste_placeholder


def test_resolve_attach_only(tmp_path: Path) -> None:
    f = tmp_path / "kickoff.md"
    f.write_text("立项内容\n", encoding="utf-8")
    result = resolve_user_material("下周立项 @kickoff.md 请推荐", cwd=tmp_path)
    assert result.should_enter_loop is True
    assert "立项内容" in result.assembled
    assert any(line.startswith("[attach] ok") for line in result.status_lines)
    assert not any(line.startswith("[paste]") for line in result.status_lines)


def test_resolve_paste_only_with_sidecar() -> None:
    body = "\n".join(f"line{i}" for i in range(12))
    pastes = (PasteBlock(content=body),)
    raw = f"{format_paste_placeholder(12)}\n\n帮我总结"
    result = resolve_user_material(raw, pastes=pastes)
    assert result.should_enter_loop is True
    assert result.user_text == "帮我总结"
    assert body in result.assembled
    assert any(line.startswith("[paste] ok") for line in result.status_lines)


def test_resolve_attach_and_paste(tmp_path: Path) -> None:
    f = tmp_path / "notes.md"
    f.write_text("附件\n", encoding="utf-8")
    body = "\n".join(f"line{i}" for i in range(12))
    pastes = (PasteBlock(content=body),)
    raw = f"请推荐 @notes.md {format_paste_placeholder(12)}"
    result = resolve_user_material(raw, pastes=pastes, cwd=tmp_path)
    assert result.should_enter_loop is True
    assert "附件" in result.assembled
    assert body in result.assembled
    assert any(line.startswith("[attach] ok") for line in result.status_lines)
    assert any(line.startswith("[paste] ok") for line in result.status_lines)


def test_resolve_empty_no_loop() -> None:
    result = resolve_user_material("   ")
    assert result.should_enter_loop is False
    assert result.status_lines == ()


def test_resolve_inline_paste_fallback() -> None:
    body = "\n".join(f"chat {i}" for i in range(15))
    raw = f"{body}\n帮我总结"
    result = resolve_user_material(raw)
    assert result.should_enter_loop is True
    assert result.user_text == "帮我总结"
    assert body in result.assembled
