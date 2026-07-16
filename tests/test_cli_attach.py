"""cli_attach：@ 解析、读文件、组装。"""

from __future__ import annotations

from pm_agent.cli_attach import (
    extract_mentions,
    looks_like_attach_path,
    strip_mentions,
)


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
