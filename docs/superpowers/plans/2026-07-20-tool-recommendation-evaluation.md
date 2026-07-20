# PM 工具推荐离线命中评测 Implementation Plan

**Goal:** 用人工黄金集、稳定基线和候选 A/B 回归门禁，量化工具库更新对推荐命中的影响。

**Architecture:** `evaluation/` 提供数据模型、加载与摘要、runner、comparison、gates、reporting
和 service；运营 CLI 提供人机工作流；`promote` 在原子发布前组合正式库基线门禁与候选门禁。

**Spec:** `docs/superpowers/specs/2026-07-20-tool-recommendation-evaluation-design.md`

## Task 1：评测领域层

- [x] 定义黄金用例、单条结果、摘要、版本差异和门禁模型
- [x] 实现数据集加载、唯一 ID 校验、条件启用和稳定摘要
- [x] 实现确定性 Top 1/Top 3/MRR/误召回指标
- [x] 实现用例级版本比较和主要混淆对

## Task 2：回归门禁与报告

- [x] 实现关键退化、共同 Top 3、新增误召回门禁
- [x] 实现候选 12/8/2/2 覆盖与正例 Top 3 ≥80% 门禁
- [x] 实现无时间戳 JSON 基线
- [x] 实现 JSON 与 Markdown 临时报告

## Task 3：黄金集与基线

- [x] 建立 60 条沟通与冲突黄金用例
- [x] 用 `requires_tools` 隔离非暴力沟通与主动倾听候选用例
- [x] 生成当前 20 工具正式库基线
- [x] 验证相同输入重复运行可通过基线门禁

## Task 4：CLI 与发布集成

- [x] 新增 `evaluate` 和筛选参数
- [x] 新增 `eval-prompt` 与人工审核约束
- [x] 新增 `update-baseline` 显式确认
- [x] 新增 `evaluate-candidate` 内存 A/B
- [x] 在 `promote` 写盘前组合两类门禁

## Task 5：验证与治理

- [x] 覆盖数据摘要、指标、条件跳过、比较和门禁单元测试
- [x] 覆盖 CLI 基线更新、报告生成和发布阻断集成测试
- [x] 更新运营手册、Workspace Skill 和变更记录
- [x] 运行全量 pytest 与 ruff
