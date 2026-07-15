# PM Agent 变更记录

## 新增功能

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

### 2026-07-14 · 清理旧脚手架以便按 Python 选型重建

- **遇到的问题**：仓库中曾有按 TypeScript 选型落地的阶段 1 产物，与现行方案不一致。
- **原因**：技术选型由 TS 调整为 Python（见技术选型调研修订说明）。
- **解决方案**：删除未提交的旧脚手架；保留 `doc/` + `CLAUDE.md`；从阶段 0 按 Python 结构重建。
