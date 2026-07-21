## 项目目的

PM Agent 是一个面向个人项目经理的 CLI 工具。用户可通过终端多轮对话：

- 根据工作卡点获得 PM 工具推荐（如项目章程、风险登记册、决策与沟通方法等，正式库约 20 个）
- 自动起草「项目章程」和「风险登记册」Markdown 文档并导出

技术栈：Python 3.11+ + `openai` SDK → DeepSeek API

## 项目状态

当前处于 **MVP 可演示完成**（阶段 0～5）。需求/方案见 `docs/`；实现见 `src/pm_agent/`。

## 关键文档

- `docs/PM-Agent-MVP-PRD.md` — 产品需求文档
- `docs/PM-Agent-技术方案.md` — 技术架构方案（Python、自研 Loop、Tool Registry）
- `docs/PM-Agent-技术选型调研-2026-07-14.md` — 技术选型调研（含语言从 TS → Python 的修订说明）
- `docs/PM-Agent-开发计划.md` — 分阶段开发计划（6 个阶段：0～5）
- `docs/需求孵化.md` — 需求孵化记录
- `docs/agent_learn.md` — **功能变更与问题解决记录**（见下方说明）

## 变更记录要求

每当新增功能或解决问题时，必须在 `docs/agent_learn.md` 中做简要记录：

**新增功能** 需记录：
- 新增加了什么功能
- 原因
- 一句话方案

**解决问题** 需记录：
- 遇到的问题
- 原因
- 解决方案

## 技术选型

| 层级 | 选型 | 理由 |
|------|------|------|
| 语言/运行时 | **Python 3.11+** | Agent 教程/示例多；脚本迭代快；学习摩擦力低 |
| Agent 编排 | **自研 Loop** + 迭代上限 + `[tool]` 日志 | 练手核心，不上 LangChain/LangGraph |
| LLM | `openai` Python SDK → DeepSeek（兼容 OpenAI） | Tool Calls 成熟，Provider 可切换 |
| 校验 | **Pydantic** | 校验 tool arguments，防幻觉字段 |
| CLI | 标准库 `input()` | 最小可用，零依赖 |
| 数据 | `data/tools.json` + `recommendation_boosts.json` + 内存会话 + `output/` | 无数据库也能闭环 |
| 配置 | `.env` + `.gitignore` | 密钥安全 |
| 包管理 | **uv**（推荐）或 pip + venv | 现代 Python 工具链 |
| 测试 | **pytest** | 优先测纯函数与路径守卫 |
| 风格 | **ruff**（format + lint） | 统一代码风格 |

## 目录结构

```
pm-agent/
├── README.md
├── pyproject.toml          # uv/pip 项目元数据
├── .env.example
├── .gitignore
├── data/
│   ├── tools.json          # 自包含工具库（正式库约 20 个）
│   └── recommendation_boosts.json  # 推荐启发式场景桶
├── output/                 # 导出目录（gitignore）
├── src/
│   └── pm_agent/
│       ├── __init__.py
│       ├── __main__.py     # python -m pm_agent
│       ├── cli.py          # REPL（input() 循环）
│       ├── config.py       # 环境变量
│       ├── agent/
│       │   ├── loop.py     # Agent Loop（迭代上限、[tool] 日志）
│       │   ├── llm.py      # OpenAI 兼容客户端封装
│       │   ├── session.py  # SessionState（messages, draft, clarify_count）
│       │   └── prompts.py  # 系统提示词
│       ├── tools/
│       │   ├── registry.py # 注册/查找/执行、schema 导出
│       │   ├── bootstrap.py# 组装入口
│       │   ├── knowledge/  # search / recommend / detail
│       │   ├── draft/      # charter / risk
│       │   ├── export/     # markdown（路径白名单）
│       │   └── demo/       # echo / add
│       ├── knowledge/
│       │   └── repo.py     # ToolsRepository（加载 tools.json + recommendation_boosts.json）
│       └── export/
│           └── render.py   # Markdown 模板渲染
└── tests/
    ├── test_repo.py
    ├── test_path_guard.py
    ├── test_draft_merge.py
    └── test_loop_limits.py
```

## 开发计划（6 阶段）

| 阶段 | 内容 | 可演示 |
|------|------|--------|
| 0 | 工程骨架 | `uv run pmbox` 看到欢迎语 |
| 1 | 假工具 + 可见循环 | CLI 输入 → 看到 `[tool]` 日志（无需 API Key） |
| 2 | 接真 LLM + Tool Calling | 真实模型调用注册工具 |
| 3 | 知识库 + 推荐/详情工具 | 「下周立项」→ 推荐含项目章程等 1～3 个工具 |
| 4 | 起草 + Markdown 导出 | 对话起草章程/风险登记册 → 导出 `output/*.md` |
| 5 | 打磨与验收 | 对照 PRD 验收清单自测通过 |

## 开发命令

```bash
# 安装依赖
uv sync

# 启动开发（使用 FakeLLM，无需 API Key）
USE_FAKE_LLM=true uv run pmbox

# 启动开发（使用 DeepSeek）
uv run pmbox

# 等价：uv run python -m pm_agent

# 运行测试
uv run pytest

# 代码风格检查
uv run ruff check
```

## 架构要点

- **单体进程**：CLI 读输入 → Agent Loop 调 LLM → 执行本地 Tool → 更新会话状态/写文件 → 打印回复
- **自研 Agent Loop**：`while iter < max_iterations` 循环，`[tool]` 日志可见，迭代上限（默认 10）
- **Tool Registry**：可增删工具，支持 `search_tools`、`get_tool_detail`、`recommend_tools`、`draft_project_charter`、`draft_risk_register`、`export_markdown`
- **LLM 抽象**：`LlmClient` 协议统一 FakeLLM 与 RealLLM，通过 `USE_FAKE_LLM` 切换
- **Mock 先行**：先假 LLM/真工具，再接真实模型
- **无外部依赖**：无数据库、无 Web 框架、无 HTTP 后端
- **路径白名单**：`export_markdown` 仅允许写入 `output/` 目录

## 其他要求

- 这是我的个人学习项目，我希望从 0 到 1 了解熟悉 Agent 的开发过程，因此文件目录需要高度结构化，符合 AI Agent 的最佳实践
