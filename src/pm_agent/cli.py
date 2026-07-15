"""CLI REPL：欢迎语 / 元指令 / Fake 或 Real Agent Loop。"""

from __future__ import annotations

import sys

from pm_agent import __version__
from pm_agent.agent.llm import (
    FakeLlmClient,
    LlmClient,
    OpenAICompatibleClient,
    build_llm_client,
    demo_script_for_user_text,
)
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.session import SessionState
from pm_agent.config import ConfigError, load_settings
from pm_agent.tools.bootstrap import build_registry_from_path

WELCOME = """\
╔══════════════════════════════════════════╗
║             pmbox  v{version}             ║
╚══════════════════════════════════════════╝

面向个人项目经理的 CLI 助手。

可推荐约 39 个 PMBOK 工具；可起草「项目章程 / 风险登记册」并导出 Markdown。

当前能力：
  · 卡点澄清（≤2 轮）→ 库内推荐 1～3 个工具 → 可查详情
  · 起草章程 / 风险登记册（1～3 条）→ 预览 → 确认后写入 output/
  · FakeLLM / DeepSeek 可切换；工具调用可见 [tool] 日志

输入 /help 查看指令与演示句，输入 /quit 退出。
"""

HELP = """\
可用指令：
  /help · 帮助     显示本说明
  /quit · 退出     结束进程

演示句（Fake / 真模型均可试）：
  · 「下周立项，不知道从哪下手」→ 推荐含项目章程
  · 「看一下 project-charter」→ 工具详情
  · 「帮我起草项目章程」→ 草稿预览 → 「确认导出」
  · 「起草风险登记册」→ 预览 → 「确认导出风险登记册」
  · 「帮我起草 WBS」→ 明确拒绝（仅章程/风险可起草）

空输入会提示示例卡点，不会进入 Agent 循环。
"""

EMPTY_INPUT_HINT = (
    "请用一句话描述你当前的项目卡点，例如：下周要立项还没授权。"
)

QUIT_COMMANDS = frozenset({"/quit", "quit", "exit", "退出", "q"})
HELP_COMMANDS = frozenset({"/help", "help", "帮助", "?"})


def _print_welcome() -> None:
    print(WELCOME.format(version=__version__), flush=True)


def _print_help() -> None:
    print(HELP, flush=True)


def _is_quit(text: str) -> bool:
    return text.lower() in QUIT_COMMANDS or text in QUIT_COMMANDS


def _is_help(text: str) -> bool:
    return text.lower() in HELP_COMMANDS or text in HELP_COMMANDS


def _client_for_turn(
    *,
    use_fake: bool,
    real_client: LlmClient | None,
    user_text: str,
) -> LlmClient:
    if use_fake:
        return FakeLlmClient(demo_script_for_user_text(user_text))
    assert real_client is not None
    return real_client


def main() -> None:
    """入口：加载配置 → 欢迎语 → REPL → handle_user_turn。"""
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[config] {exc}", flush=True)
        raise SystemExit(1) from exc

    _print_welcome()

    print(
        f"[config] provider={settings.provider_label}  "
        f"model={settings.deepseek_model if not settings.use_fake_llm else '-'}  "
        f"output={settings.output_dir}  "
        f"max_iter={settings.max_tool_iterations}",
        flush=True,
    )
    if settings.config_notice:
        print(f"[config] {settings.config_notice}", flush=True)

    state = SessionState()
    try:
        registry, repo = build_registry_from_path(
            settings.tools_json_path,
            session=state,
            output_dir=settings.output_dir,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(
            "工具库未加载成功，请检查 tools 数据文件后重启。"
            f"（详情：{exc}）",
            flush=True,
        )
        raise SystemExit(1) from exc

    print(f"[config] tools_loaded={len(repo)}", flush=True)
    if len(repo) == 0:
        print(
            "工具库未加载成功，请检查 tools 数据文件后重启。",
            flush=True,
        )
        raise SystemExit(1)
    print(flush=True)

    real_client: LlmClient | None = None
    if not settings.use_fake_llm:
        real_client = build_llm_client(settings)
        assert isinstance(real_client, OpenAICompatibleClient)

    while True:
        try:
            raw = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。", flush=True)
            break

        if not raw:
            print(EMPTY_INPUT_HINT, flush=True)
            continue

        if _is_quit(raw):
            print("再见。", flush=True)
            break

        if _is_help(raw):
            _print_help()
            continue

        llm = _client_for_turn(
            use_fake=settings.use_fake_llm,
            real_client=real_client,
            user_text=raw,
        )
        reply = handle_user_turn(
            raw,
            state,
            llm,
            registry,
            max_iterations=settings.max_tool_iterations,
        )
        print(f"助手> {reply}", flush=True)
        print(flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
