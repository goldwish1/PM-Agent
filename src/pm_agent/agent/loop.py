"""Agent Loop：迭代上限、调模型、派发工具、可见 [tool] 日志。"""

from __future__ import annotations

import json
from typing import Any

from pm_agent.agent.llm import LlmApiError, LlmClient
from pm_agent.agent.prompts import MAX_CLARIFY_ROUNDS, get_system_prompt
from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.tools.registry import ToolRegistry


def _format_args_summary(arguments: dict[str, Any] | Any) -> str:
    if not isinstance(arguments, dict):
        return repr(arguments)
    try:
        return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(arguments)


def _log_tool(name: str, arguments: dict[str, Any], status: str) -> None:
    summary = _format_args_summary(arguments)
    print(f"[tool] {name}({summary}) → {status}", flush=True)


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


def run_agent_loop(
    state: SessionState,
    llm: LlmClient,
    registry: ToolRegistry,
    max_iterations: int = 10,
) -> str:
    """
    在已含本轮 user message 的 session 上跑工具循环。

    返回最终助手文本（也可能是触顶提示）。
    """
    if max_iterations < 1:
        max_iterations = 1

    tools_schema = registry.openai_tools_schema()
    iteration = 0

    while True:
        try:
            response = llm.complete(state.messages, tools=tools_schema)
        except LlmApiError as exc:
            final_text = exc.user_message
            state.append({"role": "assistant", "content": final_text})
            return final_text

        content = response.get("content")
        tool_calls = response.get("tool_calls") or []

        if not tool_calls:
            final_text = (content or "").strip() or "（模型未返回文本。）"
            state.append({"role": "assistant", "content": final_text})
            return final_text

        if iteration >= max_iterations:
            final_text = (
                "本轮已达上限，请换一种说法或直接说要起草哪份文档。"
            )
            state.append({"role": "assistant", "content": final_text})
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

        for tc in tool_calls:
            name = str(tc["name"])
            args = tc.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}

            result = registry.execute(name, args)
            status = "err" if result.startswith("错误：") else "ok"
            _log_tool(name, args, status)

            state.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": result,
                }
            )

        iteration += 1


def handle_user_turn(
    text: str,
    state: SessionState,
    llm: LlmClient,
    registry: ToolRegistry,
    max_iterations: int = 10,
) -> str:
    """追加用户消息并跑 Agent Loop；维护澄清计数与系统提示。"""
    _ensure_system_prompt(state)
    state.append({"role": "user", "content": text})
    _inject_clarify_force_reminder(state)

    tools_before = sum(1 for m in state.messages if m.get("role") == "tool")
    reply = run_agent_loop(state, llm, registry, max_iterations=max_iterations)
    _update_clarify_after_turn(state, tools_before=tools_before, reply=reply)
    return reply
