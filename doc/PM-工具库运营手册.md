# PM 工具库运营手册

## 1. 目标

工具库追求的不是数量，而是：用户描述真实卡点时能命中正确工具，并能在 10 分钟内开始行动。

正式工具位于 `data/tools.json`；所有新增工具必须先进入 `data/tool_candidates.json`，禁止让 AI 直接修改正式库。

历史流程文档类工具保存在 `data/tools.archive.json`，仅供人工参考与对照。若要从归档加回正式库，必须重新走候选池 `ingest → review → promote`，禁止直接拷贝绕过评审。

## 2. 固定流程

1. **发现**：从真实对话、复盘和工具家族缺口收集候选。
2. **生成**：按单一工具家族生成 5～8 个结构化草案。
3. **导入**：脚本检查重复和越权状态后进入候选池。
4. **评审**：按五维评分卡评分，低于 8 分不得批准。
5. **评测**：用人工审核的黄金用例比较正式库与候选库，检查命中和误召回。
6. **发布**：内容门禁、正式库基线和候选 A/B 门禁均通过后原子写入正式库。
7. **复盘**：观察推荐命中、实际起用和工具重叠，必要时降级、合并或淘汰。
8. **下架**：正式库用 `retire` 归档到 `tools.archive.json`；候选池用 `discard` 移除；禁止手改 JSON 删除。

## 3. 常用命令

```bash
# 查看候选
uv run python scripts/manage_tool_catalog.py list

# 生成“沟通与冲突”家族的 AI 提示词
uv run python scripts/manage_tool_catalog.py prompt \
  --family 沟通与冲突 --count 6 --output output/tool-generation-prompt.txt

# 将 AI 仅输出的 JSON 数组导入候选池
uv run python scripts/manage_tool_catalog.py ingest output/generated-candidates.json

# 全池校验
uv run python scripts/manage_tool_catalog.py validate

# 五项依次为：触发明确、可操作、产出明确、边界清晰、推荐价值
uv run python scripts/manage_tool_catalog.py review nonviolent-communication \
  --scores 2,2,2,2,2 --approve --note "沟通家族首批评审"

# 当前正式库离线评测；报告写到 output/evaluation/
uv run python scripts/manage_tool_catalog.py evaluate

# 为候选生成 12 条待人工审核的黄金用例提示词
uv run python scripts/manage_tool_catalog.py eval-prompt nonviolent-communication \
  --output output/nonviolent-communication-eval-prompt.txt

# 人工审核并合并黄金用例后，显式更新基线；不得由 AI 自动执行
# （--yes 成功后会自动刷新 baseline.md / baseline.html）
uv run python scripts/manage_tool_catalog.py update-baseline --yes

# 导出黄金用例 / 基线的可读视图（Markdown + HTML，写入 output/evaluation/）
uv run python scripts/manage_tool_catalog.py export-cases
uv run python scripts/manage_tool_catalog.py export-baseline

# 对已批准候选运行正式库/候选库 A/B 评测
uv run python scripts/manage_tool_catalog.py evaluate-candidate nonviolent-communication

# promote 会重复执行基线与候选门禁；先无副作用演练，再正式发布
uv run python scripts/manage_tool_catalog.py promote nonviolent-communication --dry-run
uv run python scripts/manage_tool_catalog.py promote nonviolent-communication

# 正式库下架 → 归档（先演练，再确认写盘）
uv run python scripts/manage_tool_catalog.py retire legacy-tool --dry-run
uv run python scripts/manage_tool_catalog.py retire legacy-tool --note "与 XXX 合并" --yes

# draftable 或硬编码推荐 slug 需人工确认后加 --force
uv run python scripts/manage_tool_catalog.py retire project-charter --force --yes

# 候选池清理（published 且正式库仍存在时须先 retire）
uv run python scripts/manage_tool_catalog.py discard draft-slug --dry-run
uv run python scripts/manage_tool_catalog.py discard draft-slug --yes
```

全局可用 `--tools`、`--archive`、`--candidates`、`--cases`、`--baseline` 和
`--evaluation-output` 指向临时文件，便于试验和测试；参数需放在子命令之前。

## 4. 评分规则

| 维度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| 触发明确性 | 用户不会这样描述问题 | 需专业词才能触发 | 有多条自然口语卡点 |
| 可操作性 | 只有理念 | 有步骤但含糊 | 每一步可直接执行 |
| 产出明确性 | 没有结果 | 有模糊结论 | 有清单、话术、表格或行动 |
| 边界清晰性 | 与现有工具重复 | 有部分重叠 | 何时用/不用清晰 |
| 推荐价值 | 不值得前三 | 仅窄场景有用 | 高频且应进入前三 |

总分低于 8 分不得批准。PM 相关性是前置门槛：不是项目经理真实工作场景的工具，不进入评分。

## 5. 内容门禁

- description 同时包含“何时用 / 何时别用 / 常见坑”；
- steps 为 5～8 条，每条是“动作 → 产出”；
- scenarios 为 6～12 条，至少包含一条易混或反例；
- trigger_phrases 至少 3 条用户原话；
- use_cases 只能使用运行时合法分类；
- 默认 `draftable=false`，除非代码中已存在对应专用起草工具；
- 与正式库、候选池均不得重复。

## 6. 家族化增长

建议每轮只处理一个家族：

1. 沟通与冲突；
2. 问题分析；
3. 决策与取舍；
4. 会议与协作；
5. 复盘与学习；
6. 向上管理与汇报。

每轮宁可发布 1～3 个高质量工具，也不要批量上架未经使用验证的条目。

## 7. 发布后复盘

发布后至少增加一条对应的推荐/搜索回归测试。定期检查：

- 是否能被用户原话命中；
- 是否经常与相邻工具混淆；
- 用户是否能按步骤得到明确产出；
- 是否长期没有被使用；
- 是否应该合并、降级或删除。

## 8. 推荐命中评测

### 8.1 真相源与产物

- 黄金用例：`data/evaluation/tool_recommendation_cases.json`，纳入版本控制；
- 正式基线：`data/evaluation/baseline.json`，纳入版本控制且不含时间戳；
- 临时报告：`output/evaluation/*.json` 与 `*.md`，不纳入版本控制；
- 可读视图：`output/evaluation/cases.{md,html}` 与 `baseline.{md,html}`，由
  `export-cases` / `export-baseline` 生成，不纳入版本控制；禁止手改，不参与 digest/门禁；
- 运行器直接调用 `ToolsRepository.recommend_by_question`，不调用 LLM，不产生费用，
  同一份工具库与用例应得到相同结果。

查阅用例或基线时，优先打开 HTML（可搜索/筛选）；Markdown 适合在编辑器中快速扫读。
改完黄金用例 JSON 后请手动导出：

```bash
uv run python scripts/manage_tool_catalog.py export-cases
uv run python scripts/manage_tool_catalog.py export-baseline
```

`update-baseline --yes` 写盘成功后会自动刷新 `baseline.md` / `baseline.html`。

每条用例可以同时声明：Top 1 可接受工具、Top 3 必含工具、Top 3 禁止工具，
以及 `requires_tools`。候选专属用例必须在 `requires_tools` 中填写候选 slug；
候选未发布时自动跳过，加入候选仓库后自动启用。

### 8.2 用例最低覆盖

每个新候选至少 12 条：

- 至少 8 条正例，包含用户原话和不复制触发短语的改写；
- 至少 2 条边界例，明确与最近邻工具如何分流；
- 至少 2 条反例，用 `forbidden_top3` 防止过度召回；
- 强场景标记 `critical=true`；
- 正例的候选 Top 3 命中率至少 80%。

AI 可以通过 `eval-prompt` 生成 JSON 草案，但必须由人审核真实性、期望工具和边界。
禁止自动把 AI 输出写入黄金集，禁止自动更新基线。

### 8.3 指标与门禁

报告包含 Top 1 accuracy、Top 3 recall、MRR、禁止工具误召回率和主要混淆对。
第一版发布门禁规则：

- 关键用例退化：阻断；
- 共同用例 Top 3 命中率下降：阻断；
- 新增禁止工具误召回：阻断；
- 候选覆盖不足或候选正例 Top 3 低于 80%：阻断；
- Top 1 或 MRR 整体下降：告警，人工判断。

`promote` 默认执行全部门禁，不提供跳过评测的发布参数。门禁失败时只生成报告，
不得修改正式库或候选状态。

### 8.4 基线更新纪律

修改黄金集后，旧基线会因摘要不一致而阻断发布。正确顺序是：

1. 改黄金集前先运行 `evaluate`，确认正式库相对旧基线无退化；
2. 人工评审并提交黄金用例；
3. 运行 `update-baseline` 查看指标；
4. 人工确认变更合理后，再加 `--yes` 覆盖基线；
5. 运行 `evaluate`，确认新基线通过；
6. 再运行候选 A/B 与发布流程。

更新基线不是“让测试变绿”的手段。若正式推荐算法或工具内容同时变化，应先解释每条退化，
再决定修复实现还是接受并记录新的产品预期。

### 8.5 下架后的基线纪律

`retire` 默认会清理黄金集中对该 slug 的引用，并删除因此变成孤儿的典型/改写正例。
清理后旧基线摘要会失效，正确顺序是：

1. `retire <slug> --dry-run` 确认受影响用例；
2. `retire <slug> --yes` 写盘；
3. 运行 `evaluate`，确认正式库相对预期合理；
4. 人工确认后 `update-baseline --yes`；
5. 若工具曾出现在 `KEYWORD_BOOSTS` / `FALLBACK_SLUGS`，同步修改
   `src/pm_agent/knowledge/repo.py`（`--force` 只绕过门禁，不改代码）。
