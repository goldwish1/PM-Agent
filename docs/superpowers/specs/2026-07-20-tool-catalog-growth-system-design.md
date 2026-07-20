# 设计：PM 工具库持续生长系统

**日期**：2026-07-20  
**状态**：已实现  
**范围**：仓库内候选发现、AI 草案生成、质量评审、确定性发布；不改变 pmbox 主对话流程

## 1. 目标

将“偶尔手工向 `tools.json` 增加条目”升级为可持续运营闭环：

1. 候选工具与正式工具分离；
2. AI 负责生成结构化草案，不直接修改正式库；
3. 脚本负责导入、评分、校验和发布；
4. 发布过程可测试、可审查、失败无副作用；
5. 新工具通过自身触发短语参与检索，减少长期维护硬编码关键词。

## 2. 形态选择

采用三层组合：

- **仓库模块/脚本（主系统）**：确定性状态流转、质量门禁、发布；
- **规范文档（规则）**：准入标准、运营节奏和工具家族路线图；
- **Workspace Skill（AI 加速器）**：编排“生成提示词 → 导入 → 评审 → 发布”，不能绕过脚本。

不采用“仅 Skill”方案，因为无法可靠承担版本、测试和发布原子性；不采用“脚本直接调用模型”方案，避免把密钥、模型成本和非确定性引入基础运营链路。

## 3. 数据模型

### 3.1 正式库

`data/tools.json` 继续是运行时唯一真相源。`PmTool` 新增可选字段：

- `trigger_phrases: list[str]`：用户可能说出的口语触发句；参与搜索索引。

历史条目无需迁移，默认空列表。

### 3.2 候选池

新增 `data/tool_candidates.json`，单条候选包含：

- 身份：`slug`、`name`、`family`；
- 价值：`problem`、`differentiation`、`proposed_use_cases`；
- 召回：`trigger_phrases`；
- 生命周期：`status`、`quality_score`、`review_notes`；
- 内容草案：`tool`（完整 `PmTool`，可为空）。

状态：`inbox → drafted → review → approved → published`；另有 `rejected`。

### 3.3 评分卡

五项各 0～2 分，总分 10 分：

1. `trigger_clarity`：卡点能否由用户自然表达；
2. `actionability`：是否有明确可执行步骤；
3. `output_clarity`：是否产生明确成果；
4. `boundary_clarity`：与已有工具边界是否清楚；
5. `recommendation_value`：是否值得进入推荐前三。

批准门槛：总分 ≥8，且严格内容校验通过。

## 4. 质量门禁

候选发布前必须满足：

- slug 在候选池与正式库均不重复；
- `use_cases` 合法；
- `description` 明确包含“何时用 / 何时别用 / 常见坑”；
- `steps` 为 5～8 条，且每条包含“→”表达动作与产出；
- `scenarios` 为 6～12 条，至少包含一条“易混”或“反例”；
- 至少 3 条口语 `trigger_phrases`；
- 候选与正式草案 slug 一致；
- 状态为 `approved` 且评分 ≥8。

发布采用临时文件替换，全部校验通过后才同时更新正式库与候选状态。

## 5. 命令接口

新增 `scripts/manage_tool_catalog.py`：

- `list [--status]`：浏览候选；
- `validate`：校验候选池和正式库；
- `prompt --family --count`：生成包含现有工具上下文和硬约束的 AI 提示词；
- `ingest FILE`：将 AI 输出的候选 JSON 合并进候选池；
- `review SLUG --scores a,b,c,d,e [--approve] [--note]`：评分并进入评审/批准；
- `promote SLUG [--dry-run]`：通过门禁后发布到正式库。

## 6. AI Skill

新增 Workspace Skill：`.claude/skills/pm-tool-catalog/SKILL.md`。它必须：

1. 先读取运营规则；
2. 通过脚本生成上下文提示词；
3. 只将 AI 结果写入候选 JSON；
4. 执行 `ingest` 和 `validate`；
5. 评审与发布前明确展示评分和差异；
6. 不直接编辑 `data/tools.json`。

## 7. 运营节奏

建议按月或双周运行：

1. 从真实卡点补充候选；
2. 每轮只扩一个工具家族；
3. AI 生成 5～8 个候选；
4. 人工评审少量高分条目；
5. 发布后补推荐回归用例；
6. 定期复审低命中、重叠或不可执行工具。

## 8. 测试

覆盖：模型加载、重复检测、评分门槛、严格内容门禁、提示词上下文、导入去重、dry-run 无副作用、发布成功、触发短语参与搜索。全量 pytest 与 ruff 必须通过。
