# PM 工具库持续生长系统 Implementation Plan

**Goal:** 建立候选发现、AI 草案生成、质量评审和确定性发布的长期运营闭环。

**Architecture:** `knowledge/catalog_ops.py` 承担领域模型和纯业务逻辑；`scripts/manage_tool_catalog.py` 提供 CLI；`data/tool_candidates.json` 保存运营状态；Workspace Skill 只编排流程；`tools.json` 保持正式真相源。

**Spec:** `docs/superpowers/specs/2026-07-20-tool-catalog-growth-system-design.md`

## Task 1：领域模型与质量门禁

- [x] 新增候选状态、评分卡、候选模型
- [x] 实现候选池读取、唯一性和严格内容校验
- [x] 实现原子写入与发布逻辑
- [x] 为 `PmTool` 增加 `trigger_phrases` 并纳入搜索

## Task 2：运营 CLI

- [x] 实现 `list` / `validate` / `prompt`
- [x] 实现 `ingest` / `review` / `promote`
- [x] 默认定位仓库内正式库和候选池
- [x] 错误输出可读且返回非零状态码

## Task 3：候选池、规则与 Skill

- [x] 新增候选池并放入“非暴力沟通”示范草案
- [x] 新增工具库运营手册
- [x] 新增 Workspace Skill，禁止直接改正式库
- [x] README 增加维护入口

## Task 4：验证与记录

- [x] 新增领域逻辑与 CLI 测试
- [x] 更新 `doc/agent_learn.md`
- [x] 运行目标测试、全量 pytest、ruff
- [x] 检查未覆盖用户已有未提交文件
