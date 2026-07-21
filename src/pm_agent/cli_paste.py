"""CLI 大块粘贴：占位符、组装注入文本、提交时回退检测。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pm_agent.cli_attach import MAX_FILE_BYTES
from pm_agent.cli_text_budget import truncate_utf8

PASTE_MIN_LINES = 10
PASTE_MIN_BYTES = 2048

_PASTE_PLACEHOLDER = re.compile(r"\[paste\] \+(\d+) lines")


@dataclass(frozen=True)
class PasteBlock:
    """TTY 侧车保存的粘贴块（按出现顺序）。"""

    content: str


@dataclass(frozen=True)
class PasteItem:
    ok: bool
    content: str = ""
    line_count: int = 0
    size_bytes: int = 0
    truncated: bool = False
    reason: str = ""


@dataclass(frozen=True)
class PasteResult:
    user_text: str
    assembled: str
    items: tuple[PasteItem, ...]

    @property
    def should_enter_loop(self) -> bool:
        if self.user_text.strip():
            return True
        return any(i.ok for i in self.items)


def count_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def should_fold_paste(text: str) -> bool:
    if count_lines(text) >= PASTE_MIN_LINES:
        return True
    return len(text.encode("utf-8")) >= PASTE_MIN_BYTES


def format_paste_placeholder(line_count: int) -> str:
    return f"[paste] +{line_count} lines"


def format_paste_line(item: PasteItem) -> str:
    if item.ok:
        kb = (
            max(1, (item.size_bytes + 1023) // 1024) if item.size_bytes >= 1024 else None
        )
        size = f"{kb}KB" if kb is not None else f"{item.size_bytes} B"
        extra = ", truncated" if item.truncated else ""
        return f"[paste] ok  (+{item.line_count} lines, {size}{extra})"
    return f"[paste] fail  (+{item.line_count} lines)  {item.reason}"


def extract_paste_placeholders(text: str) -> tuple[str, list[int]]:
    line_counts: list[int] = []

    def _repl(match: re.Match[str]) -> str:
        line_counts.append(int(match.group(1)))
        return ""

    stripped = _PASTE_PLACEHOLDER.sub(_repl, text)
    user_text = re.sub(r"\s+", " ", stripped).strip()
    return user_text, line_counts


def _load_paste_content(
    content: str,
    *,
    remaining_budget: int,
) -> PasteItem:
    line_count = count_lines(content)
    size_bytes = len(content.encode("utf-8"))
    if remaining_budget <= 0:
        return PasteItem(
            ok=False,
            line_count=line_count,
            size_bytes=size_bytes,
            reason="合计体积已满，未载入",
        )
    limit = min(MAX_FILE_BYTES, remaining_budget)
    truncated_content, truncated = truncate_utf8(content, limit)
    return PasteItem(
        ok=True,
        content=truncated_content,
        line_count=line_count,
        size_bytes=size_bytes,
        truncated=truncated,
    )


def _paste_budget_used(item: PasteItem) -> int:
    if not item.ok:
        return 0
    raw = item.content.removesuffix("\n\n…[内容已截断]")
    return min(item.size_bytes, MAX_FILE_BYTES, len(raw.encode("utf-8")))


def _assemble_paste_blocks(
    user_text: str,
    ok_items: list[PasteItem],
) -> str:
    if not ok_items:
        return user_text
    blocks: list[str] = []
    for idx, item in enumerate(ok_items, start=1):
        header = (
            f"[粘贴材料 {idx}] lines={item.line_count} "
            f"truncated={'true' if item.truncated else 'false'}"
        )
        blocks.append(f"---\n{header}\n{item.content}")
    body = "\n".join(blocks)
    return f"{user_text}\n\n{body}" if user_text else body


def resolve_pastes(
    raw: str,
    *,
    pastes: tuple[PasteBlock, ...] = (),
    remaining_budget: int,
) -> PasteResult:
    user_text, placeholder_counts = extract_paste_placeholders(raw)

    if pastes:
        items: list[PasteItem] = []
        budget = remaining_budget
        for block in pastes:
            item = _load_paste_content(block.content, remaining_budget=budget)
            items.append(item)
            if item.ok:
                budget -= _paste_budget_used(item)
        ok_items = [i for i in items if i.ok]
        assembled = _assemble_paste_blocks(user_text, ok_items)
        return PasteResult(user_text=user_text, assembled=assembled, items=tuple(items))

    if placeholder_counts:
        return PasteResult(user_text=user_text, assembled=user_text, items=())

    detected_user, detected_blocks = detect_inline_paste(raw)
    if not detected_blocks:
        return PasteResult(user_text=raw, assembled=raw, items=())

    items = []
    budget = remaining_budget
    for block in detected_blocks:
        item = _load_paste_content(block.content, remaining_budget=budget)
        items.append(item)
        if item.ok:
            budget -= _paste_budget_used(item)
    ok_items = [i for i in items if i.ok]
    assembled = _assemble_paste_blocks(detected_user, ok_items)
    return PasteResult(user_text=detected_user, assembled=assembled, items=tuple(items))


def _edge_penalty(edge_lines: list[str], adjacent_middle_line: str) -> int:
    if not edge_lines:
        return 0
    edge = edge_lines[-1]
    edge_tokens = edge.split()[:2]
    middle_tokens = adjacent_middle_line.split()[:2]
    if edge_tokens and edge_tokens == middle_tokens:
        return 10_000
    return 0


def _best_inline_split(lines: list[str]) -> tuple[int, int, int, int] | None:
    """返回 (prefix_n, suffix_n, penalty, middle_len) 最优拆分，无则 None。"""
    n = len(lines)
    best: tuple[int, int, int, int] | None = None
    for prefix_n in range(0, 4):
        for suffix_n in range(0, 4):
            if prefix_n + suffix_n >= n:
                continue
            prefix = lines[:prefix_n]
            suffix = lines[n - suffix_n :] if suffix_n else []
            if any(len(line) >= 200 for line in prefix + suffix):
                continue
            middle = lines[prefix_n : n - suffix_n]
            middle_text = "\n".join(middle)
            if not should_fold_paste(middle_text):
                continue
            penalty = 0
            if prefix_n:
                penalty += _edge_penalty(prefix, middle[0])
            if suffix_n:
                penalty += _edge_penalty(suffix, middle[-1])
            if prefix_n == 0 and suffix_n == 0:
                penalty += 1
            score = (penalty, -len(middle), -(prefix_n + suffix_n))
            if best is None:
                best = (prefix_n, suffix_n, penalty, len(middle))
                continue
            best_score = (best[2], -best[3], -(best[0] + best[1]))
            if score < best_score:
                best = (prefix_n, suffix_n, penalty, len(middle))
    return best


def detect_inline_paste(raw: str) -> tuple[str, tuple[PasteBlock, ...]]:
    if _PASTE_PLACEHOLDER.search(raw):
        return raw, ()
    if not should_fold_paste(raw):
        return raw, ()

    lines = raw.splitlines()
    split = _best_inline_split(lines)
    if split is None:
        return raw, ()

    prefix_n, suffix_n, _, _ = split
    n = len(lines)
    middle_lines = lines[prefix_n : n - suffix_n]
    middle_text = "\n".join(middle_lines)

    parts: list[str] = []
    if prefix_n:
        parts.append("\n".join(lines[:prefix_n]).strip())
    if suffix_n:
        parts.append("\n".join(lines[n - suffix_n :]).strip())
    user_text = " ".join(p for p in parts if p)

    return user_text, (PasteBlock(content=middle_text),)
