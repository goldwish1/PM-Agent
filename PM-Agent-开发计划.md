# PM Agent - 分阶段开发计划

**项目名称**：PM Agent  
**文档版本**：v1.0  
**创建时间**：2026-07-14  
**关联文档**：  
- PRD：`项目文档/PM-Agent/PM-Agent-MVP-PRD.md`  
- 技术方案：`项目文档/PM-Agent/PM-Agent-技术方案.md`

---

## 1. 开发计划概述

### 1.1 开发目标

将 MVP 按「功能增量」拆成可演示阶段：每阶段结束都能在终端跑起来，优先打通 **Agent 循环可见性 → 推荐 → 起草 → 导出**。

### 1.2 开发原则

- **增量开发**：每阶段有可运行原型  
- **优先核心**：先假 LLM / 真工具，再接真模型  
- **Mock 先行**：抽象 `LLMClient`，Mock 与真实 Provider 可切换  
- **可切换性**：`LLM_PROVIDER=mock|deepseek|openai`  

> 说明：本项目无 Web 前端，「Mock」指 **Mock 大模型返回**（含预设 tool_calls），而非 Mock HTTP 后端。

---

## 2. 各阶段功能清单

### 阶段1：工程骨架 + 假循环可见

**目标**：仓库可启动；不依赖真实 API 也能演示「用户输入 → 工具调用日志 → 回复」。

**功能清单**：
- [ ] 初始化 `pm-agent`：`package.json`、`tsconfig`、`.env.example`、`.gitignore`
- [ ] 复制 `tools.json` 到 `data/`
- [ ] 实现 `ToolsRepository`（load / findBySlug）
- [ ] 实现 `ToolRegistry` + 2 个 pure 工具：`search_tools`、`get_tool_detail`
- [ ] 实现 `LLMClient` 接口 + **MockProvider**（按用户关键词返回固定 tool_calls）
- [ ] 实现最小 `AgentLoop`（maxIterations、`[tool]` 日志）
- [ ] 实现 `readline` REPL（`/help` `/quit`）

**可运行的最小原型**：
- 启动 `npx tsx src/index.ts`
- 输入「找一下风险相关工具」→ 见到 `[tool] search_tools` → 终端打印工具列表

**预计时间**：1～2 天

---

### 阶段2：真实 LLM + 推荐闭环

**目标**：接入 DeepSeek Tool Calls，完成「卡点 → 推荐 1～3」主路径。

**功能清单**：
- [ ] DeepSeek Provider（`openai` SDK + baseURL）
- [ ] 系统提示词（能力边界、白名单、澄清≤2）
- [ ] `recommend_tools` + slug 校验
- [ ] 澄清轮次计数（SessionState）
- [ ] 环境变量与错误文案（鉴权/网络失败）

**可运行的最小原型**：
- 配置 `DEEPSEEK_API_KEY` 后，描述卡点 → 得到带理由的 1～3 个合法工具推荐

**预计时间**：1～2 天

---

### 阶段3：章程起草 + Markdown 导出

**目标**：打通 Happy Path B（章程）。

**功能清单**：
- [ ] `draft_project_charter`（合并字段、「待补充」）
- [ ] Session mode：`drafting_charter` / `preview`
- [ ] `MarkdownExporter` + `export_markdown`（路径白名单）
- [ ] 终端简短预览 + 打印导出路径
- [ ] 单测：路径逃逸被拒绝

**可运行的最小原型**：
- 「帮我起草项目章程」→ 多轮补字段 → 导出 `output/项目章程-*.md` → 能打开编辑

**预计时间**：1～2 天

---

### 阶段4：风险登记册 + 拒绝路径硬化

**目标**：完成第二起草工具，并卡死非法起草。

**功能清单**：
- [ ] `draft_risk_register`（默认 1～3 条）
- [ ] 对非白名单起草请求：工具/提示词双重约束 + 体验验收
- [ ] 连续工具失败止损与迭代上限提示完善
- [ ] README：启动、环境变量、演示脚本

**可运行的最小原型**：
- 风险路径导出 Markdown 成功  
- 要求「起草 WBS」被拒绝并引导

**预计时间**：1 天

---

### 阶段5（可选加强）：体验与回归

**目标**：练手复盘与稳定性，不扩产品范围。

**功能清单**：
- [ ] 黄金对话回归（Mock 固定剧本）
- [ ] 日志格式统一、帮助文案完善  
- [ ] （可选）OpenAI Provider 切换验证  

**可运行的最小原型**：
- `npm test` 覆盖 loop 上限、推荐校验、导出路径

**预计时间**：0.5～1 天

---

## 3. Mock 数据设计

### 3.1 阶段1 Mock：LLM 剧本

**用途**：无 API Key 时开发 Loop / Tools。

**数据结构**：

```typescript
type MockScript = {
  whenUserIncludes: string; // 关键词
  assistantContent?: string;
  toolCalls?: Array<{
    id: string;
    name: string;
    arguments: Record<string, unknown>;
  }>;
};

// 示例
const mockScripts: MockScript[] = [
  {
    whenUserIncludes: "风险",
    toolCalls: [
      {
        id: "call_1",
        name: "search_tools",
        arguments: { query: "风险" },
      },
    ],
  },
  {
    whenUserIncludes: "立项",
    toolCalls: [
      {
        id: "call_2",
        name: "recommend_tools",
        arguments: { question: "下周要立项还没授权", max: 3 },
      },
    ],
  },
];
```

**实现方式**：
- `MockProvider.complete()` 扫描最后一条 user 消息选中剧本
- 无匹配则返回纯文本：「请描述你的项目卡点」

### 3.2 阶段2+ Mock：推荐结果样例

```typescript
const mockRecommendResult = {
  reasoning: "立项未授权，适合先用项目章程明确授权与范围。",
  tools: [
    {
      slug: "project-charter",
      name: "项目章程 (Project Charter)",
      summary: "正式授权项目并任命项目经理的文档",
      processGroup: "启动",
      knowledgeArea: "范围",
    },
  ],
};
```

### 3.3 阶段3 Mock：章程草稿

```typescript
const mockCharterDraft = {
  projectName: "示例立项项目",
  sponsor: "待补充",
  projectManager: "张三",
  businessCase: "验证市场需求",
  highLevelScope: "MVP 功能集",
  milestones: "M1 需求 / M2 上线",
  budget: "待补充",
  risks: "资源不足",
  signature: "待补充",
};
```

---

## 4. 数据请求抽象层设计

### 4.1 设计目标

- 统一 `LLMClient` 接口；Mock / DeepSeek / OpenAI 可切换  
- 工具执行不依赖 Provider  
- 类型安全（Zod 校验 tool arguments）  

### 4.2 接口设计

```typescript
// src/agent/llm/client.ts
export type ToolCall = {
  id: string;
  name: string;
  arguments: string; // JSON string from model
};

export type LLMResponse = {
  content: string | null;
  tool_calls: ToolCall[];
};

export interface LLMClient {
  complete(input: {
    messages: ChatMessage[];
    tools: ToolDefinition[];
  }): Promise<LLMResponse>;
}

export function createLLMClient(): LLMClient {
  const provider = process.env.LLM_PROVIDER ?? "deepseek";
  if (provider === "mock") return new MockProvider();
  if (provider === "openai") return new OpenAICompatibleProvider("openai");
  return new OpenAICompatibleProvider("deepseek");
}
```

### 4.3 使用方式

```typescript
// loop.ts
const llm = createLLMClient();
const res = await llm.complete({ messages, tools: registry.toLLMTools() });
```

**切换**：

```bash
# 无 Key 开发
LLM_PROVIDER=mock npx tsx src/index.ts

# 真模型
DEEPSEEK_API_KEY=sk-... LLM_PROVIDER=deepseek npx tsx src/index.ts
```

---

## 5. 开发顺序建议

### 5.1 推荐开发顺序

**顺序1：Loop 先行（强烈推荐）**
1. 阶段1（Mock Loop + search/detail）  
2. 阶段2（真 LLM + 推荐）  
3. 阶段3（章程 + 导出）  
4. 阶段4（风险 + 拒绝路径）  
5. 阶段5（可选）  

**优势**：最早看到「像 Agent」；符合练手目标；导出最后接也不堵学习曲线。

**顺序2：导出先行** — 不推荐（易做成脚本而非 Agent）。

### 5.2 关键路径

1. 阶段1 → 阶段2（必须先有 Loop 才能接真模型）  
2. 阶段2 → 阶段3（推荐闭环后再起草，避免无交互目标）  
3. 阶段3 → 阶段4（复用导出管线）  

**可并行**：阶段5 的测试与阶段4 文档可部分并行。

### 5.3 风险提示

- **风险1：模型不调工具** — 强化 system prompt + tool description「何时用」；Mock 阶段先验证 Registry  
- **风险2：编造 slug** — `recommend_tools` 内强制校验  
- **风险3：密钥泄露** — `.gitignore` + 日志脱敏；Code review 检查导出内容  
- **风险4：范围回流** — 严格按 PRD 白名单，阶段4 不做第四个起草工具  

---

## 6. 附录

### 6.1 相关文档

- **PRD文档**：`项目文档/PM-Agent/PM-Agent-MVP-PRD.md`  
- **技术方案文档**：`项目文档/PM-Agent/PM-Agent-技术方案.md`  
- **技术调研**：`项目文档/PM-Agent/TDD/PM-Agent-技术选型调研-2026-07-14.md`

### 6.2 版本历史

| 版本 | 日期 | 说明 | 作者 |
|------|------|------|------|
| v1.0 | 2026-07-14 | 初始版本 | - |

---

**文档状态**：已确认（2026-07-14）  
**下一步**：可在新仓库 `pm-agent` 按阶段1开工
