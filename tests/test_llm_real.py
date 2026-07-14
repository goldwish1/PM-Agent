"""配置解析与 Real LLM 客户端（不依赖真实 API Key）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai import APIConnectionError, AuthenticationError, RateLimitError

from pm_agent.agent.llm import (
    LlmApiError,
    OpenAICompatibleClient,
    classify_api_error,
)
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.session import SessionState
from pm_agent.config import ConfigError, load_settings, resolve_use_fake_llm
from pm_agent.tools.demo import build_demo_registry


def test_resolve_use_fake_when_env_unset_and_no_key() -> None:
    use_fake, notice = resolve_use_fake_llm(use_fake_env=None, has_api_key=False)
    assert use_fake is True
    assert notice is not None
    assert "FakeLLM" in notice


def test_resolve_use_real_when_env_unset_and_has_key() -> None:
    use_fake, notice = resolve_use_fake_llm(use_fake_env=None, has_api_key=True)
    assert use_fake is False
    assert notice is None


def test_resolve_respects_explicit_fake_even_with_key() -> None:
    use_fake, notice = resolve_use_fake_llm(use_fake_env="true", has_api_key=True)
    assert use_fake is True
    assert notice is None


def test_load_settings_errors_when_real_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pm_agent.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("USE_FAKE_LLM", "false")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    with pytest.raises(ConfigError) as exc_info:
        load_settings()
    assert "DEEPSEEK_API_KEY" in str(exc_info.value)


def test_load_settings_auto_fake_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pm_agent.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-your-key-here")
    settings = load_settings()
    assert settings.use_fake_llm is True
    assert settings.provider_label == "FakeLLM"
    assert settings.config_notice is not None
    assert settings.deepseek_base_url == "https://api.deepseek.com/v1"
    assert settings.deepseek_model == "DeepSeek-V4-Flash"


def test_classify_auth_rate_network_errors() -> None:
    auth = classify_api_error(
        AuthenticationError(
            message="bad key",
            response=MagicMock(status_code=401),
            body=None,
        )
    )
    assert auth.kind == "auth"
    assert "API 密钥" in auth.user_message

    rate = classify_api_error(
        RateLimitError(
            message="slow down",
            response=MagicMock(status_code=429),
            body=None,
        )
    )
    assert rate.kind == "rate_limit"
    assert "频繁" in rate.user_message

    network = classify_api_error(
        APIConnectionError(request=MagicMock(), message="down")
    )
    assert network.kind == "network"
    assert "暂时不可用" in network.user_message


def test_openai_compatible_client_parses_tool_calls() -> None:
    mock_client = MagicMock()
    function = SimpleNamespace(
        name="echo",
        arguments='{"text": "hello"}',
    )
    tool_call = SimpleNamespace(id="call_1", function=function)
    message = SimpleNamespace(content=None, tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[choice]
    )

    llm = OpenAICompatibleClient(
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
        model="DeepSeek-V4-Flash",
        client=mock_client,
    )
    result = llm.complete(
        [{"role": "user", "content": "echo hello"}],
        tools=[{"type": "function", "function": {"name": "echo"}}],
    )

    assert result["tool_calls"] is not None
    assert result["tool_calls"][0]["name"] == "echo"
    assert result["tool_calls"][0]["arguments"] == {"text": "hello"}
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "DeepSeek-V4-Flash"
    assert "tools" in kwargs


def test_loop_surfaces_llm_api_error() -> None:
    class BoomClient:
        def complete(self, messages, tools=None):
            raise LlmApiError("auth", "鉴权失败：测试提示。")

    state = SessionState()
    reply = handle_user_turn(
        "hi",
        state,
        BoomClient(),
        build_demo_registry(),
        max_iterations=3,
    )
    assert "鉴权失败" in reply
