"""集成终端 Shift+Enter 键位配置（Cursor / VS Code）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SHIFT_ENTER_SEQUENCE = "\u001b[13;2u"

SHIFT_ENTER_BINDING: dict[str, Any] = {
    "key": "shift+enter",
    "command": "workbench.action.terminal.sendSequence",
    "args": {"text": SHIFT_ENTER_SEQUENCE},
    "when": "terminalFocus",
}


def is_integrated_terminal() -> bool:
    """是否为 VS Code / Cursor 集成终端。"""
    return os.environ.get("TERM_PROGRAM") == "vscode"


def _is_cursor() -> bool:
    if os.environ.get("CURSOR_TRACE_ID") or os.environ.get("CURSOR_SESSION_ID"):
        return True
    node = (os.environ.get("VSCODE_GIT_ASKPASS_NODE") or "").lower()
    return "cursor" in node


def keybindings_path() -> Path | None:
    """返回当前编辑器用户 keybindings.json 路径。"""
    app_name = "Cursor" if _is_cursor() else "Code"
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / app_name / "User" / "keybindings.json"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return Path(appdata) / app_name / "User" / "keybindings.json"
    return home / ".config" / app_name / "User" / "keybindings.json"


def has_shift_enter_binding(path: Path | None = None) -> bool:
    """keybindings 是否已包含 pmbox 所需的 Shift+Enter 序列。"""
    target = path if path is not None else keybindings_path()
    if target is None or not target.is_file():
        return False
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return False
    return "13;2u" in text or SHIFT_ENTER_SEQUENCE in text


def _load_keybindings(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        msg = "keybindings.json 格式异常：期望 JSON 数组"
        raise ValueError(msg)
    return data


def _binding_matches(item: dict[str, Any]) -> bool:
    if item.get("key") != "shift+enter":
        return False
    args = item.get("args")
    if not isinstance(args, dict):
        return False
    text = args.get("text")
    return text == SHIFT_ENTER_SEQUENCE


def setup_terminal_keybinding() -> str:
    """写入 Shift+Enter 键位；返回给用户的状态说明。"""
    if not is_integrated_terminal():
        return (
            "[terminal] 当前不是 VS Code / Cursor 集成终端。\n"
            "原生终端（iTerm2、Ghostty 等）一般无需 /setup-terminal。\n"
            "若 Shift+Enter 无效，可临时用 Ctrl+J 换行。"
        )

    path = keybindings_path()
    if path is None:
        return "[terminal] 无法定位 keybindings.json，请手动配置 Shift+Enter。"

    editor = "Cursor" if _is_cursor() else "VS Code"
    if has_shift_enter_binding(path):
        return (
            f"[terminal] {editor} 已配置 Shift+Enter → {path}\n"
            "请重新打开终端标签页后重试。"
        )

    bindings: list[dict[str, Any]] = []
    if path.is_file():
        try:
            bindings = _load_keybindings(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return (
                f"[terminal] 读取 {path} 失败：{exc}\n"
                "请手动在 keybindings.json 追加：\n"
                f"{json.dumps(SHIFT_ENTER_BINDING, ensure_ascii=False, indent=2)}"
            )

    if any(_binding_matches(item) for item in bindings):
        return f"[terminal] {editor} 已存在 Shift+Enter 绑定：{path}"

    bindings.append(SHIFT_ENTER_BINDING)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bindings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return (
        f"[terminal] 已为 {editor} 写入 Shift+Enter 键位：{path}\n"
        "请关闭并重新打开集成终端标签页，再运行 pmbox 验证换行。"
    )


def integrated_terminal_hint() -> str | None:
    """集成终端且未配置时返回一行提示。"""
    if not is_integrated_terminal() or not sys.stdin.isatty():
        return None
    if has_shift_enter_binding():
        return None
    editor = "Cursor" if _is_cursor() else "VS Code"
    return (
        f"[hint] {editor} 集成终端下 Shift+Enter 默认等同 Enter；"
        "请先运行 /setup-terminal（仅一次），或临时用 Ctrl+J 换行。"
    )
