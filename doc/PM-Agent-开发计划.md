# PM Agent - 分阶段开发计划

**项目名称**：PM Agent  
**文档版本**：v1.0  
**创建时间**：2026-07-14  
**文档状态**：**已确认**（2026-07-14）  
**关联文档**：  
- PRD：`项目文档/PM-Agent/PM-Agent-MVP-PRD.md`  
- 技术方案：`项目文档/PM-Agent/PM-Agent-技术方案.md`

---

## 1. 开发计划概述

### 1.1 开发目标

将 MVP 按**功能增量**拆成多阶段；每阶段结束都有**可运行原型**。个人学习项目，优先跑通「看得见的 Agent 循环」，再补推荐与起草导出。

### 1.2 开发原则

- **增量开发**：每阶段可演示  
- **优先核心**：先 loop + 假工具，再接真 LLM，再接知识库与导出  
- **Mock 先行**：早期用 FakeLLM / 固定 tool_calls，不依赖真实密钥也能测循环  
- **可切换**：`LlmClient` 协议统一 Fake 与 Real  

---

## 2. 各阶段功能清单

### 阶段 0：工程骨架

**目标**：仓库可安装、可启动、可读配置。

**功能清单**：
- [ ] 初始化 `uv`/`pyproject.toml`、包结构 `src/pm_agent`
- [ ] `.env.example`、`.gitignore`、`README`（如何运行）
- [ ] `config.py` 读环境变量
- [ ] 空 CLI：打印能力说明后 `/quit` 退出

**可运行的最小原型**：
- 执行 `uv run python -m pm_agent` 看到欢迎语，输入退出可结束

**预计时间**：0.5～1 天

---

### 阶段 1：假工具 + 可见循环（不接真模型）

**目标**：证明「循环发动机」存在且可观察。

**功能清单**：
- [ ] `ToolRegistry` + 1～2 个演示工具（如 `echo`、`add`）
- [ ] `FakeLlmClient`：按脚本返回预设 `tool_calls` 再返回最终文本
- [ ] `loop.py`：迭代上限、`[tool]` 日志、tool 结果回填
- [ ] pytest：触顶停止、未知工具返回纠正指令

**可运行的最小原型**：
- CLI 输入任意话 → 终端看到 `[tool] ...` → 看到最终假回复
- 不需要 API Key

**预计时间**：1～2 天

---

### 阶段 2：接真 LLM + 最小 Tool Calling

**目标**：真实模型能选中并调用注册工具。

**功能清单**：
- [ ] `openai` SDK → DeepSeek Real 客户端
- [ ] 系统提示：你是 PM Agent（能力边界草稿版）
- [ ] 将 Registry schemas 传给 API
- [ ] API 错误分类提示（鉴权/限流/网络）
- [ ] Fake / Real 通过环境变量切换

**可运行的最小原型**：
- 配置 Key 后，用户说「调用 echo 说 hello」类指令，可见真实 tool 往返

**预计时间**：1 天

---

### 阶段 3：知识库 + 推荐/详情工具

**目标**：对齐 PRD「推荐库内工具」。

**功能清单**：
- [ ] 拷贝并纳入 `data/tools.json`
- [ ] `ToolsRepository` + `search_tools` / `get_tool_detail` / `recommend_tools`
- [ ] slug 白名单校验
- [ ] 澄清计数：最多 2 轮（可用系统 reminder 辅助）
- [ ] 更新系统提示：不可填工具说明边界

**可运行的最小原型**：
- 「下周立项还没授权」→ 推荐含项目章程等 1～3 工具 + 理由
- 「看一下 project-charter」→ 详情

**预计时间**：1～2 天

---

### 阶段 4：起草 + Markdown 导出（Happy Path B）

**目标**：章程 / 风险登记册闭环到本地文件。

**功能清单**：
- [ ] `draft_project_charter` / `draft_risk_register`（1～3 条）
- [ ] 终端简短预览（工具返回摘要即可）
- [ ] `export_markdown` + 路径白名单 + `output/` 命名规则
- [ ] 拒绝其他工具起草的提示（系统提示 + 无对应 tool）
- [ ] pytest：路径逃逸被拒；导出文件含关键字段

**可运行的最小原型**：
- 对话起草章程 → 确认导出 → 打印路径 → 打开 Markdown 可读
- 风险登记册 1～3 条同样可导出

**预计时间**：1～2 天

---

### 阶段 5：打磨与验收对照 PRD

**目标**：对照 PRD 验收清单自测通过。

**功能清单**：
- [ ] 帮助文案与能力说明对齐 PRD
- [ ] 空输入/工具库缺失/写盘失败文案
- [ ] README：安装、配置 Key、演示脚本（示例对话）
- [ ] （可选）ruff 整理

**可运行的最小原型**：
- 按 PRD「验收标准」四条完整走通一遍并截终端记录

**预计时间**：0.5～1 天

---

## 3. Mock 数据设计

> CLI 项目的 Mock = **FakeLLM 预设轨迹** + **精简 tools 夹具**，不是前端 HTTP Mock。

### 3.1 阶段 1 Mock（循环）

**用途**：无密钥验证 loop。

```python
# Fake 轨迹示例（概念）
FAKE_TURNS = [
    {
        "tool_calls": [
            {"id": "1", "name": "echo", "arguments": {"text": "ping"}}
        ]
    },
    {
        "content": "已调用 echo，结果已看见。这是假模型收尾。"
    },
]
```

### 3.2 阶段 3 Mock（知识库夹具）

**用途**：单测不依赖完整 39 条时，用迷你 JSON。

```python
# tests/fixtures/tools_mini.json
[
  {
    "slug": "project-charter",
    "name": "项目章程",
    "processGroup": "启动",
    "knowledgeArea": "范围",
    "summary": "正式授权项目",
    "description": "...",
    "steps": ["..."],
    "scenarios": ["项目启动"]
  },
  {
    "slug": "risk-register",
    "name": "风险登记册",
    "processGroup": "规划",
    "knowledgeArea": "风险",
    "summary": "记录风险",
    "description": "...",
    "steps": ["..."],
    "scenarios": ["风险识别"]
  }
]
```

### 3.3 阶段 4 Mock（草稿）

```python
mock_charter = {
    "project_name": "学习型 PM Agent",
    "sponsor": "待补充",
    "project_manager": "自己",
    "business_case": "练手造 Agent",
    "high_level_scope": "CLI 推荐与导出",
    "milestones": "MVP 可导出 MD",
    "budget": "待补充",
    "risks": "模型幻觉工具名",
    "signature": "待补充",
}
```

---

## 4. 数据请求抽象层设计

### 4.1 设计目标

- FakeLLM 与 RealLLM **同一接口**  
- 工具执行不关心模型来源  
- 测试可注入 Fake  

### 4.2 接口设计

```python
from typing import Protocol, Any

class LlmClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """返回统一形状：content?, tool_calls?"""
        ...


class FakeLlmClient:
    def __init__(self, script: list[dict[str, Any]]): ...
    def complete(self, messages, tools=None) -> dict[str, Any]: ...


class OpenAICompatibleClient:
    def __init__(self, api_key: str, base_url: str, model: str): ...
    def complete(self, messages, tools=None) -> dict[str, Any]: ...
```

**切换方式**：

```python
# 环境变量 USE_FAKE_LLM=true → Fake
# 否则 → DeepSeek Real
```

### 4.3 使用方式

```python
def handle_user_turn(text: str, llm: LlmClient, registry: ToolRegistry, state: SessionState):
    state.messages.append({"role": "user", "content": text})
    return run_agent_loop(state, llm, registry, max_iterations=10)
```

---

## 5. 开发顺序建议

### 5.1 推荐顺序（学习路径）

**顺序：循环内核先行（推荐）**

0 → 1 → 2 → 3 → 4 → 5

**优势**：
- 最快获得「我在造 Agent」的体感（阶段 1 无需 Key）  
- 真模型接入后再挂业务工具，问题易定位（是 loop 还是 prompt/工具描述）  

不推荐「先做完所有业务工具再写 loop」——易写成脚本而不是 Agent。

### 5.2 关键路径

**必须串行**：
1. 阶段 0 → 1（先有包与 loop）  
2. 阶段 1 → 2（同一 `LlmClient` 换 Real）  
3. 阶段 3 → 4（无推荐/草稿状态则导出无意义）  

**可并行**（有余力时）：
- 阶段 3 的 `tools.json` 裁剪/拷贝 与 阶段 2 Real 客户端调试  
- 阶段 4 的 Markdown 渲染纯函数 可先单测，再挂 tool  

### 5.3 风险提示

- **风险1：过早调 prompt 却没设迭代上限** → 阶段 1 就必须实现 `max_iterations`  
- **风险2：tools.json 一次性塞进系统提示** → 坚持 search/detail 分层  
- **风险3：导出路径未做白名单** → 阶段 4 先写 pytest 再写功能  
- **风险4：澄清死循环** → 代码层 `clarify_count` 硬限制  

---

## 6. 附录

### 6.1 相关文档

- **PRD**：`项目文档/PM-Agent/PM-Agent-MVP-PRD.md`  
- **技术方案**：`项目文档/PM-Agent/PM-Agent-技术方案.md`  
- **技术调研**：`项目文档/PM-Agent/TDD/PM-Agent-技术选型调研-2026-07-14.md`

### 6.2 版本历史

| 版本 | 日期 | 说明 | 作者 |
|------|------|------|------|
| v1.0 | 2026-07-14 | 初始版本（Python 自研 Loop） | - |
| v1.0 确认 | 2026-07-14 | 用户确认开发计划，可进入开发 | - |
