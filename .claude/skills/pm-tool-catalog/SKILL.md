---
name: pm-tool-catalog
description: "持续运营 pmbox 的 PM 工具库。Use when: 新增工具、批量生成工具、扩展工具家族、评审候选工具、发布 tools.json、下架/归档工具、清理候选池、工具库治理、非暴力沟通等实用工具入库。"
---

# PM Tool Catalog Operator

用于持续发现、生成、评审和发布 PM 工具。正式工具库是受保护产物，所有新增内容必须经过候选池和确定性脚本。

## 必读

开始前读取：

1. `doc/PM-工具库运营手册.md`
2. `src/pm_agent/knowledge/categories.py`
3. `data/tool_candidates.json`
4. `data/evaluation/tool_recommendation_cases.json`（改期望时）
5. `data/evaluation/baseline.json`（改基线或门禁对照时）

查阅评测用例或基线表现时，优先导出并打开可读视图，不要把整份 JSON 当阅读界面：

```bash
uv run python scripts/manage_tool_catalog.py export-cases
uv run python scripts/manage_tool_catalog.py export-baseline
```

产物在 `output/evaluation/cases.{md,html}` 与 `baseline.{md,html}`。HTML 支持搜索与筛选。
视图禁止手改；与 JSON 不一致时以 JSON 为准并重新导出。

需要了解正式条目风格时，读取 `data/tools.json` 中 2～3 个最接近的高质量工具，不要把整个文件原样复制到回复。

## 工作流

### 1. 确定本轮工具家族

一次只处理一个家族。若用户已指定（例如沟通、复盘、问题分析），直接使用；未指定时，根据现有候选池和正式库缺口提出一个家族建议。

### 2. 生成上下文提示词

运行：

`uv run python scripts/manage_tool_catalog.py prompt --family <家族> --count <数量> --output output/tool-generation-prompt.txt`

使用生成的提示词约束候选结构。AI 输出必须是纯 JSON 数组，写到 `output/generated-candidates.json`，不得直接写 `data/tools.json`。

### 3. 导入与校验

运行：

- `uv run python scripts/manage_tool_catalog.py ingest output/generated-candidates.json`
- `uv run python scripts/manage_tool_catalog.py validate`

若失败，只修复候选池或生成结果；不得放宽门禁来让错误通过。

### 4. 评审

逐个检查真实卡点、动作、产出、边界和推荐价值。五项各 0～2 分。先向用户展示候选摘要、最近邻工具差异和建议评分；未经用户确认，不执行 `--approve`。

批准命令：

`uv run python scripts/manage_tool_catalog.py review <slug> --scores a,b,c,d,e --approve --note <说明>`

### 5. 建立命中评测

批准候选后，为它生成至少 12 条待审核语料的提示词：

`uv run python scripts/manage_tool_catalog.py eval-prompt <slug> --output output/<slug>-eval-prompt.txt`

AI 只能生成草案。人工审核后，将用例合并到
`data/evaluation/tool_recommendation_cases.json`。候选专属用例必须设置
`requires_tools=["<slug>"]`，并满足至少 8 条正例、2 条边界例、2 条反例。
合并后运行 `export-cases`，用 HTML/Markdown 复核可读视图。

修改黄金集之前先运行一次 `evaluate` 确认旧基线正常；合并并审核用例后，显式更新基线：

- `uv run python scripts/manage_tool_catalog.py update-baseline`
- 人工确认指标后：`uv run python scripts/manage_tool_catalog.py update-baseline --yes`
  （成功后会自动刷新 `output/evaluation/baseline.md` 与 `baseline.html`）

禁止自动接受 AI 生成语料，禁止为了通过门禁自动更新基线。

### 6. 候选 A/B 评测

运行：

`uv run python scripts/manage_tool_catalog.py evaluate-candidate <slug>`

阅读 `output/evaluation/candidate-<slug>.md`。关键用例退化、共同用例 Top 3 下降、
新增误召回、覆盖不足或候选正例 Top 3 低于 80% 时，必须修复候选内容或用例；
不得放宽门禁。Top 1/MRR 下降为告警，需要人工解释。

### 7. 发布

先执行 dry-run：

`uv run python scripts/manage_tool_catalog.py promote <slug> --dry-run`

通过后再正式发布：

`uv run python scripts/manage_tool_catalog.py promote <slug>`

发布后必须补充对应的搜索或推荐回归测试，并运行 pytest 与 ruff。

### 8. 下架与清理

正式库淘汰用归档，不直接抹除：

```bash
uv run python scripts/manage_tool_catalog.py retire <slug> --dry-run
uv run python scripts/manage_tool_catalog.py retire <slug> --note <说明> --yes
```

- 工具移入 `data/tools.archive.json`，从 `data/tools.json` 移除。
- 默认清理黄金集中对该 slug 的引用；可用 `--keep-cases` 跳过（仅调试）。
- `draftable=true` 或出现在推荐硬编码列表时，必须人工确认后加 `--force`。
- 写盘后运行 `evaluate`，再人工 `update-baseline --yes`。

候选池清理：

```bash
uv run python scripts/manage_tool_catalog.py discard <slug> --dry-run
uv run python scripts/manage_tool_catalog.py discard <slug> --yes
```

若候选为 `published` 且正式库仍存在同 slug，必须先 `retire`。

## 硬约束

- 禁止绕过脚本直接向 `data/tools.json` 添加新工具。
- 禁止手改 `data/tools.json` / `data/tools.archive.json` 删除或下架工具。
- 禁止让导入内容预设为 `approved` 或 `published`。
- 禁止将 `draftable` 设为 true，除非已有对应 `draft_*` 实现和导出链路。
- 禁止一次混合多个工具家族。
- 禁止以数量替代质量；评分低于 8/10 不批准。
- 禁止绕过 `promote` 的命中门禁，或在未人工审核时更新黄金集/基线。
- 禁止绕过 dry-run/确认直接归档 `draftable` 或硬编码推荐 slug（须 `--force`）。
- 禁止手改 `output/evaluation/cases.*` / `baseline.*` 视图；改期望只改 JSON 再 export。
- 每次新增或解决问题后更新 `doc/agent_learn.md`。
