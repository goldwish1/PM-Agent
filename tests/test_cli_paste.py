"""cli_paste：阈值、占位符、组装、回退检测。"""

from __future__ import annotations

from pm_agent.cli_paste import (
    PASTE_MIN_BYTES,
    PASTE_MIN_LINES,
    PasteBlock,
    count_lines,
    detect_inline_paste,
    extract_paste_placeholders,
    format_paste_line,
    format_paste_placeholder,
    resolve_pastes,
    should_fold_paste,
)


def test_should_fold_paste_by_lines() -> None:
    text = "\n".join(f"line{i}" for i in range(PASTE_MIN_LINES))
    assert should_fold_paste(text) is True
    short = "\n".join(f"line{i}" for i in range(PASTE_MIN_LINES - 1))
    assert should_fold_paste(short) is False


def test_should_fold_paste_by_bytes() -> None:
    text = "x" * PASTE_MIN_BYTES
    assert should_fold_paste(text) is True
    assert should_fold_paste("x" * (PASTE_MIN_BYTES - 1)) is False


def test_format_paste_placeholder() -> None:
    assert format_paste_placeholder(62) == "[paste] +62 lines"


def test_extract_paste_placeholders_strips_and_collects() -> None:
    raw = "[paste] +62 lines\n\n帮我总结建票"
    user_text, counts = extract_paste_placeholders(raw)
    assert user_text == "帮我总结建票"
    assert counts == [62]


def test_extract_multiple_placeholders_in_order() -> None:
    raw = "先看 [paste] +10 lines 再看 [paste] +20 lines 问题"
    user_text, counts = extract_paste_placeholders(raw)
    assert counts == [10, 20]
    assert "先看" in user_text
    assert "问题" in user_text


def test_resolve_pastes_with_sidecar() -> None:
    body = "\n".join(f"msg{i}" for i in range(12))
    pastes = (PasteBlock(content=body),)
    raw = f"{format_paste_placeholder(12)}\n\n帮我总结"
    result = resolve_pastes(raw, pastes=pastes, remaining_budget=128 * 1024)
    assert result.user_text == "帮我总结"
    assert len(result.items) == 1
    assert result.items[0].ok is True
    assert "[粘贴材料 1]" in result.assembled
    assert body in result.assembled
    assert result.should_enter_loop is True


def test_format_paste_line_ok() -> None:
    from pm_agent.cli_paste import PasteItem

    line = format_paste_line(
        PasteItem(ok=True, content="x", line_count=62, size_bytes=4300)
    )
    assert line.startswith("[paste] ok")
    assert "+62 lines" in line


def test_format_paste_line_fail() -> None:
    from pm_agent.cli_paste import PasteItem

    line = format_paste_line(
        PasteItem(ok=False, line_count=62, reason="合计体积已满，未载入")
    )
    assert line.startswith("[paste] fail")


def test_detect_inline_paste_question_at_end() -> None:
    body = "\n".join(f"chat line {i}" for i in range(15))
    raw = f"{body}\n帮我总结建票"
    user_text, blocks = detect_inline_paste(raw)
    assert user_text == "帮我总结建票"
    assert len(blocks) == 1
    assert count_lines(blocks[0].content) >= PASTE_MIN_LINES


def test_detect_inline_paste_question_at_start() -> None:
    body = "\n".join(f"chat line {i}" for i in range(15))
    raw = f"帮我总结建票\n{body}"
    user_text, blocks = detect_inline_paste(raw)
    assert user_text == "帮我总结建票"
    assert len(blocks) == 1


def test_detect_inline_paste_whole_block_only() -> None:
    body = "\n".join(f"chat line {i}" for i in range(15))
    user_text, blocks = detect_inline_paste(body)
    assert user_text == ""
    assert len(blocks) == 1
    assert blocks[0].content == body


def test_detect_inline_paste_skips_small_text() -> None:
    raw = "只有一行短问题"
    user_text, blocks = detect_inline_paste(raw)
    assert user_text == raw
    assert blocks == ()


def test_resolve_pastes_inline_fallback() -> None:
    body = "\n".join(f"chat line {i}" for i in range(15))
    raw = f"{body}\n帮我总结"
    result = resolve_pastes(raw, pastes=(), remaining_budget=128 * 1024)
    assert result.user_text == "帮我总结"
    assert result.items[0].ok is True
    assert body in result.assembled
