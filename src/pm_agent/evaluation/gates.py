"""工具推荐评测的发布回归门禁。"""

from __future__ import annotations

from pm_agent.evaluation.models import (
    CaseChangeKind,
    CaseResult,
    CaseType,
    ComparisonReport,
    EvaluationCase,
    EvaluationReport,
    GateIssue,
    GateResult,
    GateSeverity,
)


def evaluate_regression_gate(
    before: EvaluationReport,
    after: EvaluationReport,
    comparison: ComparisonReport,
    cases: list[EvaluationCase],
    *,
    candidate_slug: str | None = None,
) -> GateResult:
    """检查关键退化、误召回与候选覆盖。"""
    issues: list[GateIssue] = []
    case_by_id = {case.id: case for case in cases}
    before_by_id = {result.case_id: result for result in before.results}
    after_by_id = {result.case_id: result for result in after.results}

    if before.dataset_digest != after.dataset_digest:
        issues.append(
            _issue("dataset-mismatch", "评测集摘要不一致", GateSeverity.BLOCKING)
        )
        return _result(issues)

    for change in comparison.changes:
        if change.critical and change.kind == CaseChangeKind.REGRESSED:
            issues.append(
                _issue(
                    "critical-regression",
                    f"关键用例退化：{change.query}",
                    GateSeverity.BLOCKING,
                    change.case_id,
                )
            )
        for slug in change.new_forbidden_hits:
            issues.append(
                _issue(
                    "new-forbidden-hit",
                    f"新增误召回 {slug}：{change.query}",
                    GateSeverity.BLOCKING,
                    change.case_id,
                )
            )
        if change.kind == CaseChangeKind.REGRESSED and not change.critical:
            issues.append(
                _issue(
                    "case-regression",
                    f"非关键用例退化：{change.query}",
                    GateSeverity.WARNING,
                    change.case_id,
                )
            )

    common_top3_before: list[bool] = []
    common_top3_after: list[bool] = []
    for case_id, old in before_by_id.items():
        new = after_by_id[case_id]
        case = case_by_id[case_id]
        if old.active and case.required_top3:
            common_top3_before.append(old.top3_pass is True)
            common_top3_after.append(new.active and new.top3_pass is True)
    if _rate(common_top3_after) < _rate(common_top3_before):
        issues.append(
            _issue(
                "top3-regression",
                "共同用例的 Top 3 命中率下降",
                GateSeverity.BLOCKING,
            )
        )

    if after.summary.top1_accuracy < before.summary.top1_accuracy:
        issues.append(
            _issue(
                "top1-warning",
                "整体 Top 1 命中率下降（第一版仅告警）",
                GateSeverity.WARNING,
            )
        )
    if after.summary.mrr < before.summary.mrr:
        issues.append(
            _issue(
                "mrr-warning",
                "整体 MRR 下降（第一版仅告警）",
                GateSeverity.WARNING,
            )
        )

    if candidate_slug:
        issues.extend(
            _candidate_coverage_issues(candidate_slug, cases, after_by_id)
        )
    return _result(issues)


def evaluate_baseline_gate(
    baseline: EvaluationReport,
    current: EvaluationReport,
    cases: list[EvaluationCase],
) -> GateResult:
    """当前正式库相对受控基线的门禁。"""
    if baseline.dataset_digest != current.dataset_digest:
        return GateResult(
            passed=False,
            issues=[
                _issue(
                    "baseline-dataset-mismatch",
                    "黄金评测集已变化，请审核并显式更新基线",
                    GateSeverity.BLOCKING,
                )
            ],
        )
    from pm_agent.evaluation.comparison import compare_reports

    comparison = compare_reports(baseline, current)
    return evaluate_regression_gate(baseline, current, comparison, cases)


def _candidate_coverage_issues(
    slug: str,
    cases: list[EvaluationCase],
    results: dict[str, CaseResult],
) -> list[GateIssue]:
    candidate_cases = [
        case
        for case in cases
        if slug in case.requires_tools
        and (slug in case.relevant_tools or slug in case.forbidden_top3)
    ]
    positive = [
        case
        for case in candidate_cases
        if case.case_type != CaseType.NEGATIVE and slug in case.relevant_tools
    ]
    boundary = [case for case in candidate_cases if case.case_type == CaseType.BOUNDARY]
    negative = [case for case in candidate_cases if case.case_type == CaseType.NEGATIVE]
    issues: list[GateIssue] = []

    thresholds = [
        (len(candidate_cases) >= 12, "candidate-cases", "候选评测用例少于 12 条"),
        (len(positive) >= 8, "candidate-positive", "候选正例少于 8 条"),
        (len(boundary) >= 2, "candidate-boundary", "候选边界用例少于 2 条"),
        (len(negative) >= 2, "candidate-negative", "候选反例少于 2 条"),
    ]
    for passed, code, message in thresholds:
        if not passed:
            issues.append(_issue(code, message, GateSeverity.BLOCKING))

    active_positive = [results[case.id] for case in positive]
    top3_hits = sum(slug in result.rankings for result in active_positive)
    if not active_positive or top3_hits / len(active_positive) < 0.8:
        issues.append(
            _issue(
                "candidate-top3",
                "候选正例 Top 3 命中率低于 80%",
                GateSeverity.BLOCKING,
            )
        )
    critical_failures = [
        result
        for case in candidate_cases
        if case.critical
        for result in [results[case.id]]
        if not result.passed
    ]
    for result in critical_failures:
        issues.append(
            _issue(
                "candidate-critical",
                f"候选关键用例未通过：{result.query}",
                GateSeverity.BLOCKING,
                result.case_id,
            )
        )
    return issues


def _rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _issue(
    code: str,
    message: str,
    severity: GateSeverity,
    case_id: str | None = None,
) -> GateIssue:
    return GateIssue(code=code, message=message, severity=severity, case_id=case_id)


def _result(issues: list[GateIssue]) -> GateResult:
    return GateResult(
        passed=not any(issue.severity == GateSeverity.BLOCKING for issue in issues),
        issues=issues,
    )
