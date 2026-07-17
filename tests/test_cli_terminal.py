"""cli_terminal：集成终端 Shift+Enter 配置。"""

from __future__ import annotations

import json
from pathlib import Path

from pm_agent.cli_terminal import (
    SHIFT_ENTER_BINDING,
    has_shift_enter_binding,
    is_integrated_terminal,
    setup_terminal_keybinding,
)


def test_has_shift_enter_binding_detects_sequence(tmp_path: Path) -> None:
    path = tmp_path / "keybindings.json"
    path.write_text(
        json.dumps([SHIFT_ENTER_BINDING], ensure_ascii=False),
        encoding="utf-8",
    )
    assert has_shift_enter_binding(path) is True


def test_setup_terminal_writes_binding(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "keybindings.json"
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.setenv("CURSOR_TRACE_ID", "test")
    monkeypatch.setattr("pm_agent.cli_terminal.keybindings_path", lambda: path)

    message = setup_terminal_keybinding()

    assert "写入 Shift+Enter" in message
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[-1]["key"] == "shift+enter"


def test_is_integrated_terminal() -> None:
    assert is_integrated_terminal.__module__ == "pm_agent.cli_terminal"
