"""LLM 等待 spinner：非 TTY 空操作；TTY 同行 |/-\\。"""

from __future__ import annotations

import io
import time
from unittest.mock import patch

from pm_agent.agent.spinner import llm_spinner


def test_llm_spinner_noop_when_not_tty() -> None:
    buf = io.StringIO()
    with patch.object(buf, "isatty", return_value=False):
        with llm_spinner(stream=buf):
            time.sleep(0.05)
    assert buf.getvalue() == ""


def test_llm_spinner_writes_frames_when_tty() -> None:
    buf = io.StringIO()
    with patch.object(buf, "isatty", return_value=True):
        with llm_spinner(enabled=True, stream=buf):
            time.sleep(0.2)
    out = buf.getvalue()
    assert any(ch in out for ch in "|/-\\")
    assert out.endswith("\n")
    # 结束时应擦除最后一帧（\b \b），行末不含残留 spinner 字符
    before_nl = out[: -1]
    assert not before_nl.endswith(("|", "/", "-", "\\"))


def test_llm_spinner_enabled_false_skips_even_if_tty() -> None:
    buf = io.StringIO()
    with patch.object(buf, "isatty", return_value=True):
        with llm_spinner(enabled=False, stream=buf):
            time.sleep(0.05)
    assert buf.getvalue() == ""
