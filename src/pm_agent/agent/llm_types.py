"""LLM 客户端协议与错误类型（无 openai 依赖）。"""

from __future__ import annotations

from typing import Any, Protocol


class LlmClient(Protocol):
    """Fake / Real 统一接口。"""

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """返回统一形状：{"content", "tool_calls", "usage"}。"""
        ...


class LlmApiError(Exception):
    """已分类的 LLM API 错误，供 CLI / Loop 展示中文提示。"""

    def __init__(self, kind: str, user_message: str) -> None:
        super().__init__(user_message)
        self.kind = kind
        self.user_message = user_message
