"""从环境变量加载运行时配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 仓库根目录：src/pm_agent/config.py → 上三级
REPO_ROOT = Path(__file__).resolve().parents[2]

_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "sk-your-key-here",
        "your-key-here",
        "changeme",
    }
)
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})


class ConfigError(Exception):
    """配置无效（例如显式要求 Real 却缺少 API Key）。"""


@dataclass(frozen=True)
class Settings:
    """进程级配置（MVP：无跨会话持久化）。"""

    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    openai_api_key: str
    use_fake_llm: bool
    output_dir: Path
    max_tool_iterations: int
    tools_json_path: Path
    provider_label: str
    config_notice: str | None = None


def _looks_like_real_key(value: str) -> bool:
    cleaned = value.strip()
    return cleaned not in _PLACEHOLDER_KEYS


def _parse_bool_env(raw: str | None) -> bool | None:
    """解析显式布尔环境变量；未设置返回 None。"""
    if raw is None:
        return None
    text = raw.strip().lower()
    if text == "":
        return None
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    # 无法识别时按未设置处理，避免误伤
    return None


def _parse_max_iterations() -> int:
    raw = os.getenv("MAX_TOOL_ITERATIONS") or os.getenv("MAX_ITERATIONS") or "10"
    try:
        return max(1, int(raw))
    except ValueError:
        return 10


def resolve_use_fake_llm(
    *,
    use_fake_env: str | None,
    has_api_key: bool,
) -> tuple[bool, str | None]:
    """
    决定是否使用 FakeLLM。

    - 显式 USE_FAKE_LLM=true/false → 尊重用户
    - 未设置：无 Key → Fake + 提示；有 Key → Real
    """
    explicit = _parse_bool_env(use_fake_env)
    if explicit is True:
        return True, None
    if explicit is False:
        return False, None
    if has_api_key:
        return False, None
    return (
        True,
        "未检测到有效 DEEPSEEK_API_KEY，已自动使用 FakeLLM"
        "（配置密钥后可走真实模型；也可显式 USE_FAKE_LLM=true）。",
    )


def load_settings() -> Settings:
    """加载 `.env` 并解析为 Settings。缺 Key 且显式 Real 时抛 ConfigError。"""
    load_dotenv(REPO_ROOT / ".env")

    output_raw = os.getenv("OUTPUT_DIR", "./output")
    output_dir = Path(output_raw)
    if not output_dir.is_absolute():
        output_dir = (REPO_ROOT / output_dir).resolve()

    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    has_key = _looks_like_real_key(deepseek_api_key)
    use_fake, notice = resolve_use_fake_llm(
        use_fake_env=os.getenv("USE_FAKE_LLM"),
        has_api_key=has_key,
    )

    if not use_fake and not has_key:
        raise ConfigError(
            "已要求使用真实模型（USE_FAKE_LLM=false），但未配置有效的 "
            "DEEPSEEK_API_KEY。请在 .env 中填写密钥，或改用 "
            "USE_FAKE_LLM=true。"
        )

    provider_label = "FakeLLM" if use_fake else "DeepSeek"

    return Settings(
        deepseek_api_key=deepseek_api_key if has_key else "",
        deepseek_base_url=os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        ).strip(),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "DeepSeek-V4-Flash").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        use_fake_llm=use_fake,
        output_dir=output_dir,
        max_tool_iterations=_parse_max_iterations(),
        tools_json_path=REPO_ROOT / "data" / "tools.json",
        provider_label=provider_label,
        config_notice=notice,
    )
