"""黄金用例与基线 Markdown/HTML 视图渲染。"""

from __future__ import annotations

from pathlib import Path

from pm_agent.evaluation.models import (
    CaseResult,
    CaseType,
    EvaluationCase,
    EvaluationReport,
    EvaluationSummary,
)
from pm_agent.evaluation.views import (
    render_baseline_html,
    render_baseline_markdown,
    render_cases_html,
    render_cases_markdown,
    write_baseline_views,
    write_cases_views,
)


def _case() -> EvaluationCase:
    return EvaluationCase(
        id="escape-001",
        query='反馈含 <script>alert("x")</script> 与 | 分隔',
        context="上下文 <b>粗体</b>",
        family="沟通与冲突",
        case_type=CaseType.TYPICAL,
        critical=True,
        acceptable_top1=["sbi-feedback"],
        required_top3=["sbi-feedback"],
        forbidden_top3=["conflict-resolution-process"],
        tags=["正式工具"],
    )


def _report() -> EvaluationReport:
    return EvaluationReport(
        dataset_digest="dataset-digest",
        tools_digest="tools-digest",
        summary=EvaluationSummary(
            total_cases=2,
            active_cases=2,
            skipped_cases=0,
            top1_cases=2,
            top1_passed=1,
            top1_accuracy=0.5,
            top3_cases=2,
            top3_passed=1,
            top3_recall=0.5,
            mrr_cases=2,
            mrr=0.5,
            forbidden_cases=1,
            forbidden_violations=1,
            forbidden_violation_rate=1.0,
            confusion={"sbi-feedback -> project-charter": 1},
        ),
        results=[
            CaseResult(
                case_id="escape-001",
                query="失败用例含 <tag>",
                family="沟通与冲突",
                case_type=CaseType.TYPICAL,
                critical=True,
                active=True,
                rankings=["project-charter"],
                top1_pass=False,
                top3_pass=False,
                reciprocal_rank=0.0,
                forbidden_hits=["conflict-resolution-process"],
            ),
            CaseResult(
                case_id="ok-001",
                query="通过用例",
                family="沟通与冲突",
                case_type=CaseType.TYPICAL,
                critical=False,
                active=True,
                rankings=["sbi-feedback"],
                top1_pass=True,
                top3_pass=True,
                reciprocal_rank=1.0,
            ),
        ],
    )


def test_render_cases_markdown_includes_fields_and_escapes_pipes() -> None:
    md = render_cases_markdown([_case()])
    assert "escape-001" in md
    assert "sbi-feedback" in md
    assert "\\| 分隔" in md
    assert "沟通与冲突" in md


def test_render_cases_html_escapes_markup_and_supports_filters() -> None:
    html = render_cases_html([_case()])
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert 'id="q"' in html
    assert 'id="family"' in html
    assert 'id="type"' in html
    assert "sbi-feedback" in html


def test_render_baseline_views_include_kpis_and_failures() -> None:
    report = _report()
    md = render_baseline_markdown(report)
    html = render_baseline_html(report)
    assert "50.0%" in md
    assert "sbi-feedback -> project-charter" in md
    assert "escape-001" in md
    assert "&lt;tag&gt;" in html
    assert 'id="only-fail"' in html
    assert "dataset-digest" in html


def test_write_views_creates_markdown_and_html(tmp_path: Path) -> None:
    md_path, html_path = write_cases_views([_case()], tmp_path / "out")
    assert md_path.name == "cases.md"
    assert html_path.name == "cases.html"
    assert md_path.is_file()
    assert html_path.is_file()

    baseline_md, baseline_html = write_baseline_views(_report(), tmp_path / "out")
    assert baseline_md.name == "baseline.md"
    assert baseline_html.name == "baseline.html"
    assert baseline_md.is_file()
    assert baseline_html.is_file()
