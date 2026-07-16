# PM Agent 变更记录

## 解决问题

### 2026-07-16 · 分支评审：目录拒绝用例与无关文件

- **遇到的问题**：`test_load_rejects_directory` 对无扩展名目录先命中「仅支持 .md/.txt」，未覆盖「不是普通文件」；分支误跟踪无关 `.cursor/plans` 文件。
- **原因**：扩展名校验在 `is_file()` 之前；计划文件曾被一并提交。
- **解决方案**：用名为 `kickoff.md` 的目录测目录拒绝；`git rm` 移除误跟踪 plan；补仅 `@file` 时 `assembled` 以 `---` 开头的用例。

## 新增功能

### 2026-07-16 · CLI @ 附带材料辅助推荐

- **新增加了什么功能**：输入 `@路径` 附带 `.md/.txt`；CLI 打印 `[attach]` 并将正文注入本轮消息，prompt 引导少问快荐。
- **原因**：用户常有卡点相关纪要，纯对话澄清成本高。
- **一句话方案**：`cli_attach` 解析/截断/组装 + CLI 接入；不新增通用读盘工具。

### 2026-07-16 · tools 按业务域分包

- **新增加了什么功能**：`tools/` 拆为 `knowledge` / `draft` / `export` / `demo` 子包；根级保留 `registry.py` + `bootstrap.py`。
- **原因**：扁平文件混杂多域，后续扩工具时难扫；按域分组更符合 Agent 工具层惯例。
- **一句话方案**：一工具一文件仍同居 Args+execute+register；bootstrap 统一组装；无行为变更。

### 2026-07-16 · 工具 pure 标记与保守并行

- **新增加了什么功能**：`ToolSpec.pure`；同轮 `tool_calls` 全部为已知 pure 工具且数量 >1 时用线程池并行执行。
- **原因**：对齐书中工具六字段与副作用安全；纯读工具可并行，起草/导出仍串行。
- **一句话方案**：知识类/demo 标 `pure=True`，draft/export 标 `False`；Loop 保守调度，结果与 trace 仍按原顺序写回。

### 2026-07-16 · 澄清轮次上限 2→5

- **新增加了什么功能**：澄清硬上限由 2 轮放宽为 5 轮。
- **原因**：过短输入时 2 轮往往信息仍不足就被强制推荐，交互偏紧。
- **一句话方案**：`MAX_CLARIFY_ROUNDS = 5`，同步系统提示与 PRD/技术方案文案。

### 2026-07-16 · Agent 循环过程层可见日志

- **新增加了什么功能**：每轮迭代打印 `thinking` / `response` / `tool_call` / `tool_result`（含耗时）；与最终 `●` 回复分层显示。
- **原因**：对齐「循环可见」学习目标与 PRD；原先仅有 `[tool] … → ok|err`，缺少迭代边界、结果摘要与耗时。
- **一句话方案**：`agent/trace.py` 过程层（分隔行+缩进，不用 `●`）；`loop.py` 接入并计时 `execute`；CLI 空一行后打印结果层 `●`。

### 2026-07-15 · debug 落盘改为每 turn 一个 JSON

- **遇到的问题**：每次 `llm.complete` 写 `turn-NNN-iter-MM.json` 且重复拷贝全量 messages，回放一轮用户对话要开多个文件。
- **原因**：L2 按「单次 API 调用」落盘，未按用户回合聚合。
- **解决方案**：`TurnDebugDump` 写 `turn-NNN.json`，`iterations[]` 累加每次调用；回合结束写入 `final_assistant` + messages 快照 + `usage_total`。

### 2026-07-15 · LLM 调试观测（L1 终端 + L2 落盘）

- **新增加了什么功能**：每次 `llm.complete` 可观测输入/输出摘要与 token 用量；默认将完整 messages 写入 `output/debug/`；支持 `/debug`、`/dump` 与 `PMBOX_DEBUG` / `PMBOX_DEBUG_DUMP`。
- **原因**：开发阶段需回放发给模型的上下文与用量，持续迭代 prompt / tool / loop。
- **一句话方案**：`complete` 返回 `usage`；`debug_log` 打印 `[llm]` 并 dump JSON；CLI 局部开关 + dump 默认 on。

### 2026-07-15 · 交互终端 slash 命令前缀补全

- **新增加了什么功能**：TTY 下输入 `/` 或 `/h` 边打边出候选，Tab 可补全 `/help`、`/quit`。
- **原因**：接近常见 Agent CLI（如 Claude Code）的 slash UX，减少手打完整元指令。
- **一句话方案**：`prompt_toolkit` Completer + `complete_while_typing`；非 TTY（管道）回退 `input()`。

### 2026-07-15 · REPL 对齐 Claude Code 对话样式

- **新增加了什么功能**：输入提示符改为仅 `>`；AI 回复以 `●` 起头；去掉 `助手>` / `pmbox>` 说话人文字标签。
- **原因**：对齐 Claude Code 式 REPL，减轻标签噪音。
- **一句话方案**：`cli.py` 中 `input("> ")` 与 `print(f"● {reply}")`；`[tool]` 日志不变。

### 2026-07-15 · REPL 输入提示符改为 pmbox>

- **新增加了什么功能**：CLI 输入提示由 `你>` 改为 `pmbox>`。
- **原因**：与产品名对齐，提示符风格接近常见 CLI（如 `mysql>`）。
- **一句话方案**：`cli.py` 中 `input("pmbox> ")`；回复侧 `助手>` 不变。

### 2026-07-15 · CLI 对外名与入口改为 pmbox

- **新增加了什么功能**：终端命令与产品名统一为 `pmbox`（欢迎语、系统提示、导出页脚）；`[project.scripts]` 入口 `pmbox`。
- **原因**：产品对外名称从「PM Agent」改为更好记的 CLI 命令。
- **一句话方案**：保留 Python 包 `pm_agent`；`pyproject.toml` 注册 `pmbox`；运行时文案与 README/开发命令同步；`python -m pm_agent` 仍可用。

### 2026-07-14 · 适配 NIO OpenAI 兼容网关

- **新增加了什么功能**：默认 `DEEPSEEK_BASE_URL=https://api.deepseek.com/v1`、`DEEPSEEK_MODEL=DeepSeek-V4-Flash`；Real 客户端超时 120s；`.env.example` / README 说明兼容网关。
- **原因**：用户实际走 NIO 网关而非官方 `api.deepseek.com`。
- **一句话方案**：保留 `DEEPSEEK_*` 变量名，仅改默认 base_url/model 与文档表述。

### 2026-07-14 · 阶段 5：打磨与 PRD 验收

- **新增加了什么功能**：对齐 PRD 边界文案（空输入/鉴权限流网络/写盘失败/迭代上限）；Fake 拒绝路径（起草 WBS 等）；工具库加载失败退出提示；README 完整演示脚本；验收单测。
- **原因**：对照 PRD Happy Path A/B、拒绝路径与异常场景可自测通过。
- **一句话方案**：补齐 Fake 关键词剧本与 CLI/错误文案，用管道脚本覆盖主路径，不改核心架构。

### 2026-07-14 · 阶段 4：起草 + Markdown 导出

- **新增加了什么功能**：`SessionState` 章程/风险草稿；`draft_project_charter` / `draft_risk_register` / `export_markdown`；`render.py` 中文模板；`output/` 路径白名单；Fake 剧本覆盖「起草→确认导出」；pytest 覆盖合并与路径逃逸。
- **原因**：对齐 PRD Happy Path B，闭环「起草预览 → 确认 → 本地 Markdown」。
- **一句话方案**：草稿挂会话；Pydantic 校验参数；导出前 confirmed=true；写盘前 `resolve_safe_output_file` 拒绝逃逸。

### 2026-07-14 · 阶段 3：知识库 + 推荐/详情工具

- **新增加了什么功能**：充实 `data/tools.json`（39 条）；`ToolsRepository`；注册 `search_tools` / `get_tool_detail` / `recommend_tools`（slug 白名单）；澄清计数上限 2；Fake 剧本支持立项→推荐含项目章程；系统提示改为库内推荐优先。
- **原因**：对齐 PRD「仅推荐库内工具」主路径，使 Fake/Real 均可演示推荐闭环。
- **一句话方案**：本地 JSON 知识库 + 白名单校验的 recommend；Loop 维护 clarify_count；Fake 按关键词走 recommend 剧本。

### 2026-07-14 · 阶段 2：接真 LLM + Tool Calling

- **新增加了什么功能**：`OpenAICompatibleClient`（`openai` SDK → DeepSeek）；`USE_FAKE_LLM` / 有无 Key 自动切换 Fake↔Real；API 错误分类（鉴权/限流/网络）；PM Agent 能力边界系统提示；CLI 去掉强制 Fake；配套 mock 单测。
- **原因**：让真实模型能选中并调用已注册演示工具，完成「真 Tool Calling」闭环。
- **一句话方案**：同一 `LlmClient.complete` 协议；Real 走 Chat Completions + tools schema，异常映射中文提示后由 Loop 返回用户。

### 2026-07-14 · 阶段 1：假工具 + 可见 Agent 循环

- **新增加了什么功能**：`ToolRegistry`（注册/执行/OpenAI schema）；演示工具 `echo`/`add`；`FakeLlmClient` 剧本；`run_agent_loop` / `handle_user_turn`（迭代上限、`[tool]` 日志、未知工具纠正）；`SessionState`；CLI 将业务输入接入 Fake 循环；pytest 覆盖触顶、未知工具、成功路径。
- **原因**：证明「循环发动机」存在且可观察，无需 API Key 即可演示 Agent 形态。
- **一句话方案**：Fake 按剧本产出 tool_calls → Registry 本地执行并打 `[tool]` → 结果回填 messages → 最终假回复或触顶提示。

### 2026-07-14 · 阶段 0：工程骨架（Python）

- **新增加了什么功能**：可用 `uv` 安装的 Python 包结构（`src/pm_agent`）；`config.py` 读 `.env`；CLI 欢迎语 + `/help` `/quit`；占位包（`agent/` `tools/` `knowledge/` `export/`）；最小 `data/tools.json`、`output/`、`tests/`。
- **原因**：按开发计划阶段 0，先做到仓库可安装、可启动、可读配置，再进入假工具循环。
- **一句话方案**：`uv` + `pyproject.toml` 脚手架；`python -m pm_agent` → `cli.main()` 打欢迎语后 REPL，阶段 0 不接 Agent Loop。

### 2026-07-14 · （已废弃）原 TypeScript 阶段 1 脚手架

- **新增加了什么功能**：曾按旧选型落地 CLI / Mock 循环等（已删除）。
- **原因**：学习路线改为 Python；旧实现与当前 `CLAUDE.md` / 开发计划冲突。
- **一句话方案**：清理后改以 Python 阶段 0 起重新实现（见上一条）。

## 解决问题

### 2026-07-15 · 删除元指令关键词别名

- **遇到的问题**：帮助/退出同时存在 slash（`/help`、`/quit`）与关键词别名（`帮助`、`退出`、`q` 等），与补全列表双源维护，易不一致。
- **原因**：早期兼顾中文关键词习惯；引入 slash 补全后别名变为冗余。
- **解决方案**：CLI 仅精确识别 `/help`、`/quit`；删除 `QUIT_COMMANDS`/`HELP_COMMANDS` 别名集合；文档同步。

### 2026-07-14 · 清理旧脚手架以便按 Python 选型重建

- **遇到的问题**：仓库中曾有按 TypeScript 选型落地的阶段 1 产物，与现行方案不一致。
- **原因**：技术选型由 TS 调整为 Python（见技术选型调研修订说明）。
- **解决方案**：删除未提交的旧脚手架；保留 `doc/` + `CLAUDE.md`；从阶段 0 按 Python 结构重建。
