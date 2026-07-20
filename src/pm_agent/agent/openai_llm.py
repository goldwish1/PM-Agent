"""OpenAI 兼容 Real LLM 客户端（顶栏加载 openai SDK）。"""

from __future__ import annotations

import json
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from pm_agent.agent.llm_types import LlmApiError


def classify_api_error(exc: BaseException) -> LlmApiError:
    """将 openai SDK 异常映射为用户可读中文提示。"""
    if isinstance(exc, LlmApiError):
        return exc
    if isinstance(exc, AuthenticationError):
        return LlmApiError(
            "auth",
            "API 密钥无效或未配置，请检查本地配置后重启。",
        )
    if isinstance(exc, RateLimitError):
        return LlmApiError(
            "rate_limit",
            "请求过于频繁，请稍后再试。",
        )
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return LlmApiError(
            "network",
            "模型服务暂时不可用（网络或服务异常）。请稍后重试；"
            "你也可以直接说：起草项目章程 / 起草风险登记册。",
        )
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status == 401:
            return LlmApiError(
                "auth",
                "API 密钥无效或未配置，请检查本地配置后重启。",
            )
        if status == 429:
            return LlmApiError(
                "rate_limit",
                "请求过于频繁，请稍后再试。",
            )
        return LlmApiError(
            "api",
            "模型服务暂时不可用（网络或服务异常）。请稍后重试；"
            "你也可以直接说：起草项目章程 / 起草风险登记册。",
        )
    return LlmApiError(
        "unknown",
        "模型服务暂时不可用（网络或服务异常）。请稍后重试；"
        "你也可以直接说：起草项目章程 / 起草风险登记册。",
    )


def _parse_tool_arguments(raw: str | None) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"_raw": parsed}


def _extract_usage(response: Any) -> dict[str, int] | None:
    """从 OpenAI 兼容 response.usage 提取 token 计数。"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    total = getattr(usage, "total_tokens", None)
    if prompt is None and completion is None and total is None:
        return None
    out: dict[str, int] = {}
    if prompt is not None:
        out["prompt_tokens"] = int(prompt)
    if completion is not None:
        out["completion_tokens"] = int(completion)
    if total is not None:
        out["total_tokens"] = int(total)
    elif "prompt_tokens" in out and "completion_tokens" in out:
        out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    for key in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        val = getattr(usage, key, None)
        if val is not None:
            out[key] = int(val)
    return out or None


def _normalize_messages_for_api(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """去掉仅本地使用的字段，保持 OpenAI Chat Completions 形状。"""
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        item: dict[str, Any] = {"role": role}
        if role == "tool":
            item["tool_call_id"] = msg.get("tool_call_id")
            item["content"] = msg.get("content") or ""
            # name 对部分兼容端可选；DeepSeek 通常可接受省略
            if msg.get("name"):
                item["name"] = msg["name"]
        elif role == "assistant":
            item["content"] = msg.get("content")
            if msg.get("tool_calls"):
                item["tool_calls"] = msg["tool_calls"]
        else:
            item["content"] = msg.get("content")
        cleaned.append(item)
    return cleaned


class OpenAICompatibleClient:
    """DeepSeek / OpenAI 兼容 Chat Completions + tools。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        client: OpenAI | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _normalize_messages_for_api(messages),
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise classify_api_error(exc) from exc

        usage = _extract_usage(response)

        if not response.choices:
            return {
                "content": "（模型未返回任何 choice。）",
                "tool_calls": None,
                "usage": usage,
            }

        message = response.choices[0].message
        content = message.content
        raw_calls = getattr(message, "tool_calls", None) or []
        if not raw_calls:
            return {"content": content, "tool_calls": None, "usage": usage}

        tool_calls: list[dict[str, Any]] = []
        for tc in raw_calls:
            function = getattr(tc, "function", None)
            name = getattr(function, "name", None) if function else None
            arguments = getattr(function, "arguments", None) if function else None
            tool_calls.append(
                {
                    "id": str(getattr(tc, "id", "") or f"call_{len(tool_calls) + 1}"),
                    "name": str(name or ""),
                    "arguments": _parse_tool_arguments(arguments),
                }
            )
        return {"content": content, "tool_calls": tool_calls, "usage": usage}

