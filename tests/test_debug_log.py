"""LLM 调试观测：L1 格式、L2 落盘、usage 解析、配置默认值。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pm_agent.agent.debug_log import (
    TurnDebugDump,
    format_llm_round,
    print_llm_round,
    sum_usage,
)
from pm_agent.agent.llm import OpenAICompatibleClient
from pm_agent.config import load_settings


def test_format_llm_round_includes_turn_iter_usage() -> None:
    text = format_llm_round(
        user_turn=2,
        iteration=1,
        messages=[{"role": "user", "content": "hi"}],
        tools_count=8,
        content=None,
        tool_calls=[{"name": "search_tools", "arguments": {}}],
        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
    )
    assert "turn=2" in text
    assert "iter=1" in text
    assert "msgs=1" in text
    assert "tools=8" in text
    assert "search_tools" in text
    assert "prompt=10" in text
    assert "completion=3" in text
    assert "total=13" in text


def test_format_llm_round_fake_usage(capsys: pytest.CaptureFixture[str]) -> None:
    print_llm_round(
        user_turn=1,
        iteration=1,
        messages=[],
        tools_count=0,
        content="hello",
        tool_calls=None,
        usage=None,
        llm_is_fake=True,
    )
    out = capsys.readouterr().out
    assert "usage: fake" in out
    assert "content=hello" in out


def test_turn_debug_dump_aggregates_iterations(tmp_path: Path) -> None:
    dump = TurnDebugDump(tmp_path, turn=2, user_text="遇到一个风险")
    dump.record_iteration(
        iteration=1,
        messages=[{"role": "user", "content": "遇到一个风险"}],
        tools_count=8,
        content=None,
        tool_calls=[{"id": "c1", "name": "search_tools", "arguments": {}}],
        usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
    )
    path = dump.record_iteration(
        iteration=2,
        messages=[
            {"role": "user", "content": "遇到一个风险"},
            {"role": "tool", "content": "{}"},
        ],
        tools_count=8,
        content="推荐风险登记册",
        tool_calls=None,
        usage={"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
    )
    finalize_path = dump.finalize(
        "推荐风险登记册",
        [
            {"role": "user", "content": "遇到一个风险"},
            {"role": "assistant", "content": "推荐风险登记册"},
        ],
    )

    assert path == finalize_path
    assert path.name == "turn-002.json"
    assert not (tmp_path / "debug" / "turn-002-iter-01.json").exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["turn"] == 2
    assert data["user"] == "遇到一个风险"
    assert len(data["iterations"]) == 2
    assert "messages" not in data["iterations"][0]
    assert data["iterations"][0]["msgs"] == 1
    assert data["iterations"][0]["response"]["tool_calls"][0]["name"] == "search_tools"
    assert data["final_assistant"] == "推荐风险登记册"
    assert data["messages"][-1]["content"] == "推荐风险登记册"
    assert data["usage_total"] == {
        "prompt_tokens": 30,
        "completion_tokens": 8,
        "total_tokens": 38,
    }


def test_sum_usage_none_when_all_fake() -> None:
    assert sum_usage([{"usage": None}, {"usage": None}]) is None


def test_openai_compatible_client_extracts_usage() -> None:
    mock_client = MagicMock()
    message = SimpleNamespace(content="ok", tool_calls=None)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=2, total_tokens=13)
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[choice],
        usage=usage,
    )

    llm = OpenAICompatibleClient(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="test-model",
        client=mock_client,
    )
    result = llm.complete([{"role": "user", "content": "hi"}])
    assert result["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 2,
        "total_tokens": 13,
    }
    assert result["content"] == "ok"
    assert result["tool_calls"] is None


def test_debug_dump_defaults_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pm_agent.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.delenv("PMBOX_DEBUG", raising=False)
    monkeypatch.delenv("PMBOX_DEBUG_DUMP", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-your-key-here")
    settings = load_settings()
    assert settings.debug_llm is False
    assert settings.debug_dump_llm is True


def test_debug_dump_can_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pm_agent.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-your-key-here")
    monkeypatch.setenv("PMBOX_DEBUG_DUMP", "0")
    monkeypatch.setenv("PMBOX_DEBUG", "1")
    settings = load_settings()
    assert settings.debug_llm is True
    assert settings.debug_dump_llm is False
