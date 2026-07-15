"""CLI REPL：欢迎语 / 元指令 / Fake 或 Real Agent Loop。"""

from __future__ import annotations

import sys
from pathlib import Path

from pm_agent import __version__
from pm_agent.agent.debug_log import debug_dir
from pm_agent.agent.llm import (
    FakeLlmClient,
    LlmClient,
    OpenAICompatibleClient,
    build_llm_client,
    demo_script_for_user_text,
)
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.session import SessionState
from pm_agent.cli_input import read_user_line
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
  · /debug · /dump 切换 LLM 摘要与落盘（dump 默认开）

输入 /help 查看指令与演示句，输入 /quit 退出。
交互终端下以 / 开头可 Tab 补全指令。
"""

HELP = """\
可用指令：
  /help · 帮助     显示本说明
  /quit · 退出     结束进程
  /debug · 调试    切换终端 [llm] 摘要 on/off
  /dump · 落盘     切换 output/debug JSON 落盘 on/off

交互终端下输入 / 或 /h 可边打边补，Tab 补全完整命令。

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


def _print_welcome() -> None:
    print(WELCOME.format(version=__version__), flush=True)


def _print_help() -> None:
    print(HELP, flush=True)


def _is_quit(text: str) -> bool:
    return text == "/quit"


def _is_help(text: str) -> bool:
    return text == "/help"


def _is_debug(text: str) -> bool:
    return text == "/debug"


def _is_dump(text: str) -> bool:
    return text == "/dump"


def _on_off(flag: bool) -> str:
    return "on" if flag else "off"


def _print_debug_status(
    *,
    debug_on: bool,
    dump_on: bool,
    output_dir: Path,
) -> None:
    print(
        f"[config] debug={_on_off(debug_on)} dump={_on_off(dump_on)} "
        f"dir={debug_dir(output_dir)}",
        flush=True,
    )


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

    debug_on = settings.debug_llm
    dump_on = settings.debug_dump_llm
    _print_debug_status(
        debug_on=debug_on,
        dump_on=dump_on,
        output_dir=settings.output_dir,
    )
    print(flush=True)

    real_client: LlmClient | None = None
    if not settings.use_fake_llm:
        real_client = build_llm_client(settings)
        assert isinstance(real_client, OpenAICompatibleClient)

    user_turn = 0
    while True:
        try:
            raw = read_user_line("> ").strip()
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

        if _is_debug(raw):
            debug_on = not debug_on
            _print_debug_status(
                debug_on=debug_on,
                dump_on=dump_on,
                output_dir=settings.output_dir,
            )
            continue

        if _is_dump(raw):
            dump_on = not dump_on
            _print_debug_status(
                debug_on=debug_on,
                dump_on=dump_on,
                output_dir=settings.output_dir,
            )
            continue

        user_turn += 1
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
            debug_llm=debug_on,
            debug_dump_llm=dump_on,
            output_dir=settings.output_dir,
            user_turn=user_turn,
            llm_is_fake=settings.use_fake_llm,
        )
        print(f"● {reply}", flush=True)
        print(flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
