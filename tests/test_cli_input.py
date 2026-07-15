"""slash 前缀补全与非 TTY 读入回退。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from prompt_toolkit.document import Document

from pm_agent.cli_input import (
    SlashCompleter,
    matching_slash_commands,
    read_user_line,
)


def test_matching_slash_root() -> None:
    cmds = [c for c, _ in matching_slash_commands("/")]
    assert cmds == ["/help", "/quit", "/debug", "/dump"]


def test_matching_slash_help_prefix() -> None:
    cmds = [c for c, _ in matching_slash_commands("/h")]
    assert cmds == ["/help"]


def test_matching_slash_quit_prefix() -> None:
    cmds = [c for c, _ in matching_slash_commands("/q")]
    assert cmds == ["/quit"]


def test_matching_slash_dump_prefix() -> None:
    cmds = [c for c, _ in matching_slash_commands("/du")]
    assert cmds == ["/dump"]


def test_matching_slash_d_prefix() -> None:
    cmds = [c for c, _ in matching_slash_commands("/d")]
    assert cmds == ["/debug", "/dump"]


def test_matching_non_slash_empty() -> None:
    assert matching_slash_commands("你好") == []
    assert matching_slash_commands("") == []
    assert matching_slash_commands("help") == []


def test_completer_yields_help_for_h() -> None:
    completer = SlashCompleter()
    completions = list(
        completer.get_completions(Document("/h"), complete_event=MagicMock())
    )
    assert len(completions) == 1
    assert completions[0].text == "/help"
    assert completions[0].start_position == -2


def test_read_user_line_falls_back_when_not_tty() -> None:
    with (
        patch("pm_agent.cli_input.sys.stdin") as mock_stdin,
        patch("pm_agent.cli_input.input", return_value="  hello  ") as mock_input,
    ):
        mock_stdin.isatty.return_value = False
        assert read_user_line("> ") == "  hello  "
        mock_input.assert_called_once_with("> ")
