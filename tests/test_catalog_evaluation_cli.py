"""工具库运营 CLI 的评测与发布门禁集成测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from conftest import sample_trigger_rules
from pm_agent.evaluation.models import CaseType, EvaluationCase
from pm_agent.knowledge.catalog_ops import CandidateStatus, QualityScore, ToolCandidate
from pm_agent.knowledge.repo import PmTool, ToolsRepository

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "manage_tool_catalog.py"
SPEC = importlib.util.spec_from_file_location("manage_tool_catalog", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
main = MODULE.main


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _formal_tool() -> PmTool:
    return PmTool(
        slug="formal-tool",
        name="正式工具",
        use_cases=["沟通与汇报"],
        summary="处理正式场景",
        trigger_phrases=["正式场景问题"],
        trigger_match_rules=sample_trigger_rules("正式场景问题"),
    )


def _candidate_tool() -> PmTool:
    return PmTool(
        slug="candidate-tool",
        name="候选工具",
        use_cases=["沟通与汇报"],
        summary="通过复述和澄清处理候选场景",
        description=(
            "何时用：需要理解复杂诉求时。何时别用：需要紧急处置时。"
            "常见坑：直接给建议；没有确认理解；忽略下一步。"
        ),
        steps=[
            "听取完整表达 → 产出信息摘要",
            "复述事实观点 → 产出确认句",
            "澄清含糊信息 → 产出待确认项",
            "识别关键顾虑 → 产出顾虑清单",
            "总结一致分歧 → 产出对齐清单",
        ],
        scenarios=[
            "对方说了很多但诉求不清楚",
            "团队成员感觉未被理解",
            "复杂信息需要先确认",
            "不应马上给建议",
            "需要澄清真实顾虑",
            "紧急事故应直接处置（反例）",
        ],
        trigger_phrases=["候选场景问题", "先理解再建议", "确认真实顾虑"],
        trigger_match_rules=sample_trigger_rules(
            "候选场景问题",
            "先理解再建议",
            "确认真实顾虑",
        ),
    )


def _approved_candidate() -> ToolCandidate:
    tool = _candidate_tool()
    return ToolCandidate(
        slug=tool.slug,
        name=tool.name,
        family="测试家族",
        problem="需要先理解复杂诉求，避免答非所问。",
        trigger_phrases=tool.trigger_phrases,
        differentiation="区别于正式工具：候选工具先澄清完整诉求。",
        proposed_use_cases=tool.use_cases,
        status=CandidateStatus.APPROVED,
        quality_score=QualityScore(
            trigger_clarity=2,
            actionability=2,
            output_clarity=2,
            boundary_clarity=1,
            recommendation_value=1,
        ),
        tool=tool,
    )


def _complete_candidate_cases() -> list[EvaluationCase]:
    cases = [
        EvaluationCase(
            id=f"candidate-positive-{index}",
            query=f"候选场景问题 {index}",
            family="测试家族",
            case_type=CaseType.BOUNDARY if index >= 8 else CaseType.TYPICAL,
            critical=index == 0,
            acceptable_top1=["candidate-tool"],
            required_top3=["candidate-tool"],
            requires_tools=["candidate-tool"],
        )
        for index in range(10)
    ]
    cases.extend(
        EvaluationCase(
            id=f"candidate-negative-{index}",
            query=f"完全无关的反例 {index}",
            family="测试家族",
            case_type=CaseType.NEGATIVE,
            forbidden_top3=["candidate-tool"],
            requires_tools=["candidate-tool"],
        )
        for index in range(2)
    )
    return cases


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    return (
        tmp_path / "tools.json",
        tmp_path / "candidates.json",
        tmp_path / "cases.json",
        tmp_path / "baseline.json",
        tmp_path / "reports",
    )


def _base_args(
    tools: Path,
    candidates: Path,
    cases: Path,
    baseline: Path,
    reports: Path,
) -> list[str]:
    return [
        "--tools",
        str(tools),
        "--candidates",
        str(candidates),
        "--cases",
        str(cases),
        "--baseline",
        str(baseline),
        "--evaluation-output",
        str(reports),
    ]


def test_cli_updates_baseline_then_evaluates_current(tmp_path: Path) -> None:
    tools, candidates, cases, baseline, reports = _paths(tmp_path)
    _write(tools, [_formal_tool().model_dump(mode="json", exclude_none=True)])
    _write(candidates, [])
    _write(
        cases,
        [
            EvaluationCase(
                id="formal-hit",
                query="正式场景问题",
                family="测试家族",
                case_type=CaseType.TYPICAL,
                acceptable_top1=["formal-tool"],
                required_top3=["formal-tool"],
            ).model_dump(mode="json")
        ],
    )
    args = _base_args(tools, candidates, cases, baseline, reports)

    assert main([*args, "update-baseline", "--yes"]) == 0
    assert baseline.is_file()
    assert (reports / "baseline.md").is_file()
    assert (reports / "baseline.html").is_file()
    assert main([*args, "evaluate"]) == 0
    assert (reports / "current.json").is_file()
    assert (reports / "current.md").is_file()


def test_cli_export_cases_and_baseline_views(tmp_path: Path) -> None:
    tools, candidates, cases, baseline, reports = _paths(tmp_path)
    _write(tools, [_formal_tool().model_dump(mode="json", exclude_none=True)])
    _write(candidates, [])
    _write(
        cases,
        [
            EvaluationCase(
                id="formal-hit",
                query="正式场景问题",
                family="测试家族",
                case_type=CaseType.TYPICAL,
                acceptable_top1=["formal-tool"],
                required_top3=["formal-tool"],
            ).model_dump(mode="json")
        ],
    )
    args = _base_args(tools, candidates, cases, baseline, reports)
    assert main([*args, "update-baseline", "--yes"]) == 0

    assert main([*args, "export-cases"]) == 0
    assert (reports / "cases.md").is_file()
    assert (reports / "cases.html").is_file()
    cases_html = (reports / "cases.html").read_text(encoding="utf-8")
    assert "formal-hit" in cases_html
    assert "正式场景问题" in cases_html

    assert main([*args, "export-baseline"]) == 0
    assert (reports / "baseline.md").is_file()
    assert (reports / "baseline.html").is_file()
    baseline_md = (reports / "baseline.md").read_text(encoding="utf-8")
    assert "formal-hit" in baseline_md


def test_cli_promote_blocks_candidate_without_coverage(tmp_path: Path) -> None:
    tools, candidates, cases, baseline, reports = _paths(tmp_path)
    formal = _formal_tool()
    candidate = _approved_candidate()
    _write(tools, [formal.model_dump(mode="json", exclude_none=True)])
    _write(candidates, [candidate.model_dump(mode="json", exclude_none=True)])
    _write(
        cases,
        [
            EvaluationCase(
                id="formal-hit",
                query="正式场景问题",
                family="测试家族",
                case_type=CaseType.TYPICAL,
                acceptable_top1=["formal-tool"],
                required_top3=["formal-tool"],
            ).model_dump(mode="json"),
            EvaluationCase(
                id="candidate-hit",
                query="候选场景问题",
                family="测试家族",
                case_type=CaseType.TYPICAL,
                critical=True,
                acceptable_top1=["candidate-tool"],
                required_top3=["candidate-tool"],
                requires_tools=["candidate-tool"],
            ).model_dump(mode="json"),
        ],
    )
    args = _base_args(tools, candidates, cases, baseline, reports)
    assert main([*args, "update-baseline", "--yes"]) == 0
    before = tools.read_text(encoding="utf-8")

    assert main([*args, "promote", "candidate-tool"]) == 2
    assert tools.read_text(encoding="utf-8") == before
    assert not ToolsRepository.from_json_path(tools).exists("candidate-tool")
    assert (reports / "promote-candidate-tool.md").is_file()


def test_cli_promote_dry_run_passes_without_writing_catalog(tmp_path: Path) -> None:
    tools, candidates, cases, baseline, reports = _paths(tmp_path)
    formal_case = EvaluationCase(
        id="formal-hit",
        query="正式场景问题",
        family="测试家族",
        case_type=CaseType.TYPICAL,
        acceptable_top1=["formal-tool"],
        required_top3=["formal-tool"],
    )
    _write(
        tools,
        [_formal_tool().model_dump(mode="json", exclude_none=True)],
    )
    _write(
        candidates,
        [_approved_candidate().model_dump(mode="json", exclude_none=True)],
    )
    _write(
        cases,
        [
            formal_case.model_dump(mode="json"),
            *[case.model_dump(mode="json") for case in _complete_candidate_cases()],
        ],
    )
    args = _base_args(tools, candidates, cases, baseline, reports)
    assert main([*args, "update-baseline", "--yes"]) == 0
    tools_before = tools.read_text(encoding="utf-8")
    candidates_before = candidates.read_text(encoding="utf-8")

    assert main([*args, "promote", "candidate-tool", "--dry-run"]) == 0
    assert tools.read_text(encoding="utf-8") == tools_before
    assert candidates.read_text(encoding="utf-8") == candidates_before
    assert (reports / "promote-candidate-tool.json").is_file()


def test_cli_retire_requires_yes_and_then_archives(tmp_path: Path) -> None:
    tools, candidates, cases, baseline, reports = _paths(tmp_path)
    archive = tmp_path / "tools.archive.json"
    _write(tools, [_formal_tool().model_dump(mode="json", exclude_none=True)])
    _write(candidates, [])
    _write(
        cases,
        [
            EvaluationCase(
                id="formal-hit",
                query="正式场景问题",
                family="测试家族",
                case_type=CaseType.TYPICAL,
                acceptable_top1=["formal-tool"],
                required_top3=["formal-tool"],
            ).model_dump(mode="json")
        ],
    )
    _write(archive, [])
    args = [
        *_base_args(tools, candidates, cases, baseline, reports),
        "--archive",
        str(archive),
    ]

    assert main([*args, "retire", "formal-tool"]) == 2
    assert ToolsRepository.from_json_path(tools).exists("formal-tool")

    assert main([*args, "retire", "formal-tool", "--yes"]) == 0
    assert not ToolsRepository.from_json_path(tools).exists("formal-tool")
    archived = json.loads(archive.read_text(encoding="utf-8"))
    assert archived[0]["slug"] == "formal-tool"
    remaining_cases = json.loads(cases.read_text(encoding="utf-8"))
    assert remaining_cases == []


def test_cli_discard_requires_yes(tmp_path: Path) -> None:
    tools, candidates, cases, baseline, reports = _paths(tmp_path)
    _write(tools, [_formal_tool().model_dump(mode="json", exclude_none=True)])
    _write(
        candidates,
        [_approved_candidate().model_dump(mode="json", exclude_none=True)],
    )
    _write(cases, [])
    args = _base_args(tools, candidates, cases, baseline, reports)

    assert main([*args, "discard", "candidate-tool"]) == 2
    assert len(json.loads(candidates.read_text(encoding="utf-8"))) == 1

    assert main([*args, "discard", "candidate-tool", "--yes"]) == 0
    assert json.loads(candidates.read_text(encoding="utf-8")) == []
