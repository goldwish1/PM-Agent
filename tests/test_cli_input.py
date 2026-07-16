"""cli_input：slash 命令与 @ 文件补全。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from prompt_toolkit.document import Document

from pm_agent.cli_input import (
    PmboxCompleter,
    SlashCompleter,
    _accept_current_completion,
    extract_attach_fragment,
    format_attach_completion,
    list_attach_candidates,
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


def test_extract_attach_fragment_in_middle_of_line() -> None:
    fragment = extract_attach_fragment("下周立项 @doc/需")
    assert fragment is not None
    assert fragment.raw == "@doc/需"
    assert fragment.path_prefix == "doc/需"
    assert fragment.quoted is False


def test_extract_attach_fragment_supports_quoted_path() -> None:
    fragment = extract_attach_fragment('看这个 @"我的 纪')
    assert fragment is not None
    assert fragment.raw == '@"我的 纪'
    assert fragment.path_prefix == "我的 纪"
    assert fragment.quoted is True


def test_extract_attach_fragment_ignores_email_like_input() -> None:
    assert extract_attach_fragment("联系 test@example.com") is None


def test_extract_attach_fragment_stops_after_unquoted_path() -> None:
    assert extract_attach_fragment("下周立项 @doc/foo.md 从") is None
    assert extract_attach_fragment("下周立项 @doc/foo.md") is not None


def test_list_attach_candidates_filters_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "doc" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "doc" / "skip.json").write_text("{}", encoding="utf-8")
    (tmp_path / "other.md").write_text("o", encoding="utf-8")

    candidates = list_attach_candidates("doc/", cwd=tmp_path)

    assert candidates == ["doc/a.md", "doc/b.txt"]


def test_list_attach_candidates_can_match_basename_prefix(tmp_path: Path) -> None:
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "需求孵化.md").write_text("x", encoding="utf-8")

    candidates = list_attach_candidates("需求", cwd=tmp_path)

    assert candidates == ["doc/需求孵化.md"]


def test_list_attach_candidates_skips_hidden_noise_dirs(tmp_path: Path) -> None:
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "README.md").write_text("cache", encoding="utf-8")
    (tmp_path / "README.md").write_text("real", encoding="utf-8")

    candidates = list_attach_candidates("rea", cwd=tmp_path)

    assert candidates == ["README.md"]


def test_format_attach_completion_quotes_spaces() -> None:
    assert format_attach_completion("doc/需求孵化.md") == "@doc/需求孵化.md"
    assert format_attach_completion("doc/my notes.md") == '@"doc/my notes.md"'


def test_completer_returns_slash_matches_first() -> None:
    completions = list(PmboxCompleter().get_completions(Document("/h"), None))

    assert [item.text for item in completions] == ["/help"]


def test_completer_returns_attach_matches(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "doc").mkdir()
    (tmp_path / "doc" / "需求孵化.md").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    completions = list(
        PmboxCompleter().get_completions(Document("下周立项 @doc/需"), None)
    )

    assert [item.text for item in completions] == ["@doc/需求孵化.md"]


def test_accept_current_completion_applies_selected_item() -> None:
    completion = MagicMock(text="@README.md")
    state = MagicMock(current_completion=completion, completions=[completion], complete_index=0)
    buffer = MagicMock(complete_state=state, text="@rea")
    event = MagicMock(current_buffer=buffer)

    accepted = _accept_current_completion(event)

    assert accepted is True
    buffer.apply_completion.assert_called_once_with(completion)


def test_accept_current_completion_falls_back_to_first_item() -> None:
    first = MagicMock(text="@README.md")
    second = MagicMock(text="@README-2.md")
    state = MagicMock(current_completion=None, completions=[first, second], complete_index=None)
    buffer = MagicMock(complete_state=state, text="@rea")
    event = MagicMock(current_buffer=buffer)

    accepted = _accept_current_completion(event)

    assert accepted is True
    buffer.apply_completion.assert_called_once_with(first)
