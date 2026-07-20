"""CLI 结果层渲染：TTY 下 Markdown，管道下纯文本。"""

from __future__ import annotations

import sys
from typing import TextIO

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.theme import Theme

# 去掉 inline code / code block 的 on black 底色，避免终端大块黑底。
_CLI_MARKDOWN_THEME = Theme(
    {
        "markdown.code": "bold cyan",
        "markdown.code_block": "cyan",
    }
)


def print_assistant_reply(reply: str, *, stream: TextIO | None = None) -> None:
    """打印助手最终回复；仅 TTY 用 rich 渲染 Markdown。"""
    out = stream if stream is not None else sys.stdout
    if out.isatty():
        console = Console(file=out, theme=_CLI_MARKDOWN_THEME)
        console.print(Text("● "), end="")
        console.print(Markdown(reply))
    else:
        print(f"● {reply}", file=out, flush=True)
