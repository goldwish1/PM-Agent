"""过程层可见日志：格式化与 Loop 事件流。"""

from __future__ import annotations

import pytest

from pm_agent.agent.llm import FakeLlmClient
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.session import SessionState
from pm_agent.agent.trace import (
    format_iteration_header,
    format_response_line,
    format_response_preview,
    format_thinking_line,
    format_tool_call_line,
    format_tool_result_line,
)
from pm_agent.tools.demo import build_demo_registry


def test_format_response_preview_empty_and_truncate() -> None:
    assert format_response_preview(None) == "（无文本）"
    assert format_response_preview("   ") == "（无文本）"
    assert format_response_preview("短文") == "短文"
    long = "字" * 150
    preview = format_response_preview(long)
    assert preview.endswith("…")
    assert len(preview) == 101  # 100 + …


def test_format_tool_result_ok_and_err() -> None:
    ok = format_tool_result_line("echo: hello", 12.4)
    assert ok.startswith("ok，")
    assert "耗时 12ms。" in ok

    err = format_tool_result_line("错误：未知工具 no_such", 1.1)
    assert err.startswith("err，")
    assert "耗时 1ms。" in err

    long = "x" * 200
    truncated = format_tool_result_line(long, 0)
    assert "…" in truncated
    assert truncated.startswith("ok，")


def test_format_response_line_includes_elapsed() -> None:
    line = format_response_line("hi", 12.4)
    assert line.startswith("  response: hi，")
    assert "耗时 12ms。" in line

    empty = format_response_line(None, 0.4)
    assert "（无文本）" in empty
    assert "耗时 0ms。" in empty


def test_process_layer_lines_have_no_bullet() -> None:
    assert "●" not in format_iteration_header(1)
    assert "●" not in format_thinking_line()
    assert "●" not in format_response_line("hi", 1)
    assert "●" not in format_tool_call_line("echo", {"text": "a"})
    assert format_thinking_line().startswith("  ")
    assert format_iteration_header(2) == "── 第2轮迭代 ──"


def test_loop_emits_trace_events_and_result_layer_distinct(
    capsys: pytest.CaptureFixture[str],
) -> None:
    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "echo",
                        "arguments": {"text": "hello"},
                    }
                ]
            },
            {"content": "演示完成：已调用 echo。"},
        ]
    )
    registry = build_demo_registry()
    state = SessionState()
    reply = handle_user_turn(
        "请用 echo 说 hello",
        state,
        llm,
        registry,
        max_iterations=10,
    )

    process_out = capsys.readouterr().out
    assert "── 第1轮迭代 ──" in process_out
    assert "thinking: LLM调用开始。" in process_out
    assert "tool_call: echo(" in process_out
    assert "tool_result:" in process_out
    assert "耗时" in process_out
    assert "── 第2轮迭代 ──" in process_out
    assert "response: 演示完成" in process_out
    response_lines = [ln for ln in process_out.splitlines() if "response:" in ln]
    assert response_lines
    assert all("耗时" in ln for ln in response_lines)
    process_lines = [ln for ln in process_out.splitlines() if ln.strip()]
    assert all(not ln.startswith("●") for ln in process_lines)
    for ln in process_out.splitlines():
        if "thinking:" in ln or "tool_call:" in ln or "tool_result:" in ln:
            assert ln.startswith("  ")

    # 模拟 cli 结果层：空行 + ●
    print(flush=True)
    print(f"● {reply}", flush=True)
    combined = process_out + capsys.readouterr().out
    assert "\n● " in combined
    bullet_lines = [ln for ln in combined.splitlines() if ln.startswith("● ")]
    assert len(bullet_lines) == 1
    assert "演示" in reply or "echo" in reply.lower()
