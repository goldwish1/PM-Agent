"""决策矩阵 Markdown 渲染。"""

from __future__ import annotations

from pm_agent.agent.session import DecisionMatrixDraft, MatrixCriterion, MatrixOption
from pm_agent.export.render import render_decision_matrix_markdown


def test_render_decision_matrix_contains_score_table() -> None:
    draft = DecisionMatrixDraft(
        title="自研 vs 外采",
        context="预算 50 万",
        criteria=[
            MatrixCriterion(criterion_id="C01", name="成本", weight="30%"),
            MatrixCriterion(criterion_id="C02", name="周期", weight="70%"),
        ],
        options=[
            MatrixOption(
                option_id="O01",
                name="自研",
                scores={"C01": "6", "C02": "5"},
                weighted_total="5.3",
            ),
            MatrixOption(
                option_id="O02",
                name="外采",
                scores={"C01": "8", "C02": "8"},
                weighted_total="8.0",
            ),
        ],
        recommended_option="外采",
        rationale="综合得分更高",
    )
    md = render_decision_matrix_markdown(draft)
    assert "# 决策矩阵" in md
    assert "准则 / 权重" in md
    assert "自研" in md
    assert "外采" in md
    assert "**加权总分**" in md
    assert "8.0" in md
    assert "综合得分更高" in md


def test_render_decision_matrix_empty_table_placeholder() -> None:
    md = render_decision_matrix_markdown(DecisionMatrixDraft(title="空矩阵"))
    assert "请先添加准则与方案" in md
