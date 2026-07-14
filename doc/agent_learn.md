# PM Agent 变更记录

## 新增功能

### 2026-07-14 · 阶段 1：工程骨架 + Mock Agent 循环

- **新增加了什么功能**：可启动的 CLI 骨架；`ToolsRepository` + 全量 `data/tools.json`（39 工具）；`ToolRegistry` 与 `search_tools` / `get_tool_detail`；`LLMClient` + `MockProvider` 剧本；最小 `AgentLoop`（迭代上限与 `[tool]` 日志）；`readline` REPL（`/help` `/quit`）及非交互 smoke（`PM_AGENT_SMOKE=1`）。
- **原因**：按开发计划先打通「假 LLM / 真工具」可见循环，不依赖真实 API 即可演示 Agent 形态。
- **一句话方案**：CLI 读入 → Mock 按关键词产出 tool_calls → Registry 执行本地工具 → 回灌 tool 消息 → 打印列表/详情。

## 解决问题

### 2026-07-14 · 清理阶段 1 代码以便更新技术选型

- **遇到的问题**：阶段 1 已按原选型落地脚手架与 Mock 循环，但需要重新调整技术选型，原实现不再适用。
- **原因**：技术路线待更新，保留旧脚手架会产生路径/依赖噪音，干扰后续按新方案重建。
- **解决方案**：删除未提交的阶段 1 产物（`src/`、`data/`、`output/`、`package.json`、`package-lock.json`、`tsconfig.json`、`.env.example`、`.gitignore`、`node_modules/`），仓库回到以 `doc/` + `CLAUDE.md` 为主的设计/规划状态；不提交、不改动 git 历史。
