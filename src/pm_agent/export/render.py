"""Markdown 模板渲染：项目章程 / 风险登记册。"""

from __future__ import annotations

from pm_agent.agent.session import CharterDraft, RiskRegisterDraft


def render_charter_markdown(draft: CharterDraft) -> str:
    """渲染项目章程 Markdown。"""
    d = draft.model_dump()
    return f"""# 项目章程

## 基本信息

| 字段 | 内容 |
|------|------|
| 项目名称 | {d["project_name"]} |
| 发起人 | {d["sponsor"]} |
| 项目经理 | {d["project_manager"]} |

## 商业论证

{d["business_case"]}

## 高层级范围

{d["high_level_scope"]}

## 主要里程碑

{d["milestones"]}

## 预算概览

{d["budget"]}

## 主要风险（高层）

{d["risks"]}

## 批准与签字

{d["signature"]}

---
*由 PM Agent 导出；可直接在编辑器中修改后发给发起人。*
"""


def render_risk_register_markdown(draft: RiskRegisterDraft) -> str:
    """渲染风险登记册 Markdown。"""
    if not draft.items:
        body = "_（暂无风险条目）_\n"
    else:
        rows = []
        for idx, item in enumerate(draft.items, start=1):
            rid = item.risk_id or f"R{idx:02d}"
            rows.append(
                f"| {rid} | {item.description} | {item.cause} | "
                f"{item.probability} | {item.impact} | {item.score} | "
                f"{item.response} | {item.owner} | {item.status} |"
            )
        body = (
            "| 风险ID | 描述 | 原因 | 概率 | 影响 | 评分 | 应对 | 责任人 | 状态 |\n"
            "|--------|------|------|------|------|------|------|--------|------|\n"
            + "\n".join(rows)
            + "\n"
        )

    return f"""# 风险登记册

## 条目一览

{body}
---
*由 PM Agent 导出；MVP 建议保留 1～3 条，细改可在本文件中直接编辑。*
"""
