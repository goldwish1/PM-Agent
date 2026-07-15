"""交互读入：slash 命令前缀补全；非 TTY 回退标准 input()。"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.shortcuts import CompleteStyle

# (命令, 说明) — 仅 slash 元指令进入补全列表
SLASH_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/help", "显示本说明"),
    ("/quit", "结束进程"),
    ("/debug", "切换 [llm] 终端摘要"),
    ("/dump", "切换 debug JSON 落盘"),
)


def matching_slash_commands(typed: str) -> list[tuple[str, str]]:
    """按前缀过滤 slash 命令；typed 非以 / 开头时返回空。"""
    if not typed.startswith("/"):
        return []
    return [(cmd, desc) for cmd, desc in SLASH_COMMANDS if cmd.startswith(typed)]


class SlashCompleter(Completer):
    """仅在输入以 / 开头时提供 slash 元指令补全。"""

    def get_completions(
        self,
        document: Document,
        complete_event: Any,
    ) -> Iterable[Completion]:
        typed = document.text_before_cursor.lstrip()
        for cmd, desc in matching_slash_commands(typed):
            yield Completion(
                cmd,
                start_position=-len(typed),
                display=cmd,
                display_meta=desc,
            )


def read_user_line(prompt_text: str = "> ") -> str:
    """TTY 下用 prompt_toolkit（边打边补）；管道/非交互回退 input()。"""
    if not sys.stdin.isatty():
        return input(prompt_text)
    return prompt(
        prompt_text,
        completer=SlashCompleter(),
        complete_while_typing=True,
        complete_style=CompleteStyle.COLUMN,
    )
