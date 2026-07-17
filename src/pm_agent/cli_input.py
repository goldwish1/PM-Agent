"""交互读入：slash 命令与 @附件路径补全；非 TTY 回退标准 input()。"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts import CompleteStyle

# Shift+Enter 在多数终端会落成下列 CSI；prompt_toolkit 默认把它们当成 Enter。
# 重映射为 ControlJ，再由自定义绑定插入换行。
_SHIFT_ENTER_SEQUENCES: tuple[str, ...] = (
    "\x1b[27;2;13~",
    "\x1b[13;2u",
)


def _patch_shift_enter_sequences() -> None:
    for seq in _SHIFT_ENTER_SEQUENCES:
        ANSI_SEQUENCES[seq] = Keys.ControlJ


_patch_shift_enter_sequences()

# 本进程内共享：↑/↓ 回填已提交过的输入；进程结束即清空。
_history = InMemoryHistory()

# (命令, 说明) — 仅 slash 元指令进入补全列表
SLASH_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/help", "显示本说明"),
    ("/quit", "结束进程"),
    ("/tools", "浏览知识库工具"),
    ("/debug", "切换 [llm] 终端摘要"),
    ("/dump", "切换 debug JSON 落盘"),
)

ATTACH_SUFFIXES: tuple[str, ...] = (".md", ".txt")
IGNORED_ATTACH_DIR_NAMES: tuple[str, ...] = (
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    ".cursor",
    ".superpowers",
    "__pycache__",
)


@dataclass(frozen=True)
class AttachFragment:
    """光标前正在输入的 @ 附件片段。"""

    raw: str
    path_prefix: str
    quoted: bool


def matching_slash_commands(typed: str) -> list[tuple[str, str]]:
    """按前缀过滤 slash 命令；typed 非以 / 开头时返回空。"""
    if not typed.startswith("/"):
        return []
    return [(cmd, desc) for cmd, desc in SLASH_COMMANDS if cmd.startswith(typed)]


def extract_attach_fragment(text_before_cursor: str) -> AttachFragment | None:
    """提取光标前最后一个 @ 片段；仅在行首或空白后触发。"""
    marker = text_before_cursor.rfind("@")
    if marker < 0:
        return None
    if marker > 0 and not text_before_cursor[marker - 1].isspace():
        return None

    fragment = text_before_cursor[marker:]
    if not fragment.startswith("@"):
        return None
    if fragment.startswith('@"'):
        return AttachFragment(raw=fragment, path_prefix=fragment[2:], quoted=True)
    if fragment.startswith("@'"):
        return AttachFragment(raw=fragment, path_prefix=fragment[2:], quoted=True)
    # 未加引号的 @xxx 与 cli_attach 的 @([^\s@]+) 一致：片段内出现空白即结束附件补全。
    if any(ch.isspace() for ch in fragment[1:]):
        return None
    return AttachFragment(raw=fragment, path_prefix=fragment[1:], quoted=False)


def list_attach_candidates(
    path_prefix: str,
    *,
    cwd: Path | None = None,
) -> list[str]:
    """递归列出 cwd 下可补全的 .md/.txt 文件。"""
    base = cwd if cwd is not None else Path.cwd()
    prefix = path_prefix.strip().strip('"').strip("'").lower()
    candidates: list[str] = []
    for path in sorted(base.rglob("*")):
        parts = path.relative_to(base).parts
        if any(part in IGNORED_ATTACH_DIR_NAMES for part in parts[:-1]):
            continue
        if not path.is_file() or path.suffix.lower() not in ATTACH_SUFFIXES:
            continue
        rel = path.relative_to(base).as_posix()
        rel_lower = rel.lower()
        if prefix:
            basename_lower = path.name.lower()
            if "/" in prefix:
                if not rel_lower.startswith(prefix):
                    continue
            elif not (
                rel_lower.startswith(prefix) or basename_lower.startswith(prefix)
            ):
                continue
        candidates.append(rel)
    return candidates


def format_attach_completion(path_text: str) -> str:
    """将候选路径格式化为可直接输入的 @ 片段。"""
    if any(ch.isspace() for ch in path_text):
        return f'@"{path_text}"'
    return f"@{path_text}"


class PmboxCompleter(Completer):
    """组合补全：slash 命令优先，其次是 @ 文件补全。"""

    def get_completions(
        self,
        document: Document,
        complete_event: Any,
    ) -> Iterable[Completion]:
        typed = document.text_before_cursor.lstrip()
        slash_matches = matching_slash_commands(typed)
        if slash_matches:
            for cmd, desc in slash_matches:
                yield Completion(
                    cmd,
                    start_position=-len(typed),
                    display=cmd,
                    display_meta=desc,
                )
            return

        fragment = extract_attach_fragment(document.text_before_cursor)
        if fragment is None:
            return
        for candidate in list_attach_candidates(fragment.path_prefix):
            completion_text = format_attach_completion(candidate)
            yield Completion(
                completion_text,
                start_position=-len(fragment.raw),
                display=completion_text,
                display_meta="附件文件",
            )


class SlashCompleter(PmboxCompleter):
    """兼容旧测试与调用方命名；当前已升级为组合补全。"""


def _accept_current_completion(event: Any) -> bool:
    state = event.current_buffer.complete_state
    current = state.current_completion if state is not None else None
    if current is None and state is not None and state.completions:
        current = state.completions[0]
    if current is None:
        return False
    event.current_buffer.apply_completion(current)
    return True


def _build_input_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("tab")
    def _(event: Any) -> None:
        if _accept_current_completion(event):
            return
        get_by_name("complete").call(event)

    @kb.add("enter")
    def _(event: Any) -> None:
        if _accept_current_completion(event):
            return
        get_by_name("accept-line").call(event)

    @kb.add("c-j", eager=True)
    def _(event: Any) -> None:
        event.current_buffer.insert_text("\n")

    return kb


def read_user_line(prompt_text: str = "> ") -> str:
    """TTY 下用 prompt_toolkit（边打边补、多行输入）；管道/非交互回退 input()。"""
    if not sys.stdin.isatty():
        return input(prompt_text)
    return prompt(
        prompt_text,
        completer=PmboxCompleter(),
        history=_history,
        key_bindings=_build_input_key_bindings(),
        complete_while_typing=True,
        complete_style=CompleteStyle.COLUMN,
        multiline=True,
    )
