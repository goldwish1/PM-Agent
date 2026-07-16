"""cli_attach：@ 解析、读文件、组装。"""

from __future__ import annotations

from pathlib import Path

from pm_agent.cli_attach import (
    ATTACH_EMPTY_HINT,
    MAX_FILE_BYTES,
    extract_mentions,
    format_attach_line,
    load_attachment,
    looks_like_attach_path,
    resolve_attachments,
    strip_mentions,
)


def test_attach_empty_hint_non_empty() -> None:
    assert "@" in ATTACH_EMPTY_HINT
    assert ".md" in ATTACH_EMPTY_HINT


def test_looks_like_path_accepts_relative_and_ext() -> None:
    assert looks_like_attach_path("./kickoff.md")
    assert looks_like_attach_path("../notes.txt")
    assert looks_like_attach_path("docs/a.md")
    assert looks_like_attach_path("kickoff.md")
    assert looks_like_attach_path("/tmp/x.txt")


def test_looks_like_path_rejects_email_local_part() -> None:
    assert not looks_like_attach_path("user")
    # extract 侧：整段 @user@x.com 不应产出附件 mention


def test_extract_single_and_quoted() -> None:
    text = "下周立项 @./kickoff.md 请推荐"
    ms = extract_mentions(text)
    assert len(ms) == 1
    assert ms[0].path_text == "./kickoff.md"
    assert strip_mentions(text, ms) == "下周立项 请推荐"

    q = '看这个 @"我的 纪要.md" 谢谢'
    ms2 = extract_mentions(q)
    assert len(ms2) == 1
    assert ms2[0].path_text == "我的 纪要.md"
    assert strip_mentions(q, ms2) == "看这个 谢谢"


def test_extract_multiple_in_order() -> None:
    text = "参考 @./a.md 和 @./b.txt"
    ms = extract_mentions(text)
    assert [m.path_text for m in ms] == ["./a.md", "./b.txt"]


def test_email_not_extracted_as_attach() -> None:
    text = "联系 @user@example.com 再立项"
    assert extract_mentions(text) == []
    assert strip_mentions(text, []) == text


def test_load_ok_md(tmp_path: Path) -> None:
    f = tmp_path / "kickoff.md"
    f.write_text("立项下周\n", encoding="utf-8")
    item = load_attachment("kickoff.md", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    assert item.ok is True
    assert item.content == "立项下周\n"
    assert item.truncated is False
    assert item.display_name == "kickoff.md"


def test_load_rejects_extension(tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"\x00\x01")
    item = load_attachment("a.bin", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    assert item.ok is False
    assert "md" in item.reason.lower() or "txt" in item.reason.lower() or "仅支持" in item.reason


def test_load_rejects_directory(tmp_path: Path) -> None:
    d = tmp_path / "docs"
    d.mkdir()
    # docs 无扩展名且是目录；若 looks 未过则不会调用；这里测 load 对目录
    item = load_attachment("./docs", cwd=tmp_path, remaining_budget=MAX_FILE_BYTES)
    assert item.ok is False


def test_load_truncates_to_budget(tmp_path: Path) -> None:
    f = tmp_path / "big.md"
    f.write_text("abcd" * 100, encoding="utf-8")
    item = load_attachment("big.md", cwd=tmp_path, remaining_budget=10)
    assert item.ok is True
    assert item.truncated is True
    assert "内容已截断" in item.content
    # 截断后原文部分的 utf-8 长度 <= 10
    body = item.content.split("\n\n…[内容已截断]")[0]
    assert len(body.encode("utf-8")) <= 10


def test_load_absolute_path(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi", encoding="utf-8")
    item = load_attachment(str(f.resolve()), cwd=Path("/"), remaining_budget=MAX_FILE_BYTES)
    assert item.ok is True
    assert item.content == "hi"


def test_resolve_no_mention_identity(tmp_path: Path) -> None:
    r = resolve_attachments("下周立项不知道从哪下手", cwd=tmp_path)
    assert r.user_text == "下周立项不知道从哪下手"
    assert r.assembled == r.user_text
    assert r.items == ()
    assert r.should_enter_loop is True


def test_resolve_injects_block(tmp_path: Path) -> None:
    f = tmp_path / "kickoff.md"
    f.write_text("目的：上线支付", encoding="utf-8")
    r = resolve_attachments("下周立项 @kickoff.md 请推荐", cwd=tmp_path)
    assert r.user_text == "下周立项 请推荐"
    assert r.should_enter_loop is True
    assert len(r.items) == 1 and r.items[0].ok
    assert "[附件 1]" in r.assembled
    assert "path=" in r.assembled
    assert "目的：上线支付" in r.assembled
    assert "truncated=false" in r.assembled


def test_resolve_all_fail_empty_nl_no_loop(tmp_path: Path) -> None:
    r = resolve_attachments("@missing.md", cwd=tmp_path)
    assert r.user_text == ""
    assert r.should_enter_loop is False
    assert r.items and r.items[0].ok is False


def test_resolve_total_budget_skips_later(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_bytes(b"x" * 100)
    b.write_text("second", encoding="utf-8")
    r = resolve_attachments(
        "@a.md @b.md",
        cwd=tmp_path,
        total_budget=50,
    )
    assert r.items[0].ok is True
    assert r.items[1].ok is False
    assert "合计" in r.items[1].reason or "未载入" in r.items[1].reason


def test_format_attach_line_ok_and_fail(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("hi", encoding="utf-8")
    r = resolve_attachments("@a.md", cwd=tmp_path)
    line = format_attach_line(r.items[0])
    assert line.startswith("[attach] ok")
    assert "a.md" in line

    r2 = resolve_attachments("@nope.md", cwd=tmp_path)
    line2 = format_attach_line(r2.items[0])
    assert line2.startswith("[attach] fail")
