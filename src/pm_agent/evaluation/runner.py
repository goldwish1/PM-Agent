"""运行确定性的工具推荐离线评测并计算指标。"""

from __future__ import annotations

from collections import Counter

from pm_agent.evaluation.dataset import dataset_digest, tools_digest, validate_case_tools
from pm_agent.evaluation.models import (
    CaseResult,
    EvaluationCase,
    EvaluationReport,
    EvaluationSummary,
)
from pm_agent.knowledge.repo import ToolsRepository


def run_evaluation(
    repo: ToolsRepository,
    cases: list[EvaluationCase],
) -> EvaluationReport:
    """对仓库运行黄金用例，返回稳定报告。"""
    validate_case_tools(cases, repo)
    known = {tool.slug for tool in repo.all()}
    results = [_evaluate_case(repo, case, known) for case in cases]
    return EvaluationReport(
        dataset_digest=dataset_digest(cases),
        tools_digest=tools_digest(repo),
        summary=_summarize(results, cases),
        results=results,
    )


def _evaluate_case(
    repo: ToolsRepository,
    case: EvaluationCase,
    known: set[str],
) -> CaseResult:
    missing_requirements = sorted(set(case.requires_tools) - known)
    if missing_requirements:
        return CaseResult(
            case_id=case.id,
            query=case.query,
            family=case.family,
            case_type=case.case_type,
            critical=case.critical,
            active=False,
            skipped_reason="缺少条件工具：" + ", ".join(missing_requirements),
        )

    rankings = [
        tool.slug
        for tool, _ in repo.recommend_by_question(
            case.query,
            context=case.context,
            limit=3,
        )
    ]
    top1_pass = None
    if case.acceptable_top1:
        top1_pass = bool(rankings and rankings[0] in case.acceptable_top1)
    top3_pass = None
    if case.required_top3:
        top3_pass = set(case.required_top3) <= set(rankings)

    reciprocal_rank = None
    if case.relevant_tools:
        rank = next(
            (index for index, slug in enumerate(rankings, start=1) if slug in case.relevant_tools),
            None,
        )
        reciprocal_rank = 1 / rank if rank is not None else 0.0

    return CaseResult(
        case_id=case.id,
        query=case.query,
        family=case.family,
        case_type=case.case_type,
        critical=case.critical,
        active=True,
        rankings=rankings,
        top1_pass=top1_pass,
        top3_pass=top3_pass,
        reciprocal_rank=reciprocal_rank,
        forbidden_hits=[slug for slug in rankings if slug in case.forbidden_top3],
    )


def _summarize(
    results: list[CaseResult],
    cases: list[EvaluationCase],
) -> EvaluationSummary:
    active = [result for result in results if result.active]
    top1 = [result for result in active if result.top1_pass is not None]
    top3 = [result for result in active if result.top3_pass is not None]
    reciprocal = [
        result.reciprocal_rank
        for result in active
        if result.reciprocal_rank is not None
    ]
    forbidden = [
        result
        for result, case in zip(results, cases, strict=True)
        if result.active and case.forbidden_top3
    ]
    confusion = Counter()
    case_by_id = {case.id: case for case in cases}
    for result in top1:
        if result.top1_pass or not result.rankings:
            continue
        expected = "|".join(case_by_id[result.case_id].acceptable_top1)
        confusion[f"{expected} -> {result.rankings[0]}"] += 1

    return EvaluationSummary(
        total_cases=len(results),
        active_cases=len(active),
        skipped_cases=len(results) - len(active),
        top1_cases=len(top1),
        top1_passed=sum(result.top1_pass is True for result in top1),
        top1_accuracy=_ratio(sum(result.top1_pass is True for result in top1), len(top1)),
        top3_cases=len(top3),
        top3_passed=sum(result.top3_pass is True for result in top3),
        top3_recall=_ratio(sum(result.top3_pass is True for result in top3), len(top3)),
        mrr_cases=len(reciprocal),
        mrr=_average(reciprocal),
        forbidden_cases=len(forbidden),
        forbidden_violations=sum(bool(result.forbidden_hits) for result in forbidden),
        forbidden_violation_rate=_ratio(
            sum(bool(result.forbidden_hits) for result in forbidden),
            len(forbidden),
        ),
        confusion=dict(sorted(confusion.items())),
    )


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0
