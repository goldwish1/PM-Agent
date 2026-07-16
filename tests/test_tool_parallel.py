"""工具并行：全 pure 才并行；含 impure / 未知工具走串行；消息顺序保持。"""

from __future__ import annotations

import time
from unittest.mock import patch

from pydantic import BaseModel, Field

from pm_agent.agent.llm import FakeLlmClient
from pm_agent.agent.loop import (
    _can_run_tools_in_parallel,
    _execute_tools_serial,
    handle_user_turn,
    run_agent_loop,
)
from pm_agent.agent.session import SessionState
from pm_agent.tools.demo import build_demo_registry, register_demo_tools
from pm_agent.tools.draft import register_draft_project_charter
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class SleepArgs(BaseModel):
    ms: int = Field(default=80, ge=1, le=500, description="睡眠毫秒")


def _register_sleep(registry: ToolRegistry) -> None:
    def _execute(args: SleepArgs) -> str:
        time.sleep(args.ms / 1000.0)
        return f"slept:{args.ms}"

    registry.register(
        ToolSpec(
            name="sleep",
            description="睡眠指定毫秒，用于验证并行。",
            parameters_model=SleepArgs,
            execute=_execute,
            category="demo",
            pure=True,
        )
    )


def test_registry_all_pure() -> None:
    registry = build_demo_registry()
    assert registry.all_pure(["echo", "add"]) is True
    assert registry.all_pure(["echo", "no_such"]) is False

    state = SessionState()
    register_draft_project_charter(registry, state)
    assert registry.all_pure(["echo", "draft_project_charter"]) is False


def test_can_run_parallel_requires_multiple_pure() -> None:
    registry = build_demo_registry()
    assert (
        _can_run_tools_in_parallel(
            registry,
            [{"id": "1", "name": "echo", "arguments": {"text": "a"}}],
        )
        is False
    )
    assert (
        _can_run_tools_in_parallel(
            registry,
            [
                {"id": "1", "name": "echo", "arguments": {"text": "a"}},
                {"id": "2", "name": "add", "arguments": {"a": 1, "b": 2}},
            ],
        )
        is True
    )


def test_parallel_pure_batch_preserves_message_order() -> None:
    """同轮两个 pure 工具：tool 消息顺序与 tool_calls 一致。"""
    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {"id": "c_add", "name": "add", "arguments": {"a": 1, "b": 2}},
                    {
                        "id": "c_echo",
                        "name": "echo",
                        "arguments": {"text": "hello"},
                    },
                ]
            },
            {"content": "两个工具都完成了。"},
        ]
    )
    registry = build_demo_registry()
    state = SessionState()
    reply = handle_user_turn(
        "并行 echo 与 add",
        state,
        llm,
        registry,
        max_iterations=5,
    )
    assert "完成" in reply
    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    assert tool_msgs[0]["tool_call_id"] == "c_add"
    assert "sum: 3" in tool_msgs[0]["content"]
    assert tool_msgs[1]["tool_call_id"] == "c_echo"
    assert "echo: hello" in tool_msgs[1]["content"]


def test_dispatch_uses_parallel_for_all_pure_batch() -> None:
    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {"id": "c1", "name": "echo", "arguments": {"text": "a"}},
                    {"id": "c2", "name": "add", "arguments": {"a": 1, "b": 1}},
                ]
            },
            {"content": "ok"},
        ]
    )
    registry = build_demo_registry()
    state = SessionState()
    state.append({"role": "user", "content": "go"})

    with patch(
        "pm_agent.agent.loop._execute_tools_parallel",
        side_effect=_execute_tools_serial,
    ) as parallel:
        run_agent_loop(state, llm, registry, max_iterations=5)
        assert parallel.call_count == 1


def test_dispatch_uses_serial_when_batch_has_impure() -> None:
    state = SessionState()
    registry = ToolRegistry()
    register_demo_tools(registry)
    register_draft_project_charter(registry, state)

    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {"id": "c1", "name": "echo", "arguments": {"text": "a"}},
                    {
                        "id": "c2",
                        "name": "draft_project_charter",
                        "arguments": {"project_name": "并行测试"},
                    },
                ]
            },
            {"content": "串行完成。"},
        ]
    )

    with (
        patch("pm_agent.agent.loop._execute_tools_parallel") as parallel,
        patch(
            "pm_agent.agent.loop._execute_tools_serial",
            wraps=_execute_tools_serial,
        ) as serial,
    ):
        reply = handle_user_turn(
            "含起草的一批",
            state,
            llm,
            registry,
            max_iterations=5,
        )
        assert parallel.call_count == 0
        assert serial.call_count == 1

    assert "完成" in reply or "串行" in reply
    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    assert tool_msgs[0]["name"] == "echo"
    assert tool_msgs[1]["name"] == "draft_project_charter"
    assert "ok" in tool_msgs[1]["content"]


def test_dispatch_uses_serial_for_unknown_tool_in_batch() -> None:
    registry = build_demo_registry()
    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {"id": "c1", "name": "echo", "arguments": {"text": "a"}},
                    {"id": "c2", "name": "no_such_tool", "arguments": {}},
                ]
            },
            {"content": "已纠正。"},
        ]
    )
    state = SessionState()
    with patch("pm_agent.agent.loop._execute_tools_parallel") as parallel:
        handle_user_turn("未知混入", state, llm, registry, max_iterations=5)
        assert parallel.call_count == 0

    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    assert "未知工具" in tool_msgs[1]["content"]


def test_parallel_wall_time_faster_than_serial_sum() -> None:
    """两个慢 pure 工具并行墙钟应明显小于串行之和。"""
    registry = ToolRegistry()
    _register_sleep(registry)

    llm = FakeLlmClient(
        [
            {
                "tool_calls": [
                    {"id": "s1", "name": "sleep", "arguments": {"ms": 80}},
                    {"id": "s2", "name": "sleep", "arguments": {"ms": 80}},
                ]
            },
            {"content": "睡完了。"},
        ]
    )
    state = SessionState()
    state.append({"role": "user", "content": "sleep parallel"})

    started = time.perf_counter()
    run_agent_loop(state, llm, registry, max_iterations=5)
    elapsed = time.perf_counter() - started

    # 串行约 160ms+；并行应接近 80ms+ 开销，给宽松上限 140ms
    assert elapsed < 0.14
    tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["s1", "s2"]
