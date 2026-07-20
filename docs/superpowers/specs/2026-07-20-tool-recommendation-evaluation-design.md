# 设计：PM 工具推荐离线命中评测

**日期**：2026-07-20  
**状态**：已实现  
**范围**：工具推荐黄金集、稳定基线、候选 A/B、发布回归门禁；第一版不调整推荐算法

## 1. 问题

内容评分和字段厚度只能判断一个工具是否“写得完整”，不能判断：

1. 用户换一种说法时能否命中；
2. 新工具是否挤掉正确的旧工具；
3. 相邻工具是否被误召回；
4. 更新后整体推荐质量是提升还是退化。

少量直接复制 `trigger_phrases` 的单元测试也无法提供整体指标。因此需要独立于 LLM、
可重复运行、能比较版本差异的离线评测层。

## 2. 设计原则

- **确定性**：直接调用 `ToolsRepository.recommend_by_question`，不调用模型；
- **人工真相**：AI 可以生成草案，黄金期望和基线必须人工审核；
- **条件启用**：候选专属用例用 `requires_tools` 表达，正式库未含候选时跳过；
- **双门禁**：内容质量与推荐命中分别检查，互不替代；
- **稳定产物**：基线无时间戳，数据与工具摘要由规范化 JSON 的 SHA-256 得到；
- **失败无副作用**：候选门禁失败时不修改 `tools.json` 或候选状态。

## 3. 领域模型

`EvaluationCase` 包含：

- `acceptable_top1`：第一名允许出现的工具集合；
- `required_top3`：前三名必须包含的工具集合；
- `forbidden_top3`：前三名不得出现的工具集合；
- `requires_tools`：启用该用例所需的工具；
- `case_type`：`typical`、`paraphrase`、`boundary`、`negative`；
- `critical`：关键场景，退化时阻断发布。

`EvaluationReport` 保存摘要、工具摘要、聚合指标和每条用例的实际排名。
`ComparisonReport` 将变化分为 improved、regressed、changed-neutral、unchanged、
newly-activated 和 skipped。`GateResult` 汇总 blocking/warning 问题。

## 4. 数据集与基线

- 黄金集：`data/evaluation/tool_recommendation_cases.json`；
- 正式基线：`data/evaluation/baseline.json`；
- 临时报告：`output/evaluation/`。

第一批数据集为沟通与冲突家族 60 条：当前 5 个正式工具各 7 条，非暴力沟通和主动倾听
候选各 12 条，外加 1 条全局反例。当前正式库启用 36 条、跳过 24 条候选条件用例。

## 5. 指标

- Top 1 accuracy；
- Top 3 recall；
- MRR；
- 禁止工具误召回率；
- Top 1 主要混淆对；
- 单条用例的通过、退化和新增误召回。

初始受控基线只描述当前行为，不代表质量目标：Top 1 为 50.0%，Top 3 为 62.1%，
MRR 为 0.506，禁止工具误召回率为 50.0%。后续应先用评测暴露问题，再单独优化推荐算法。

## 6. 门禁

阻断条件：

1. 关键用例由通过变为失败；
2. 共同启用用例的 Top 3 命中率下降；
3. 出现新的 `forbidden_top3` 命中；
4. 候选少于 12 条、正例少于 8 条、边界例少于 2 条或反例少于 2 条；
5. 候选正例自身进入 Top 3 的比例低于 80%；
6. 候选关键用例失败；
7. 黄金集摘要与正式基线不一致。

整体 Top 1 或 MRR 下降第一版只告警，由人判断。`promote` 没有跳过门禁的参数。

## 7. 命令

- `evaluate`：评测正式库，可按 family/tag 筛选；
- `eval-prompt`：为候选生成待人工审核的用例提示词；
- `update-baseline`：展示当前指标，只有显式 `--yes` 才写基线；
- `evaluate-candidate`：将已批准候选以内存方式加入仓库并执行 A/B；
- `promote`：先跑正式基线和候选门禁，通过后才调用原子发布。

## 8. 不在第一版范围

- 不使用 LLM-as-judge；
- 不采集线上点击或起用数据；
- 不自动修改 `keyword_boosts`、触发短语或黄金期望；
- 不把初始基线指标解释为合格线；
- 不因门禁失败自动更新基线。
