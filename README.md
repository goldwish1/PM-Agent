# PM Agent

面向个人项目经理的 CLI Agent：根据工作卡点推荐 PMBOK 工具，并起草「项目章程 / 风险登记册」Markdown。

技术栈：Python 3.11+、自研 Agent Loop、`openai` SDK（OpenAI 兼容网关）、Pydantic、标准库 `input()`。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（推荐）

## 安装

```bash
cd PM-Agent
uv sync
cp .env.example .env
# 使用真模型时：编辑 .env，将 DEEPSEEK_API_KEY 换成真实密钥
```

环境变量说明见 `.env.example`（`USE_FAKE_LLM`、`DEEPSEEK_*`、`OUTPUT_DIR`、`MAX_TOOL_ITERATIONS`）。

## 启动

```bash
# FakeLLM（无需 API Key，适合本地练循环与验收演示）
USE_FAKE_LLM=true uv run python -m pm_agent

# DeepSeek / OpenAI 兼容网关（.env 中有有效 Key；未设 USE_FAKE_LLM 时有 Key 自动走 Real）
# 本仓库默认示例：DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
#                 DEEPSEEK_MODEL=DeepSeek-V4-Flash
uv run python -m pm_agent

# 强制 Real
USE_FAKE_LLM=false uv run python -m pm_agent
```

## Fake 演示脚本（对照 PRD）

### Happy Path A：推荐 → 详情

```bash
printf '下周立项，不知道从哪下手\n看一下 project-charter\n/quit\n' \
  | USE_FAKE_LLM=true uv run python -m pm_agent
```

期望：`[tool] recommend_tools`（含项目章程）→ `[tool] get_tool_detail`。

### 澄清（过短输入）

```bash
printf '嗯\n下周立项还没授权\n/quit\n' | USE_FAKE_LLM=true uv run python -m pm_agent
```

期望：先澄清追问，再推荐。

### Happy Path B：章程起草 → 导出

```bash
printf '帮我起草项目章程\n确认导出\n/quit\n' | USE_FAKE_LLM=true uv run python -m pm_agent
ls output/*.md
```

期望：`draft_project_charter` → `export_markdown` → `output/项目章程-*.md` 可读。

### 风险登记册

```bash
printf '起草风险登记册\n确认导出风险登记册\n/quit\n' | USE_FAKE_LLM=true uv run python -m pm_agent
```

### 拒绝路径：不支持的起草

```bash
printf '帮我起草 WBS\n/quit\n' | USE_FAKE_LLM=true uv run python -m pm_agent
```

期望：说明仅支持章程/风险登记册，并可选给出库内说明。

## 常用命令

| 命令 | 说明 |
|------|------|
| `uv sync` | 安装依赖 |
| `uv run python -m pm_agent` | 启动 CLI |
| `uv run pytest` | 运行测试 |
| `uv run ruff check` | 代码风格检查 |

## CLI 指令

| 输入 | 行为 |
|------|------|
| `/help` / `帮助` | 能力说明与演示句 |
| `/quit` / `退出` | 结束进程 |
| 空回车 | 提示示例卡点（不进 Loop） |

## 目录结构

```
src/pm_agent/     # cli / agent / tools / knowledge / export
data/tools.json   # ~39 个 PMBOK 工具
output/           # 导出 Markdown（gitignore）
tests/            # pytest
doc/              # PRD / 方案 / 开发计划 / agent_learn
```

## 开发阶段

**阶段 0～5 已完成**（工程骨架 → Fake 循环 → 真 LLM → 知识库推荐 → 起草导出 → PRD 打磨验收）。

详见 `doc/PM-Agent-开发计划.md`、`CLAUDE.md`。
