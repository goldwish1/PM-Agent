"""cli_render：TTY Markdown / 非 TTY 纯文本。"""

from __future__ import annotations

from io import StringIO

from pm_agent.cli_render import print_assistant_reply


class _NonTtyIO(StringIO):
    def isatty(self) -> bool:
        return False


class _TtyIO(StringIO):
    def isatty(self) -> bool:
        return True


def test_plain_passthrough_when_not_tty() -> None:
    buf = _NonTtyIO()
    print_assistant_reply("你好 **粗体** |表|", stream=buf)
    out = buf.getvalue()
    assert out.startswith("● ")
    assert "**粗体**" in out
    assert "|表|" in out


def test_markdown_markers_consumed_on_tty() -> None:
    buf = _TtyIO()
    print_assistant_reply("你好 **粗体** 世界", stream=buf)
    out = buf.getvalue()
    assert out.startswith("● ")
    assert "粗体" in out
    assert "**" not in out
