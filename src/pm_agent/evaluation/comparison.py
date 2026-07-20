"""比较两轮工具推荐评测结果。"""

from __future__ import annotations

from pm_agent.evaluation.models import (
    CaseChange,
    CaseChangeKind,
    ComparisonReport,
    EvaluationReport,
)


def compare_reports(
    before: EvaluationReport,
    after: EvaluationReport,
) -> ComparisonReport:
    """按 case id 比较两轮报告。"""
    if before.dataset_digest != after.dataset_digest:
        raise ValueError("评测集摘要不一致，不能直接比较")
    before_by_id = {result.case_id: result for result in before.results}
    after_by_id = {result.case_id: result for result in after.results}
    if set(before_by_id) != set(after_by_id):
        raise ValueError("两轮报告包含的 case id 不一致")

    changes: list[CaseChange] = []
    for case_id in sorted(before_by_id):
        old = before_by_id[case_id]
        new = after_by_id[case_id]
        kind = _change_kind(
            old.active,
            old.passed,
            old.rankings,
            new.active,
            new.passed,
            new.rankings,
        )
        changes.append(
            CaseChange(
                case_id=case_id,
                query=new.query,
                critical=new.critical,
                kind=kind,
                before_rankings=old.rankings,
                after_rankings=new.rankings,
                before_passed=old.passed,
                after_passed=new.passed,
                new_forbidden_hits=sorted(set(new.forbidden_hits) - set(old.forbidden_hits)),
            )
        )
    return ComparisonReport(before=before.summary, after=after.summary, changes=changes)


def _change_kind(
    before_active: bool,
    before_passed: bool,
    before_rankings: list[str],
    after_active: bool,
    after_passed: bool,
    after_rankings: list[str],
) -> CaseChangeKind:
    if not before_active and after_active:
        return CaseChangeKind.NEWLY_ACTIVATED
    if not before_active and not after_active:
        return CaseChangeKind.SKIPPED
    if before_active and not after_active:
        return CaseChangeKind.REGRESSED
    if not before_passed and after_passed:
        return CaseChangeKind.IMPROVED
    if before_passed and not after_passed:
        return CaseChangeKind.REGRESSED
    if before_rankings != after_rankings:
        return CaseChangeKind.CHANGED_NEUTRAL
    return CaseChangeKind.UNCHANGED
