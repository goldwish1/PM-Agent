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
from pm_agent.cli_attach import (
    ATTACH_EMPTY_HINT,
    format_attach_line,
    resolve_attachments,
)
from pm_agent.cli_input import read_user_line
from pm_agent.cli_render import print_assistant_reply
from pm_agent.cli_terminal import integrated_terminal_hint, setup_terminal_keybinding
from pm_agent.cli_tools import format_tools_reply, is_tools_command
from pm_agent.config import ConfigError, load_settings
from pm_agent.tools.bootstrap import build_registry_from_path

WELCOME = """\
╔══════════════════════════════════════════╗
║             pmbox  v{version}             ║
╚══════════════════════════════════════════╝

面向个人项目经理的 CLI 助手。

可推荐 {tool_count} 个 PMBOK 工具；可起草「项目章程 / 风险登记册 /
决策矩阵 / 决策记录」并导出 Markdown。

当前能力：
  · 卡点澄清（≤5 轮）→ 库内推荐 1～3 个工具 → 可查详情
  · 起草章程 / 风险 / 决策矩阵 / 决策记录 → 预览 → 确认后写入 output/
  · FakeLLM / DeepSeek 可切换；Agent 循环过程日志默认可见
  · /tools 浏览知识库；/debug · /dump 切换 LLM 摘要与落盘（dump 默认开）
  · 输入中用 @./notes.md 附带 .md/.txt；交互终端下 @ 可 Tab 补全文件

输入 /help 查看指令与演示句，输入 /quit 退出。
交互终端下 Shift+Enter 换行、Enter 提交；以 / 开头可补全指令，
以 @ 开头可补全 .md/.txt 文件；↑/↓ 可回填本会话已输入内容。
"""

HELP = """\
可用指令：
  /help · 帮助     显示本说明
  /quit · 退出     结束进程
  /tools · 工具库  浏览知识库（/tools · /tools <slug> · /tools <关键词>）
  /debug · 调试    切换终端 [llm] 摘要 on/off
  /dump · 落盘     切换 output/debug JSON 落盘 on/off
  /setup-terminal  配置 Cursor/VS Code 集成终端 Shift+Enter

交互终端下 Shift+Enter 换行、Enter 提交（集成终端需先 /setup-terminal）。
输入 / 或 /h 可边打边补，Tab 补全完整命令。
输入 @ 路径前缀时，会递归提示当前工作目录下的 .md/.txt 文件。
↑/↓ 可回填本会话已提交的输入（进程结束后清空）。

演示句（Fake / 真模型均可试）：
  · 「下周立项，不知道从哪下手」→ 推荐含项目章程
  · 「下周立项 @./kickoff.md」→ 先 [attach] 再推荐
  · 「看一下 project-charter」→ 工具详情
  · 「帮我起草项目章程」→ 草稿预览 → 「确认导出」
  · 「起草风险登记册」→ 预览 → 「确认导出风险登记册」
  · 「起草决策记录」→ 预览 → 「确认导出决策记录」
  · 「起草决策矩阵」→ 预览 → 「确认导出决策矩阵」
  · 「帮我起草 WBS」→ 明确拒绝（仅章程/风险/矩阵/决策可起草）

空输入会提示示例卡点，不会进入 Agent 循环。
"""

EMPTY_INPUT_HINT = (
    "请用一句话描述你当前的项目卡点，例如：下周要立项还没授权。"
)


def _print_welcome(*, tool_count: int) -> None:
    print(
        WELCOME.format(version=__version__, tool_count=tool_count),
        flush=True,
    )


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


def _is_setup_terminal(text: str) -> bool:
    return text == "/setup-terminal"


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

    if len(repo) == 0:
        print(
            "工具库未加载成功，请检查 tools 数据文件后重启。",
            flush=True,
        )
        raise SystemExit(1)

    _print_welcome(tool_count=len(repo))

    print(
        f"[config] provider={settings.provider_label}  "
        f"model={settings.deepseek_model if not settings.use_fake_llm else '-'}  "
        f"output={settings.output_dir}  "
        f"max_iter={settings.max_tool_iterations}",
        flush=True,
    )
    if settings.config_notice:
        print(f"[config] {settings.config_notice}", flush=True)

    print(f"[config] tools_loaded={len(repo)}", flush=True)

    debug_on = settings.debug_llm
    dump_on = settings.debug_dump_llm
    _print_debug_status(
        debug_on=debug_on,
        dump_on=dump_on,
        output_dir=settings.output_dir,
    )
    print(flush=True)

    hint = integrated_terminal_hint()
    if hint:
        print(hint, flush=True)
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

        if is_tools_command(raw):
            print(format_tools_reply(repo, raw), end="", flush=True)
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

        if _is_setup_terminal(raw):
            print(setup_terminal_keybinding(), flush=True)
            continue

        attach = resolve_attachments(raw)
        for item in attach.items:
            print(format_attach_line(item), flush=True)
        if not attach.should_enter_loop:
            print(ATTACH_EMPTY_HINT, flush=True)
            continue

        user_turn += 1
        llm = _client_for_turn(
            use_fake=settings.use_fake_llm,
            real_client=real_client,
            user_text=attach.assembled,
        )
        reply = handle_user_turn(
            attach.assembled,
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
        print(flush=True)
        print_assistant_reply(reply)
        print(flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
