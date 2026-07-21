"""工具推荐离线评测、比较与回归门禁。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import sample_trigger_rules
from pm_agent.evaluation.comparison import compare_reports
from pm_agent.evaluation.dataset import dataset_digest, load_evaluation_cases
from pm_agent.evaluation.gates import evaluate_baseline_gate, evaluate_regression_gate
from pm_agent.evaluation.models import CaseChangeKind, CaseType, EvaluationCase
from pm_agent.evaluation.runner import run_evaluation
from pm_agent.knowledge.repo import PmTool, ToolsRepository


def _tool(slug: str, trigger_phrases: list[str]) -> PmTool:
    return PmTool(
        slug=slug,
        name=slug,
        use_cases=["沟通与汇报"],
        summary=f"{slug} 摘要",
        trigger_phrases=trigger_phrases,
        trigger_match_rules=sample_trigger_rules(*trigger_phrases),
    )


def _case(
    case_id: str,
    query: str,
    *,
    expected: str | None = None,
    forbidden: str | None = None,
    requires: list[str] | None = None,
    case_type: CaseType = CaseType.TYPICAL,
    critical: bool = False,
) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        query=query,
        family="测试家族",
        case_type=case_type,
        critical=critical,
        acceptable_top1=[expected] if expected else [],
        required_top3=[expected] if expected else [],
        forbidden_top3=[forbidden] if forbidden else [],
        requires_tools=requires or [],
    )


def test_dataset_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    case = _case("duplicate", "请先理解诉求", expected="alpha")
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps([case.model_dump(mode="json")] * 2, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="重复 id"):
        load_evaluation_cases(path)


def test_dataset_digest_is_independent_of_case_order() -> None:
    first = _case("a", "第一条", expected="alpha")
    second = _case("b", "第二条", expected="beta")
    assert dataset_digest([first, second]) == dataset_digest([second, first])


def test_runner_calculates_metrics_and_skips_conditional_cases() -> None:
    repo = ToolsRepository(
        [
            _tool("alpha", ["请先完整理解诉求"]),
            _tool("beta", ["请给具体反馈"]),
        ]
    )
    cases = [
        _case("alpha-hit", "请先完整理解诉求", expected="alpha"),
        _case("beta-hit", "请给具体反馈", expected="beta"),
        _case("forbidden", "请先完整理解诉求", forbidden="alpha"),
        _case(
            "conditional",
            "候选专属问题",
            expected="candidate",
            requires=["candidate"],
        ),
    ]
    report = run_evaluation(repo, cases)

    assert report.summary.active_cases == 3
    assert report.summary.skipped_cases == 1
    assert report.summary.top1_accuracy == 1.0
    assert report.summary.top3_recall == 1.0
    assert report.summary.mrr == 1.0
    assert report.summary.forbidden_violation_rate == 1.0
    assert report.results[2].passed is False
    assert report.results[3].active is False


def test_comparison_marks_newly_activated_candidate_cases() -> None:
    case = _case(
        "candidate-hit",
        "这是候选的强场景",
        expected="candidate",
        requires=["candidate"],
    )
    before = run_evaluation(ToolsRepository([_tool("alpha", ["其他问题"])]), [case])
    after = run_evaluation(
        ToolsRepository(
            [
                _tool("alpha", ["其他问题"]),
                _tool("candidate", ["这是候选的强场景"]),
            ]
        ),
        [case],
    )

    comparison = compare_reports(before, after)
    assert comparison.changes[0].kind == CaseChangeKind.NEWLY_ACTIVATED
    assert comparison.changes[0].after_passed is True


def test_candidate_gate_accepts_complete_passing_coverage() -> None:
    positive_queries = [f"完整理解复杂诉求场景{i}" for i in range(10)]
    cases = [
        _case(
            f"candidate-positive-{index}",
            query,
            expected="candidate",
            requires=["candidate"],
            case_type=CaseType.BOUNDARY if index >= 8 else CaseType.TYPICAL,
            critical=index == 0,
        )
        for index, query in enumerate(positive_queries)
    ]
    cases.extend(
        [
            _case(
                f"candidate-negative-{index}",
                f"与候选无关的反例{index}",
                forbidden="candidate",
                requires=["candidate"],
                case_type=CaseType.NEGATIVE,
            )
            for index in range(2)
        ]
    )
    current_repo = ToolsRepository([_tool("alpha", ["其他问题"])] )
    candidate_repo = ToolsRepository(
        [
            _tool("alpha", ["其他问题"]),
            _tool("candidate", positive_queries),
        ]
    )
    current = run_evaluation(current_repo, cases)
    candidate = run_evaluation(candidate_repo, cases)
    comparison = compare_reports(current, candidate)

    gate = evaluate_regression_gate(
        current,
        candidate,
        comparison,
        cases,
        candidate_slug="candidate",
    )
    assert gate.passed is True
    assert not [issue for issue in gate.issues if issue.severity.value == "blocking"]


def test_candidate_gate_blocks_missing_coverage() -> None:
    cases = [
        _case(
            "only-one",
            "唯一候选场景",
            expected="candidate",
            requires=["candidate"],
            critical=True,
        )
    ]
    current = run_evaluation(ToolsRepository([_tool("alpha", ["其他问题"])]), cases)
    candidate = run_evaluation(
        ToolsRepository(
            [
                _tool("alpha", ["其他问题"]),
                _tool("candidate", ["不匹配的触发语"]),
            ]
        ),
        cases,
    )
    comparison = compare_reports(current, candidate)
    gate = evaluate_regression_gate(
        current,
        candidate,
        comparison,
        cases,
        candidate_slug="candidate",
    )

    assert gate.passed is False
    codes = {issue.code for issue in gate.issues}
    assert "candidate-cases" in codes
    assert "candidate-top3" in codes
    assert "candidate-critical" in codes


def test_baseline_gate_blocks_changed_dataset() -> None:
    repo = ToolsRepository([_tool("alpha", ["问题"])] )
    baseline_cases = [_case("old", "问题", expected="alpha")]
    current_cases = [_case("new", "问题", expected="alpha")]
    baseline = run_evaluation(repo, baseline_cases)
    current = run_evaluation(repo, current_cases)

    gate = evaluate_baseline_gate(baseline, current, current_cases)
    assert gate.passed is False
    assert gate.issues[0].code == "baseline-dataset-mismatch"


def test_top1_and_mrr_warnings_do_not_block_release() -> None:
    case = EvaluationCase(
        id="ranking-drop",
        query="共同问题",
        family="测试家族",
        case_type=CaseType.TYPICAL,
        acceptable_top1=["z-alpha"],
    )
    before = run_evaluation(
        ToolsRepository([_tool("z-alpha", ["共同问题"])]),
        [case],
    )
    after = run_evaluation(
        ToolsRepository(
            [
                _tool("z-alpha", ["共同问题"]),
                _tool("aaa-beta", ["共同问题"]),
            ]
        ),
        [case],
    )
    comparison = compare_reports(before, after)

    gate = evaluate_regression_gate(before, after, comparison, [case])
    assert gate.passed is True
    codes = {issue.code for issue in gate.issues}
    assert "top1-warning" in codes
    assert "mrr-warning" in codes


def test_removing_required_tool_blocks_top3_gate() -> None:
    case = _case(
        "removed-tool",
        "候选问题",
        expected="candidate",
        requires=["candidate"],
    )
    baseline = run_evaluation(
        ToolsRepository([_tool("candidate", ["候选问题"])]),
        [case],
    )
    current = run_evaluation(
        ToolsRepository([_tool("alpha", ["其他问题"])]),
        [case],
    )
    comparison = compare_reports(baseline, current)

    gate = evaluate_regression_gate(baseline, current, comparison, [case])
    assert gate.passed is False
    assert "top3-regression" in {issue.code for issue in gate.issues}
