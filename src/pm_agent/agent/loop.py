"""Agent Loop：迭代上限、调模型、派发工具、过程层可见日志。"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from pm_agent.agent.debug_log import TurnDebugDump, print_llm_round
from pm_agent.agent.llm import LlmApiError, LlmClient
from pm_agent.agent.prompts import MAX_CLARIFY_ROUNDS, get_system_prompt
from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.agent.spinner import llm_spinner
from pm_agent.agent.trace import (
    trace_iteration,
    trace_response,
    trace_thinking,
    trace_tool_call,
    trace_tool_result,
)
from pm_agent.tools.registry import ToolRegistry


def _normalize_tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _can_run_tools_in_parallel(
    registry: ToolRegistry,
    tool_calls: list[dict[str, Any]],
) -> bool:
    """保守策略：数量 >1 且全部为已知 pure 工具才并行。"""
    if len(tool_calls) <= 1:
        return False
    names = [str(tc["name"]) for tc in tool_calls]
    return registry.all_pure(names)


def _execute_tools_serial(
    state: SessionState,
    registry: ToolRegistry,
    tool_calls: list[dict[str, Any]],
) -> None:
    for tc in tool_calls:
        name = str(tc["name"])
        args = _normalize_tool_args(tc.get("arguments"))
        trace_tool_call(name, args)
        started = time.perf_counter()
        result = registry.execute(name, args)
        elapsed_ms = (time.perf_counter() - started) * 1000
        trace_tool_result(result, elapsed_ms)
        state.append(
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": result,
            }
        )


def _timed_execute(
    registry: ToolRegistry,
    name: str,
    args: dict[str, Any],
) -> tuple[str, float]:
    started = time.perf_counter()
    result = registry.execute(name, args)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return result, elapsed_ms


def _execute_tools_parallel(
    state: SessionState,
    registry: ToolRegistry,
    tool_calls: list[dict[str, Any]],
) -> None:
    """全 pure 并行执行；trace 与 messages 仍按原 tool_calls 顺序输出。"""
    prepared: list[tuple[str, str, dict[str, Any]]] = []
    for tc in tool_calls:
        name = str(tc["name"])
        args = _normalize_tool_args(tc.get("arguments"))
        prepared.append((str(tc["id"]), name, args))
        trace_tool_call(name, args)

    ordered: list[tuple[str, float] | None] = [None] * len(prepared)
    max_workers = min(len(prepared), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(_timed_execute, registry, name, args): idx
            for idx, (_call_id, name, args) in enumerate(prepared)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            ordered[idx] = future.result()

    for (call_id, name, _args), timed in zip(prepared, ordered, strict=True):
        result, elapsed_ms = timed if timed is not None else ("", 0.0)
        trace_tool_result(result, elapsed_ms)
        state.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": result,
            }
        )


def _dispatch_tool_calls(
    state: SessionState,
    registry: ToolRegistry,
    tool_calls: list[dict[str, Any]],
) -> None:
    if _can_run_tools_in_parallel(registry, tool_calls):
        _execute_tools_parallel(state, registry, tool_calls)
    else:
        _execute_tools_serial(state, registry, tool_calls)


def _ensure_system_prompt(state: SessionState) -> None:
    prompt = get_system_prompt(clarify_count=state.clarify_count)
    if not state.messages or state.messages[0].get("role") != "system":
        state.messages.insert(0, {"role": "system", "content": prompt})
    else:
        state.messages[0]["content"] = prompt


def _inject_clarify_force_reminder(state: SessionState) -> None:
    if state.clarify_count < MAX_CLARIFY_ROUNDS:
        return
    state.append(
        {
            "role": "system",
            "content": (
                f"澄清已达上限（{MAX_CLARIFY_ROUNDS} 轮）。"
                "请立即调用 recommend_tools，禁止继续追问。"
            ),
        }
    )


def _update_clarify_after_turn(
    state: SessionState,
    *,
    tools_before: int,
    reply: str,
) -> None:
    all_tool_msgs = [m for m in state.messages if m.get("role") == "tool"]
    new_tool_msgs = all_tool_msgs[tools_before:]
    if new_tool_msgs:
        if any(m.get("name") == "recommend_tools" for m in new_tool_msgs):
            state.mode = SessionMode.RECOMMENDING
        return

    # 未调工具且像在追问 → 计为一次澄清
    if ("？" in reply or "?" in reply) and state.clarify_count < MAX_CLARIFY_ROUNDS:
        state.clarify_count += 1
        state.mode = SessionMode.CLARIFYING


def _normalize_response_fields(
    response: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]] | None, dict[str, int] | None]:
    content = response.get("content")
    if not (isinstance(content, str) or content is None):
        content = str(content)
    tool_calls = response.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        usage = None
    return content, tool_calls, usage


def _maybe_log_llm_round(
    *,
    debug_llm: bool,
    turn_dump: TurnDebugDump | None,
    user_turn: int,
    iteration: int,
    messages: list[dict[str, Any]],
    tools_count: int,
    response: dict[str, Any],
    llm_is_fake: bool,
) -> None:
    content, tool_calls, usage = _normalize_response_fields(response)

    if debug_llm:
        print_llm_round(
            user_turn=user_turn,
            iteration=iteration,
            messages=messages,
            tools_count=tools_count,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            llm_is_fake=llm_is_fake,
        )

    if turn_dump is not None:
        turn_dump.record_iteration(
            iteration=iteration,
            messages=messages,
            tools_count=tools_count,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
        )


def run_agent_loop(
    state: SessionState,
    llm: LlmClient,
    registry: ToolRegistry,
    max_iterations: int = 10,
    *,
    debug_llm: bool = False,
    debug_dump_llm: bool = False,
    output_dir: Path | None = None,
    user_turn: int = 1,
    user_text: str = "",
    llm_is_fake: bool = False,
) -> str:
    """
    在已含本轮 user message 的 session 上跑工具循环。

    返回最终助手文本（也可能是触顶提示）。
    """
    if max_iterations < 1:
        max_iterations = 1

    turn_dump: TurnDebugDump | None = None
    if debug_dump_llm and output_dir is not None:
        turn_dump = TurnDebugDump(
            output_dir,
            turn=user_turn,
            user_text=user_text,
        )

    tools_schema = registry.openai_tools_schema()
    tools_count = len(tools_schema)
    iteration = 0

    while True:
        round_n = iteration + 1
        trace_iteration(round_n)
        tty = sys.stdout.isatty()
        trace_thinking(end="" if tty else "\n")
        started = time.perf_counter()
        try:
            with llm_spinner(enabled=tty):
                response = llm.complete(state.messages, tools=tools_schema)
        except LlmApiError as exc:
            final_text = exc.user_message
            state.append({"role": "assistant", "content": final_text})
            if turn_dump is not None:
                turn_dump.finalize(final_text, state.messages)
            return final_text
        elapsed_ms = (time.perf_counter() - started) * 1000

        _maybe_log_llm_round(
            debug_llm=debug_llm,
            turn_dump=turn_dump,
            user_turn=user_turn,
            iteration=round_n,
            messages=state.messages,
            tools_count=tools_count,
            response=response,
            llm_is_fake=llm_is_fake,
        )

        content = response.get("content")
        tool_calls = response.get("tool_calls") or []
        trace_response(
            content if isinstance(content, str) or content is None else str(content),
            elapsed_ms,
        )

        if not tool_calls:
            final_text = (content or "").strip() or "（模型未返回文本。）"
            state.append({"role": "assistant", "content": final_text})
            if turn_dump is not None:
                turn_dump.finalize(final_text, state.messages)
            return final_text

        if iteration >= max_iterations:
            final_text = (
                "本轮已达上限，请换一种说法或直接说要起草哪份文档。"
            )
            state.append({"role": "assistant", "content": final_text})
            if turn_dump is not None:
                turn_dump.finalize(final_text, state.messages)
            return final_text

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(
                            tc.get("arguments") or {},
                            ensure_ascii=False,
                        ),
                    },
                }
                for tc in tool_calls
            ],
        }
        state.append(assistant_msg)
        _dispatch_tool_calls(state, registry, tool_calls)
        iteration += 1


def handle_user_turn(
    text: str,
    state: SessionState,
    llm: LlmClient,
    registry: ToolRegistry,
    max_iterations: int = 10,
    *,
    debug_llm: bool = False,
    debug_dump_llm: bool = False,
    output_dir: Path | None = None,
    user_turn: int = 1,
    llm_is_fake: bool = False,
) -> str:
    """追加用户消息并跑 Agent Loop；维护澄清计数与系统提示。"""
    _ensure_system_prompt(state)
    state.append({"role": "user", "content": text})
    _inject_clarify_force_reminder(state)

    tools_before = sum(1 for m in state.messages if m.get("role") == "tool")
    reply = run_agent_loop(
        state,
        llm,
        registry,
        max_iterations=max_iterations,
        debug_llm=debug_llm,
        debug_dump_llm=debug_dump_llm,
        output_dir=output_dir,
        user_turn=user_turn,
        user_text=text,
        llm_is_fake=llm_is_fake,
    )
    _update_clarify_after_turn(state, tools_before=tools_before, reply=reply)
    return reply
