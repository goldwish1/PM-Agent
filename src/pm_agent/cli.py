"""CLI REPL：欢迎语 / 元指令 / Fake 或 Real Agent Loop。"""

from __future__ import annotations

import sys
import threading

from pm_agent import __version__
from pm_agent.agent.context import context_policy_from_settings
from pm_agent.agent.debug_log import debug_dir
from pm_agent.agent.fake_llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.llm import build_llm_client
from pm_agent.agent.llm_types import LlmApiError, LlmClient
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.session import SessionState
from pm_agent.cli_input import read_user_line
from pm_agent.cli_material import MATERIAL_EMPTY_HINT, resolve_user_material
from pm_agent.cli_render import print_assistant_reply
from pm_agent.cli_terminal import integrated_terminal_hint, setup_terminal_keybinding
from pm_agent.cli_tools import format_tools_reply, is_tools_command
from pm_agent.config import ConfigError, Settings, load_settings
from pm_agent.tools.bootstrap import build_registry_from_path


class _RealLlmWarmup:
    """欢迎语后后台预热 Real 客户端；首条 Agent 轮次 join 取结果。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: LlmClient | None = None
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="pmbox-llm-warmup",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            self._client = build_llm_client(self._settings)
        except Exception as exc:  # 需带回主线程展示
            self._error = exc

    def await_client(self) -> LlmClient:
        self._thread.join()
        if self._error is not None:
            if isinstance(self._error, LlmApiError):
                raise self._error
            raise LlmApiError(
                "unknown",
                "模型客户端初始化失败。请检查本地配置后重启；"
                "你也可以直接说：起草项目章程 / 起草风险登记册。",
            ) from self._error
        assert self._client is not None
        return self._client

WELCOME = """\
╔══════════════════════════════════════════╗
║             pmbox  v{version}             ║
╚══════════════════════════════════════════╝

遇到项目管理问题时，帮你找到合适工具，并协助起草文档。

直接描述你的问题开始，输入 /help 查看指令与演示句，/quit 退出。
"""

HELP = """\
可用指令：
  /help · 帮助     显示本说明
  /new · 新会话    清除上下文并重新开始
  /quit · 退出     结束进程
  /tools · 工具库  浏览知识库（/tools · /tools <slug> · /tools <关键词>）
  /status · 状态   查看运行配置（路径、max_iter、debug/dump 等）
  /debug · 调试    切换终端 [llm] 摘要 on/off
  /dump · 落盘     切换 output/debug JSON 落盘 on/off
  /setup-terminal  配置 Cursor/VS Code 集成终端 Shift+Enter

交互终端下 Shift+Enter 换行、Enter 提交（集成终端需先 /setup-terminal）。
输入 / 或 /h 可边打边补，Tab 补全完整命令。
输入 @ 路径前缀时，会递归提示当前工作目录下的 .md/.txt 文件。
粘贴较长文本（≥10 行或 ≥2KB）时自动折叠为 [paste] +N lines，提交后显示 [paste] ok。
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
    "请用一句话描述你当前的项目问题，例如：下周要立项还没授权。\n"
    "也可试：/tools · 帮我起草项目章程 · /status"
)


def _print_welcome() -> None:
    print(WELCOME.format(version=__version__), flush=True)


def _print_help() -> None:
    print(HELP, flush=True)


def _is_quit(text: str) -> bool:
    return text == "/quit"


def _is_help(text: str) -> bool:
    return text == "/help"


def _is_new(text: str) -> bool:
    return text == "/new"


def _is_status(text: str) -> bool:
    return text == "/status"


def _is_debug(text: str) -> bool:
    return text == "/debug"


def _is_dump(text: str) -> bool:
    return text == "/dump"


def _is_setup_terminal(text: str) -> bool:
    return text == "/setup-terminal"


def _on_off(flag: bool) -> str:
    return "on" if flag else "off"


def _print_startup_config(*, settings: Settings, tool_count: int) -> None:
    model = (
        settings.deepseek_model if not settings.use_fake_llm else "-"
    )
    print(
        f"[config] {settings.provider_label} · {model} · {tool_count} tools",
        flush=True,
    )
    if settings.config_notice:
        print(f"[config] {settings.config_notice}", flush=True)


def _print_runtime_status(
    *,
    settings: Settings,
    tool_count: int,
    debug_on: bool,
    dump_on: bool,
) -> None:
    model = (
        settings.deepseek_model if not settings.use_fake_llm else "-"
    )
    print(
        f"[config] provider={settings.provider_label}  "
        f"model={model}  "
        f"output={settings.output_dir}  "
        f"max_iter={settings.max_tool_iterations}",
        flush=True,
    )
    if settings.config_notice:
        print(f"[config] {settings.config_notice}", flush=True)
    print(f"[config] tools_loaded={tool_count}", flush=True)
    print(
        f"[config] debug={_on_off(debug_on)} dump={_on_off(dump_on)} "
        f"dir={debug_dir(settings.output_dir)}",
        flush=True,
    )


def _client_for_turn(
    *,
    use_fake: bool,
    real_warmup: _RealLlmWarmup | None,
    user_text: str,
) -> LlmClient:
    if use_fake:
        return FakeLlmClient(demo_script_for_user_text(user_text))
    assert real_warmup is not None
    return real_warmup.await_client()


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

    tool_count = len(repo)
    _print_welcome()
    _print_startup_config(settings=settings, tool_count=tool_count)
    print(flush=True)

    debug_on = settings.debug_llm
    dump_on = settings.debug_dump_llm

    hint = integrated_terminal_hint()
    if hint:
        print(hint, flush=True)
        print(flush=True)

    # Real：欢迎语后再后台加载 openai，与用户读提示/打字重叠
    real_warmup: _RealLlmWarmup | None = None
    if not settings.use_fake_llm:
        real_warmup = _RealLlmWarmup(settings)

    user_turn = 0
    while True:
        try:
            user_line = read_user_line("> ")
            raw = user_line.text.strip()
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

        if _is_new(raw):
            state.clear()
            user_turn = 0
            print(
                "已开启新会话。可直接描述新问题，或输入 /help。",
                flush=True,
            )
            continue

        if is_tools_command(raw):
            print_assistant_reply(format_tools_reply(repo, raw))
            continue

        if _is_status(raw):
            _print_runtime_status(
                settings=settings,
                tool_count=tool_count,
                debug_on=debug_on,
                dump_on=dump_on,
            )
            continue

        if _is_debug(raw):
            debug_on = not debug_on
            _print_runtime_status(
                settings=settings,
                tool_count=tool_count,
                debug_on=debug_on,
                dump_on=dump_on,
            )
            continue

        if _is_dump(raw):
            dump_on = not dump_on
            _print_runtime_status(
                settings=settings,
                tool_count=tool_count,
                debug_on=debug_on,
                dump_on=dump_on,
            )
            continue

        if _is_setup_terminal(raw):
            print(setup_terminal_keybinding(), flush=True)
            continue

        material = resolve_user_material(user_line.text, pastes=user_line.pastes)
        for status in material.status_lines:
            print(status, flush=True)
        if not material.should_enter_loop:
            print(MATERIAL_EMPTY_HINT, flush=True)
            continue

        user_turn += 1
        try:
            llm = _client_for_turn(
                use_fake=settings.use_fake_llm,
                real_warmup=real_warmup,
                user_text=material.assembled,
            )
        except LlmApiError as exc:
            print(f"[llm] {exc.user_message}", flush=True)
            print(flush=True)
            continue

        reply = handle_user_turn(
            material.assembled,
            state,
            llm,
            registry,
            max_iterations=settings.max_tool_iterations,
            debug_llm=debug_on,
            debug_dump_llm=dump_on,
            output_dir=settings.output_dir,
            user_turn=user_turn,
            llm_is_fake=settings.use_fake_llm,
            context_policy=context_policy_from_settings(
                context_compact=settings.context_compact,
                context_window_turns=settings.context_window_turns,
            ),
        )
        print(flush=True)
        print_assistant_reply(reply)
        print(flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
