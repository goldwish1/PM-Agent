# PM Agent 变更记录

## 新增功能

### 2026-07-20 · 精简欢迎语与 /status

- **新增加了什么功能**：启动欢迎语与 `[config]` 精简为一屏短文案 + 一行摘要；新增只读 `/status` 查看完整运行配置；`/debug` / `/dump` 切换后打印同一套完整状态。
- **原因**：原欢迎语混入功能手册、快捷键与运维配置，首屏过载。
- **一句话方案**：分层披露——启动只保留身份与行动指引；路径 / max_iter / debug·dump 经 `/status`（及 debug 切换）查看。

### 2026-07-20 · 推荐启发式 Keyword Boosts JSON 化

- **新增加了什么功能**：将 `KEYWORD_BOOSTS` / `FALLBACK_SLUGS` 从 `repo.py` 外置为 `data/recommendation_boosts.json`；启动时加载并校验引用 slug 均在正式库；下架门禁与对齐测试改为读该配置。
- **原因**：场景桶词表与排序属于推荐策略数据，硬编码在 Python 中膨胀且与下架/调参耦合紧。
- **一句话方案**：独立 JSON + Pydantic 校验；打分逻辑不变；对齐测试遍历加载后的 boost 规则。

### 2026-07-20 · 复盘与学习家族候选入库

- **新增加了什么功能**：按运营流程为「复盘与学习」家族生成并导入 6 个候选（AAR、起停续、无责事后复盘、项目收尾清单、知识移交、结项最终报告）；`validate` 通过，待人工评审批准。
- **原因**：正式库「收尾与复盘」仅有经验教训登记册，缺少活动复盘、迭代复盘、事故复盘、行政收尾、移交与结项叙事等卡点工具。
- **一句话方案**：`prompt → generated-candidates.json → ingest → validate`；与正式库/归档最近邻做边界分流，评审确认后再 `review --approve`。

### 2026-07-20 · 复盘家族首批四工具批准

- **新增加了什么功能**：人工确认后批准 `after-action-review`、`start-stop-continue`、`blameless-postmortem`、`knowledge-handover`（均为 10/10）；已生成各自 `eval-prompt`；`project-closure-checklist` 与 `final-project-report` 仍为 drafted。
- **原因**：用户选择优先上架复盘动作类与知识移交，收尾清单与结项报告暂缓。
- **一句话方案**：`review --approve` + `eval-prompt`；评测用例须人工审核后再合并黄金集。

### 2026-07-20 · 复盘家族 48 条黄金用例合并

- **新增加了什么功能**：将 AAR / 起停续 / 无责事后复盘 / 知识移交各 12 条用例草案并入 `tool_recommendation_cases.json`（共 +48，总计 108）；已 `export-cases`。
- **原因**：用户审核草案后确认合并，为候选 A/B 与 promote 门禁提供 `requires_tools` 条件用例。
- **一句话方案**：旧基线 `evaluate` 先通过 → 合并 JSON → export；基线摘要已变，待人工 `update-baseline --yes`。

### 2026-07-20 · 复盘家族四工具发布与推荐启发式拆分

- **新增加了什么功能**：正式发布 `after-action-review`、`start-stop-continue`、`blameless-postmortem`、`knowledge-handover`（正式库 20→24）；拆分收尾 `KEYWORD_BOOSTS` 并补事前验尸/5 Why 桶；修正边界用例上下文避免「不是XXX」误触发；补充搜索/推荐回归测试。
- **原因**：候选 A/B 初评因粗粒度「复盘/移交」boost 与上下文误匹配导致正例未进 Top3、边界误召回。
- **一句话方案**：场景化 boost + 短触发语 + 净化边界上下文；逐个 `promote` 并更新基线；最终 Top1 97% / Top3 94.4% / 误召回 6.7%。

### 2026-07-20 · 混淆对推荐启发式优化

- **新增加了什么功能**：拆分沟通类 `KEYWORD_BOOSTS` 为冲突/SBI/对齐/金字塔/艰难对话场景桶；收窄「担心/老板/冲突/依赖」等过宽词；补强 5 个沟通正式工具的 `trigger_phrases`；增加 12 条混淆对 Top1 回归测试。
- **原因**：基线 Top1 混淆暴露沟通大桶把 SBI 排第一、零命中走章程 FALLBACK、以及过宽关键词抢分。
- **一句话方案**：场景化 boost + 更具体触发语；评测 Top1 50%→100%、误召回 50%→14.3%，门禁通过后更新基线。

### 2026-07-20 · 评测用例与基线可读视图导出

- **新增加了什么功能**：运营脚本新增 `export-cases` / `export-baseline`，把黄金用例与正式基线导出为 `output/evaluation/` 下的 Markdown + 可筛选 HTML；`update-baseline --yes` 写盘后自动刷新基线视图。
- **原因**：JSON 真相源不便人工审阅，需要不入库的可读视图，且不参与 digest/门禁。
- **一句话方案**：`views.py` 渲染 md/html；CLI 导出到 gitignore 的 `output/evaluation/`；基线更新路径自动双写视图。

### 2026-07-20 · 工具库下架与候选清理

- **新增加了什么功能**：运营脚本新增 `retire`（正式库归档到 `tools.archive.json`）与 `discard`（候选池移除）；联动清理评测黄金用例；对 `draftable` 与推荐硬编码 slug 默认门禁，需 `--force`；CLI 需 `--yes` 才写盘。
- **原因**：运营闭环原先只有进库，淘汰只能手改 JSON，易破坏归档约定与评测基线纪律。
- **一句话方案**：`retire` 原子归档 + 候选改 rejected + scrub 用例；`discard` 专清候选；基线仍须人工 `update-baseline`。

### 2026-07-20 · 工具推荐黄金评测与发布回归门禁

- **新增加了什么功能**：新增 60 条沟通工具黄金用例、稳定正式基线、确定性离线评测器、Top 1/Top 3/MRR/误召回指标、当前/候选 A/B 对比、JSON/Markdown 报告，以及 `evaluate`、`evaluate-candidate`、`eval-prompt`、`update-baseline` 命令；`promote` 默认先执行正式库基线和候选覆盖门禁。
- **原因**：内容门禁只能保证工具条目写得完整，不能回答“新增工具是否真的更容易命中、是否伤害旧工具、是否产生误召回”；少量固定原句测试也无法量化整体变化。
- **一句话方案**：人工黄金集 + `requires_tools` 条件用例 + 本地确定性 runner + 稳定摘要基线 + 阻断式 RegressionGate；AI 只生成待审核语料，基线只能显式人工更新。

### 2026-07-20 · 清理流程化第一批工具

- **新增加了什么功能**：将 32 条偏 PMBOK 流程文档的工具迁入 `data/tools.archive.json`；正式库收缩为 20 条实操/方法类工具（含章程、风险登记册，以及干系人登记册、甘特图、经验教训登记册、风险报告）；同步重写推荐启发式与 FakeLLM 演示脚本。
- **原因**：首批工具过于流程化，个人 PM 卡点更需要可立刻上手的方法与协作工具；先瘦身再按运营体系逐步加回。
- **一句话方案**：保留集固定拆分正式库与归档；`keyword_boosts` 仅引用保留 slug；加回须走候选池评审发布，禁止直接从 archive 拷回。

### 2026-07-17 · 工具库场景分类（移除 PMBOK 分类字段）

- **新增加了什么功能**：`tools.json` 新增多值 `use_cases` 作为唯一运行时分类；`/tools` 按实用场景分组浏览；搜索与推荐输出含场景标签。
- **原因**：五过程组/知识领域不适合个人 PM 找工具，且与决策类等工具实际用法脱节。
- **一句话方案**：11 个实用场景 + 删除 `process_group`/`knowledge_area`；PMBOK 概念仅保留在文档。

### 2026-07-17 · CLI 多行输入（Shift+Enter / Enter）

- **新增加了什么功能**：交互终端下 Shift+Enter 换行、Enter 提交整段输入；管道模式仍为单行。
- **原因**：长 prompt 需分段书写；对齐 ChatGPT / Cursor 等主流 Agent 习惯。
- **一句话方案**：`prompt_toolkit` 开启 `multiline=True`；Enter 绑定提交；Shift+Enter CSI 重映射为 `ControlJ` 后插入换行。

### 2026-07-17 · 集成终端 `/setup-terminal`

- **遇到的问题**：Cursor/VS Code 集成终端默认把 Shift+Enter 当成 Enter（`\r`），无法换行。
- **原因**：终端未发送 `\u001b[13;2u` 等区分序列，应用层无法区分按键。
- **解决方案**：新增 `/setup-terminal` 写入编辑器 `keybindings.json`；启动时未配置则提示；临时可用 Ctrl+J 换行。

### 2026-07-17 · 工具库 Top 10 内容写厚

- **新增加了什么功能**：对 10 个高频工具加厚 `description` / `steps` / `scenarios`，并增加最低厚度单测。
- **原因**：原条目过薄，推荐召回与陪跑素材不够支撑「下一步问什么 / 产出什么」。
- **一句话方案**：只扩现有字段、不改 schema；Top 10 写满规范，其余保持原样。

**Top 10 slug**：`project-charter`、`risk-register`、`stakeholder-register`、`wbs`、`raci-matrix`、`issue-log`、`change-management-plan`、`status-report`、`requirements-documentation`、`lessons-learned-register`。

**写厚规范**：`description` ≥80 字（含何时用/别用/常见坑）；`steps` 5～8 条（动作→产出）；`scenarios` 6～12 条口语卡点（含易混/反例）。

**模板示例（项目章程字段形态）**：

```text
description: 何时用：…。何时别用：…。常见坑：…
steps: 「明确业务依据 → 产出一句话说明」…
scenarios: 「下周要立项，还没正式授权」…「别和范围说明书搞混（反例）」…
```

### 2026-07-17 · CLI ↑/↓ 输入历史回填

- **新增加了什么功能**：交互终端下可用 ↑/↓ 回填本会话已提交的输入行。
- **原因**：多轮对话时常需复用/微调上一条指令，缺少 shell 式历史体验。
- **一句话方案**：`cli_input.read_user_line` 传入模块级 `InMemoryHistory`；非 TTY 仍走 `input()`。

### 2026-07-17 · CLI `/tools` 知识库浏览

- **新增加了什么功能**：REPL 元指令 `/tools`（目录 / slug 详情 / 关键词搜索）；欢迎语展示真实工具数量。
- **原因**：开发时需随时看见知识库内容，又不想维护第二份目录或热加载。
- **一句话方案**：只读读已加载的 `ToolsRepository`，`cli_tools` 纯函数格式化输出。

### 2026-07-17 · TTY 下最终回复 Markdown 渲染

- **新增加了什么功能**：交互终端中助手最终回复经 `rich` 渲染 Markdown（加粗、列表、表格等）；管道/非 TTY 仍纯文本。
- **原因**：模型默认输出 Markdown，终端 `print` 不渲染，可读性差。
- **一句话方案**：`cli_render.print_assistant_reply` 仅结果层、仅 `isatty` 时 `Console`+`Markdown`；过程日志不动；系统提示少用宽表。

### 2026-07-17 · TTY 下 LLM 等待同行 spinner

- **新增加了什么功能**：`thinking: LLM调用开始。` 同行显示经典 `|/-\\` 动画，返回后擦除再打印 `response`。
- **原因**：非流式等待时屏幕静止，用户易误以为卡住。
- **一句话方案**：`llm_spinner` 后台线程仅在 TTY + LLM 阻塞期间刷新；管道/非交互保持静态一行。

### 2026-07-17 · 过程层 response 显示 LLM 耗时

- **新增加了什么功能**：每轮迭代的 `response` 行追加 `耗时 Nms`，与 `tool_result` 风格一致。
- **原因**：第二轮等待体感长，原先只打印工具耗时，无法区分本地工具与远程 LLM 调用。
- **一句话方案**：`loop` 对 `llm.complete` 用 `perf_counter` 计时，经 `trace_response` 打印。

### 2026-07-17 · 决策记录（Decision Record）可起草工具

- **新增加了什么功能**：新增可起草工具 `draft_decision_record`，支持增量合并 9 个字段（决策标题、背景、备选方案、最终决定、决策依据、预期影响、决策人、决策日期、状态）；配套 `render_decision_markdown` 渲染模板与 `export_markdown(doc_type=decision)` 导出路径；tools.json 新增 `decision-record` 条目。
- **原因**：用户在与 AI 讨论决策场景（选方案、权衡 trade-off）后，希望 AI 能归档成结构化文档而非只留在对话历史中。
- **一句话方案**：完全复用 charter 已验证的「陪跑咨询 → 起草 → 预览 → 确认导出」模式，按 6 处改动（session/draft/render/export/bootstrap/prompts）+ tools.json 条目实施。

- **新增加了什么功能**：推荐与起草之间新增通用陪跑讨论态；`start_consulting` / `note_consulting_fact` 沉淀事实，起草时基于沉淀提炼字段并预览确认。
- **原因**：用户真实旅程是决策陪伴，而非推荐后直接填表；讨论内容需结构化沉淀以免起草时丢失。
- **一句话方案**：SessionMode.CONSULTING + consult 工具 + 系统提示词约束；不强制陪跑，无 notes 时保留逐字段兜底。

### 2026-07-17 · 决策分析工具族 + 决策矩阵可起草

- **新增加了什么功能**：`tools.json` 新增 6 个决策分析脚手架（SWOT、事前验尸、MoSCoW、5 Why、强制场分析、六顶思考帽）与可起草 `decision-matrix`；`draft_decision_matrix` 支持准则/方案/打分增量合并；`export_markdown(doc_type=decision_matrix)` 导出打分表 Markdown；`recommend_by_question` 增加决策类关键词映射。
- **原因**：仅有决策记录归档出口、缺少思考入口；用户纠结选方案时需要结构化工具引导，量化比较场景需要可导出的打分表作为过程证据。
- **一句话方案**：知识型脚手架 + 决策矩阵可起草 + 决策记录统一结论归档；提示词明确三者分工，不为每个脚手架各做导出。

## 解决问题

### 2026-07-20 · `uv run pmbox` 冷启动偏慢

- **遇到的问题**：启动到欢迎语约 1.3～1.5s，体感拖沓。
- **原因**：`cli` 顶栏经 `llm.py` 同步 `import openai`（约 1.1s）；Real 模式还在 REPL 前构造客户端。
- **解决方案**：拆成 `llm_types` / `fake_llm` / `openai_llm` + 轻量门面；欢迎语后后台预热 Real 客户端，首条 Agent 轮次再 join。

### 2026-07-16 · `@` 补全后中文 IME 闪烁

- **遇到的问题**：先 `@` 补全文件后再输入中文，按空格确认时文字会先消失再出现；直接输入中文无此问题。
- **原因**：`extract_attach_fragment` 把 `@file` 后的自然语言也当作路径前缀，触发 `complete_while_typing` 与 IME 预编辑冲突。
- **解决方案**：未加引号的 `@xxx` 片段内一旦出现空白即结束附件补全，与 `cli_attach` 的 `@([^\s@]+)` 规则对齐。

### 2026-07-16 · 分支评审：目录拒绝用例与无关文件

- **遇到的问题**：`test_load_rejects_directory` 对无扩展名目录先命中「仅支持 .md/.txt」，未覆盖「不是普通文件」；分支误跟踪无关 `.cursor/plans` 文件。
- **原因**：扩展名校验在 `is_file()` 之前；计划文件曾被一并提交。
- **解决方案**：用名为 `kickoff.md` 的目录测目录拒绝；`git rm` 移除误跟踪 plan；补仅 `@file` 时 `assembled` 以 `---` 开头的用例。

## 新增功能

### 2026-07-16 · `@` 附件路径 Tab 补全

- **新增加了什么功能**：交互终端下输入 `@` 路径前缀时，可递归补全当前工作目录下的 `.md/.txt` 文件；带空格路径自动补成引号形式。
- **原因**：当前 `@` 仅支持发送后解析，缺少类似 Claude Code 的发现性，用户需要手打完整路径。
- **一句话方案**：在 `cli_input.py` 增加 slash/@ 组合 completer；slash 补全保持不变，`@` 仅增强输入体验，不改发送后附件解析逻辑。

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

### 2026-07-17 · 陪跑打分误触澄清上限

- **遇到的问题**：决策矩阵陪跑多轮打分后，用户说「先2后3」时模型返回空或行为异常；debug 显示每轮注入了「澄清已达上限，必须 recommend_tools」。
- **原因**：`clarify_count` 在任意模式下对含 `?` 的无工具回复计数，并将 `CONSULTING` 等模式覆盖为 `CLARIFYING`；陪跑追问被误计满 5 轮后，强制提示与用户导出/起草意图冲突。
- **解决方案**：`clarify_count` 与强制 `recommend_tools` 提示仅在 `IDLE`/`CLARIFYING` 早期发现阶段生效；`get_system_prompt` 同步按 `mode` 省略 clarify 后缀。

### 2026-07-15 · 删除元指令关键词别名

- **遇到的问题**：帮助/退出同时存在 slash（`/help`、`/quit`）与关键词别名（`帮助`、`退出`、`q` 等），与补全列表双源维护，易不一致。
- **原因**：早期兼顾中文关键词习惯；引入 slash 补全后别名变为冗余。
- **解决方案**：CLI 仅精确识别 `/help`、`/quit`；删除 `QUIT_COMMANDS`/`HELP_COMMANDS` 别名集合；文档同步。

### 2026-07-14 · 清理旧脚手架以便按 Python 选型重建

- **遇到的问题**：仓库中曾有按 TypeScript 选型落地的阶段 1 产物，与现行方案不一致。
- **原因**：技术选型由 TS 调整为 Python（见技术选型调研修订说明）。
- **解决方案**：删除未提交的旧脚手架；保留 `doc/` + `CLAUDE.md`；从阶段 0 按 Python 结构重建。
