"""Agent Loop 边界：触顶停止、未知工具、Fake 剧本成功路径。"""

from __future__ import annotations

from pm_agent.agent.llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.loop import handle_user_turn, run_agent_loop
from pm_agent.agent.session import SessionState
from pm_agent.tools.demo import build_demo_registry
from pm_agent.tools.registry import ToolRegistry


def test_loop_stops_at_max_iterations() -> None:
    """模型持续 tool_calls 时，达到上限应停止且不再无限执行。"""
    always_echo = {
        "tool_calls": [
            {"id": "c1", "name": "echo", "arguments": {"text": "loop"}}
        ]
    }
    # 足够多的剧本，确保不是剧本耗尽而是触顶
    llm = FakeLlmClient([always_echo] * 20)
    registry = build_demo_registry()
    state = SessionState()
    state.append({"role": "user", "content": "keep going"})

    max_iterations = 3
    reply = run_agent_loop(state, llm, registry, max_iterations=max_iterations)

    assert "上限" in reply

    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == max_iterations


def test_unknown_tool_returns_correction_instruction() -> None:
    """未知工具应返回纠正指令，进程不崩溃，并记入 tool 消息。"""
    registry = ToolRegistry()  # 空表，任何名字都未知
    result = registry.execute("no_such_tool", {"x": 1})
    assert result.startswith("错误：")
    assert "未知工具" in result
    assert "no_such_tool" in result

    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {
                        "id": "bad_1",
                        "name": "no_such_tool",
                        "arguments": {"x": 1},
                    }
                ]
            },
            {"content": "已收到纠正，结束。"},
        ]
    )
    state = SessionState()
    reply = handle_user_turn(
        "call bad tool",
        state,
        llm,
        registry,
        max_iterations=5,
    )
    assert "纠正" in reply or "结束" in reply
    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "未知工具" in tool_msgs[0]["content"]


def test_fake_script_happy_path_echo_and_add() -> None:
    """演示关键词仍走 echo → add 剧本。"""
    llm = FakeLlmClient(demo_script_for_user_text("请用 echo 说 hello"))
    registry = build_demo_registry()
    state = SessionState()
    reply = handle_user_turn(
        "请用 echo 说 hello",
        state,
        llm,
        registry,
        max_iterations=10,
    )

    assert "演示" in reply or "echo" in reply.lower()
    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    assert "echo:" in tool_msgs[0]["content"]
    assert "sum: 3" in tool_msgs[1]["content"]
