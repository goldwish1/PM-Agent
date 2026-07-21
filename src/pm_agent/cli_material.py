"""CLI 用户材料编排：@attach 与 [paste] 统一解析、共享预算。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pm_agent.cli_attach import (
    ATTACH_EMPTY_HINT,
    MAX_TOTAL_BYTES,
    AttachResult,
    format_attach_line,
    resolve_attachments,
)
from pm_agent.cli_paste import (
    PasteBlock,
    PasteResult,
    format_paste_line,
    resolve_pastes,
)

MATERIAL_EMPTY_HINT = (
    "未载入任何材料。请直接描述卡点、使用 @./notes.md 附带 .md/.txt，"
    "或粘贴长文本（自动折叠为 [paste]）后再试。"
)


@dataclass(frozen=True)
class MaterialResult:
    user_text: str
    assembled: str
    status_lines: tuple[str, ...]
    should_enter_loop: bool


def _attach_budget_used(attach: AttachResult) -> int:
    total = 0
    for item in attach.items:
        if item.ok:
            total += min(item.size_bytes, 64 * 1024)
    return total


def _merge_assembled(
    user_text: str,
    attach: AttachResult,
    paste: PasteResult,
) -> str:
    attach_blocks: list[str] = []
    for idx, item in enumerate((i for i in attach.items if i.ok), start=1):
        path_s = str(item.path) if item.path is not None else item.display_name
        header = (
            f"[附件 {idx}] path={path_s} name={item.display_name} "
            f"truncated={'true' if item.truncated else 'false'}"
        )
        attach_blocks.append(f"---\n{header}\n{item.content}")

    paste_blocks: list[str] = []
    for idx, item in enumerate((i for i in paste.items if i.ok), start=1):
        header = (
            f"[粘贴材料 {idx}] lines={item.line_count} "
            f"truncated={'true' if item.truncated else 'false'}"
        )
        paste_blocks.append(f"---\n{header}\n{item.content}")

    blocks = attach_blocks + paste_blocks
    if not blocks:
        return user_text
    body = "\n".join(blocks)
    return f"{user_text}\n\n{body}" if user_text else body


def resolve_user_material(
    raw: str,
    *,
    pastes: tuple[PasteBlock, ...] = (),
    cwd: Path | None = None,
    total_budget: int | None = None,
) -> MaterialResult:
    budget = MAX_TOTAL_BYTES if total_budget is None else total_budget
    attach = resolve_attachments(raw, cwd=cwd, total_budget=budget)
    attach_used = _attach_budget_used(attach)
    remaining = max(0, budget - attach_used)

    paste = resolve_pastes(
        attach.user_text,
        pastes=pastes,
        remaining_budget=remaining,
    )

    user_text = paste.user_text
    assembled = _merge_assembled(user_text, attach, paste)
    status_lines = tuple(
        [format_attach_line(item) for item in attach.items]
        + [format_paste_line(item) for item in paste.items]
    )
    should_enter_loop = bool(user_text.strip()) or any(
        i.ok for i in attach.items
    ) or any(i.ok for i in paste.items)

    return MaterialResult(
        user_text=user_text,
        assembled=assembled,
        status_lines=status_lines,
        should_enter_loop=should_enter_loop,
    )


# 兼容旧引用
EMPTY_HINT = MATERIAL_EMPTY_HINT
ATTACH_ONLY_EMPTY_HINT = ATTACH_EMPTY_HINT
