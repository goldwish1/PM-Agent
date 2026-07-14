# [CLAUDE.md](http://CLAUDE.md)

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目目的

PM Agent 是一个面向个人项目经理的 CLI 工具。用户可通过终端多轮对话：

- 根据工作卡点获得 PMBOK 工具推荐（如项目章程、风险登记册等，约 39 个工具）
- 自动起草「项目章程」和「风险登记册」Markdown 文档并导出

技术栈：TypeScript + Node.js `readline/promises` + DeepSeek API（OpenAI SDK 兼容）

## 项目状态

当前处于 **设计/规划阶段**，尚未开始编码。所有需求、技术方案、开发计划已在 `doc/` 目录中完成。

## 关键文档

- `doc/PM-Agent-MVP-PRD.md` — 产品需求文档
- `doc/PM-Agent-技术方案.md` — 技术架构方案（单体进程、Agent Loop、Tool Registry）
- `doc/PM-Agent-技术选型调研-2026-07-14.md` — 技术选型调研
- `doc/PM-Agent-开发计划.md` — 分阶段开发计划（4 个阶段）
- `doc/需求孵化.md` — 需求孵化记录
- `doc/agent_learn.md` — **功能变更与问题解决记录**（见下方说明）



## 变更记录要求

每当新增功能或解决问题时，必须在 `doc/agent_learn.md` 中做简要记录：

**新增功能** 需记录：

- 新增加了什么功能
- 原因
- 一句话方案

**解决问题** 需记录：

- 遇到的问题
- 原因
- 解决方案



## 目录结构

```
.
├── CLAUDE.md
├── doc/                     # 设计文档
│   ├── PM-Agent-MVP-PRD.md
│   ├── PM-Agent-技术方案.md
│   ├── PM-Agent-技术选型调研-2026-07-14.md
│   ├── PM-Agent-开发计划.md
│   ├── 需求孵化.md
│   └── agent_learn.md       # 变更记录
├── data/                    # 工具库数据（tools.json）
├── src/                     # 源代码
│   ├── index.ts             # 入口
│   ├── cli/                 # readline I/O
│   ├── agent/               # Agent Loop
│   ├── llm/                 # LLM Client（接口 + DeepSeek/Mock Provider）
│   ├── tools/               # Tool Registry + 工具实现
│   └── types/               # 类型定义
└── output/                  # 导出产物
```



## 开发计划（4 阶段）


| 阶段  | 内容             | 可演示                        |
| --- | -------------- | -------------------------- |
| 1   | 工程骨架 + Mock 循环 | `npx tsx src/index.ts` 可交互 |
| 2   | 真实 LLM + 推荐闭环  | 卡点 → 推荐 1～3 个工具            |
| 3   | 项目章程起草 + 导出    | 多轮收集 → 预览 → 导出 Markdown    |
| 4   | 风险登记册 + 边界处理   | 同理起草 + 异常场景                |




## 开发命令

```bash
# 启动开发（使用 Mock Provider）
LLM_PROVIDER=mock npx tsx src/index.ts

# 启动开发（使用 DeepSeek）
LLM_PROVIDER=deepseek npx tsx src/index.ts
```



## 架构要点

- **单体进程**：CLI 读输入 → Agent Loop 调 LLM → 执行本地 Tool → 更新会话状态/写文件 → 打印回复
- **Tool Registry**：可增删工具，支持 `search_tools`、`get_tool_detail`、`recommend_tools`、`draft_document` 等
- **LLM 抽象**：`LLMClient` 接口 + 可切换 Provider（Mock / DeepSeek / OpenAI）
- **Mock 先行**：先假 LLM/真工具，再接真实模型
- **无外部依赖**：无数据库、无 Web 框架、无 HTTP 后端



# 其他要求

- 这是我的个人学习项目，我希望从0到1了解熟悉agent的开发过程，因此文件目录需要高度结构化，符合AI agent的最佳实践

