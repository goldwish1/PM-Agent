"""LLM 门面：轻量再导出 + build_llm_client（Real 路径延迟加载 openai）。"""

from __future__ import annotations

from typing import Any

from pm_agent.agent.fake_llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.llm_types import LlmApiError, LlmClient
from pm_agent.config import Settings

__all__ = [
    "FakeLlmClient",
    "LlmApiError",
    "LlmClient",
    "build_llm_client",
    "demo_script_for_user_text",
]


def build_llm_client(
    settings: Settings,
    *,
    fake_script: list[dict[str, Any]] | None = None,
) -> LlmClient:
    """按 Settings 构造 Fake 或 Real 客户端。"""
    if settings.use_fake_llm:
        return FakeLlmClient(fake_script)
    # 延迟加载：避免 Fake / CLI 冷启动导入 openai SDK
    from pm_agent.agent.openai_llm import OpenAICompatibleClient

    return OpenAICompatibleClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )


def __getattr__(name: str) -> Any:
    """懒导出 Real 侧符号，import 本模块时不触发 openai。"""
    if name in {"OpenAICompatibleClient", "classify_api_error"}:
        from pm_agent.agent import openai_llm

        return getattr(openai_llm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
