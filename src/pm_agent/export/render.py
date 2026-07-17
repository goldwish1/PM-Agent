"""Markdown 模板渲染：项目章程 / 风险登记册 / 决策记录 / 决策矩阵。"""

from __future__ import annotations

from pm_agent.agent.session import (
    CharterDraft,
    DecisionDraft,
    DecisionMatrixDraft,
    RiskRegisterDraft,
)


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
*由 pmbox 导出；可直接在编辑器中修改后发给发起人。*
"""


def render_decision_markdown(draft: DecisionDraft) -> str:
    """渲染决策记录 Markdown。"""
    d = draft.model_dump()
    return f"""# 决策记录

## 基本信息

| 字段 | 内容 |
|------|------|
| 决策标题 | {d["decision_title"]} |
| 决策人 | {d["decision_maker"]} |
| 决策日期 | {d["decision_date"]} |
| 状态 | {d["status"]} |

## 背景与问题

{d["context"]}

## 备选方案

{d["options_considered"]}

## 最终决定

{d["decision"]}

## 决策依据

{d["rationale"]}

## 预期影响与后果

{d["consequences"]}

---
*由 pmbox 导出；决策过程可追溯，便于后续复盘与干系人同步。*
"""


def render_decision_matrix_markdown(draft: DecisionMatrixDraft) -> str:
    """渲染决策矩阵 Markdown（含打分表）。"""
    d = draft.model_dump()
    criteria = draft.criteria
    options = draft.options

    if not criteria or not options:
        table_body = "_（请先添加准则与方案后再导出完整打分表）_\n"
    else:
        header_cols = " | ".join(
            f"{opt.name or opt.option_id or f'O{i+1}'}" for i, opt in enumerate(options)
        )
        header = f"| 准则 / 权重 | {header_cols} |\n"
        sep_cols = " | ".join("---" for _ in options)
        separator = f"|-------------|{sep_cols}|\n"
        rows: list[str] = []
        for criterion in criteria:
            cid = criterion.criterion_id or ""
            label = f"{criterion.name} {criterion.weight}".strip()
            cells: list[str] = []
            for option in options:
                score = option.scores.get(cid, "—")
                if score == "—" and cid:
                    score = option.scores.get(criterion.name, "—")
                cells.append(str(score))
            rows.append(f"| {label} | " + " | ".join(cells) + " |")
        total_cells = [opt.weighted_total or "—" for opt in options]
        rows.append("| **加权总分** | " + " | ".join(total_cells) + " |")
        table_body = header + separator + "\n".join(rows) + "\n"

    return f"""# 决策矩阵

## 基本信息

| 字段 | 内容 |
|------|------|
| 标题 | {d["title"]} |
| 背景 | {d["context"]} |

## 打分表

{table_body}
## 推荐方案

{d["recommended_option"]}

## 推荐依据

{d["rationale"]}

---
*由 pmbox 导出；打分表可作为决策过程证据，结论可同步写入决策记录。*
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
*由 pmbox 导出；MVP 建议保留 1～3 条，细改可在本文件中直接编辑。*
"""
