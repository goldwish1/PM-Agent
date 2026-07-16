"""CLI @附件：解析路径、读 .md/.txt、组装注入文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AttachMention:
    raw: str
    path_text: str
    start: int
    end: int


_QUOTED = re.compile(r'@(?:"([^"]+)"|\'([^\']+)\')')
_BARE = re.compile(r"@([^\s@]+)")


def looks_like_attach_path(path_text: str) -> bool:
    p = path_text.strip()
    if not p:
        return False
    lower = p.lower()
    if lower.endswith(".md") or lower.endswith(".txt"):
        return True
    if p.startswith("./") or p.startswith("../"):
        return True
    if "/" in p:
        return True
    return False


def extract_mentions(text: str) -> list[AttachMention]:
    mentions: list[AttachMention] = []
    used: list[tuple[int, int]] = []

    def _overlap(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in used)

    for cre in (_QUOTED, _BARE):
        for m in cre.finditer(text):
            start, end = m.span()
            if _overlap(start, end):
                continue
            if cre is _QUOTED:
                path_text = m.group(1) if m.group(1) is not None else m.group(2)
            else:
                path_text = m.group(1)
            if not looks_like_attach_path(path_text):
                continue
            used.append((start, end))
            mentions.append(
                AttachMention(raw=m.group(0), path_text=path_text, start=start, end=end)
            )
    mentions.sort(key=lambda x: x.start)
    return mentions


def strip_mentions(text: str, mentions: list[AttachMention]) -> str:
    if not mentions:
        return text
    parts: list[str] = []
    cursor = 0
    for m in sorted(mentions, key=lambda x: x.start):
        parts.append(text[cursor : m.start])
        cursor = m.end
    parts.append(text[cursor:])
    joined = "".join(parts)
    return re.sub(r"\s+", " ", joined).strip()
