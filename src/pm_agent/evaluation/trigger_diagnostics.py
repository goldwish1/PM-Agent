"""触发规则诊断：从评测失败案例反推触发关键词。"""

from __future__ import annotations

from collections import Counter

from pm_agent.evaluation.models import CaseType, EvaluationCase, EvaluationReport
from pm_agent.knowledge.matching import tokenize_query_for_search
from pm_agent.knowledge.repo import PmTool


def _failed_positive_cases(
    cases: list[EvaluationCase],
    report: EvaluationReport,
    tool_slug: str,
) -> list[EvaluationCase]:
    by_id = {r.case_id: r for r in report.results}
    failed: list[EvaluationCase] = []
    for case in cases:
        # 仅看“正例/边界正例”：该工具应该出现在 Top3。
        if case.case_type == CaseType.NEGATIVE:
            continue
        if tool_slug not in case.relevant_tools:
            continue
        result = by_id.get(case.id)
        if not result or not result.active:
            continue
        if tool_slug not in result.rankings:
            failed.append(case)
    return failed


def suggest_any_of_keywords(
    *,
    tool: PmTool,
    cases: list[EvaluationCase],
    report: EvaluationReport,
    tool_slug: str,
    max_suggestions: int = 10,
) -> list[str]:
    """从失败案例反推候选 any_of 关键词（不保证必过，只是建议）。"""

    failed_cases = _failed_positive_cases(cases, report, tool_slug)
    if not failed_cases:
        return []

    existing = {
        kw
        for rule in tool.trigger_match_rules
        for kw in (*rule.all_of, *rule.any_of)
        if kw.strip()
    }

    counts: Counter[str] = Counter()
    for case in failed_cases:
        tokens = tokenize_query_for_search(
            f"{case.query} {case.context}",
            max_tokens=40,
        )
        for token in tokens:
            token = token.strip()
            if not token or token in existing:
                continue
            counts[token] += 1

    # 计数优先，其次按长度更长的优先（更精确），最后按字典序保证确定性。
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    return [kw for kw, _ in ranked[:max_suggestions]]

