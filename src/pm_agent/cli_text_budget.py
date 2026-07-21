"""CLI 文本体积：UTF-8 截断与共享后缀。"""

from __future__ import annotations

TRUNCATION_SUFFIX = "\n\n…[内容已截断]"


def truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False
    cut = raw[:max_bytes].decode("utf-8", errors="ignore")
    return cut + TRUNCATION_SUFFIX, True
