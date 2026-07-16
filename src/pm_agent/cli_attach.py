"""CLI @附件：解析路径、读 .md/.txt、组装注入文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 64 * 1024
MAX_TOTAL_BYTES = 128 * 1024
TRUNCATION_SUFFIX = "\n\n…[内容已截断]"
_ALLOWED_SUFFIX = {".md", ".txt"}


@dataclass(frozen=True)
class AttachMention:
    raw: str
    path_text: str
    start: int
    end: int


@dataclass(frozen=True)
class AttachItem:
    ok: bool
    display_name: str
    path: Path | None = None
    reason: str = ""
    content: str = ""
    truncated: bool = False
    size_bytes: int = 0


_QUOTED = re.compile(r'@(?:"([^"]+)"|\'([^\']+)\')')
_BARE = re.compile(r"@([^\s@]+)")


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False
    cut = raw[:max_bytes].decode("utf-8", errors="ignore")
    return cut + TRUNCATION_SUFFIX, True


def load_attachment(
    path_text: str,
    *,
    cwd: Path,
    remaining_budget: int,
) -> AttachItem:
    display = Path(path_text).name or path_text
    if remaining_budget <= 0:
        return AttachItem(ok=False, display_name=display, reason="合计体积已满，未载入")

    path = Path(path_text)
    if not path.is_absolute():
        path = (cwd / path).resolve()
    else:
        path = path.resolve()

    display = path.name
    if path.suffix.lower() not in _ALLOWED_SUFFIX:
        return AttachItem(
            ok=False,
            display_name=display,
            path=path,
            reason="仅支持 .md / .txt",
        )
    if not path.exists():
        return AttachItem(ok=False, display_name=display, path=path, reason="文件不存在")
    if not path.is_file():
        return AttachItem(ok=False, display_name=display, path=path, reason="不是普通文件")

    try:
        data = path.read_bytes()
    except OSError as exc:
        return AttachItem(
            ok=False, display_name=display, path=path, reason=f"无法读取：{exc}"
        )

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return AttachItem(
            ok=False,
            display_name=display,
            path=path,
            reason="无法按 UTF-8 解码，请另存为 UTF-8",
        )

    limit = min(MAX_FILE_BYTES, remaining_budget)
    content, truncated = _truncate_utf8(text, limit)
    return AttachItem(
        ok=True,
        display_name=display,
        path=path,
        content=content,
        truncated=truncated,
        size_bytes=len(data),
    )


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
