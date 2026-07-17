"""CLI 结果层渲染：TTY 下 Markdown，管道下纯文本。"""

from __future__ import annotations

import sys
from typing import TextIO

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text


def print_assistant_reply(reply: str, *, stream: TextIO | None = None) -> None:
    """打印助手最终回复；仅 TTY 用 rich 渲染 Markdown。"""
    out = stream if stream is not None else sys.stdout
    if out.isatty():
        console = Console(file=out)
        console.print(Text("● "), end="")
        console.print(Markdown(reply))
    else:
        print(f"● {reply}", file=out, flush=True)
