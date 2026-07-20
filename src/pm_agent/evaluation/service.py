"""工具推荐评测的高层编排服务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pm_agent.evaluation.comparison import compare_reports
from pm_agent.evaluation.dataset import filter_cases, load_evaluation_cases
from pm_agent.evaluation.gates import evaluate_baseline_gate, evaluate_regression_gate
from pm_agent.evaluation.models import (
    ComparisonReport,
    EvaluationCase,
    EvaluationReport,
    GateResult,
)
from pm_agent.evaluation.reporting import load_report
from pm_agent.evaluation.runner import run_evaluation
from pm_agent.knowledge.catalog_ops import load_candidates, promote_candidate
from pm_agent.knowledge.repo import ToolsRepository


@dataclass(frozen=True)
class EvaluationBundle:
    """当前/候选报告、差异与门禁。"""

    cases: list[EvaluationCase]
    current: EvaluationReport
    candidate: EvaluationReport | None = None
    comparison: ComparisonReport | None = None
    gate: GateResult | None = None


def evaluate_current(
    tools_path: Path | str,
    cases_path: Path | str,
    *,
    family: str | None = None,
    tag: str | None = None,
) -> EvaluationBundle:
    cases = filter_cases(load_evaluation_cases(cases_path), family=family, tag=tag)
    repo = ToolsRepository.from_json_path(tools_path)
    return EvaluationBundle(cases=cases, current=run_evaluation(repo, cases))


def evaluate_candidate(
    tools_path: Path | str,
    candidates_path: Path | str,
    cases_path: Path | str,
    slug: str,
) -> EvaluationBundle:
    cases = load_evaluation_cases(cases_path)
    current_repo = ToolsRepository.from_json_path(tools_path)
    tool = promote_candidate(candidates_path, tools_path, slug, dry_run=True)
    candidate_repo = ToolsRepository(
        [*current_repo.all(), tool],
        boosts=current_repo.boost_rules,
        fallback_slugs=current_repo.fallback_slugs,
    )
    current = run_evaluation(current_repo, cases)
    candidate = run_evaluation(candidate_repo, cases)
    comparison = compare_reports(current, candidate)
    gate = evaluate_regression_gate(
        current,
        candidate,
        comparison,
        cases,
        candidate_slug=slug,
    )
    return EvaluationBundle(
        cases=cases,
        current=current,
        candidate=candidate,
        comparison=comparison,
        gate=gate,
    )


def check_current_against_baseline(
    tools_path: Path | str,
    cases_path: Path | str,
    baseline_path: Path | str,
) -> EvaluationBundle:
    bundle = evaluate_current(tools_path, cases_path)
    baseline = load_report(baseline_path)
    comparison = compare_reports(baseline, bundle.current)
    gate = evaluate_baseline_gate(baseline, bundle.current, bundle.cases)
    return EvaluationBundle(
        cases=bundle.cases,
        current=bundle.current,
        candidate=baseline,
        comparison=comparison,
        gate=gate,
    )


def build_evaluation_prompt(
    candidates_path: Path | str,
    tools_path: Path | str,
    slug: str,
    *,
    count: int = 12,
) -> str:
    """生成待人工审核的黄金语料草案提示词。"""
    candidate = next(
        (item for item in load_candidates(candidates_path) if item.slug == slug),
        None,
    )
    if candidate is None or candidate.tool is None:
        raise ValueError(f"候选池中不存在完整候选「{slug}」")
    repo = ToolsRepository.from_json_path(tools_path)
    adjacent = "\n".join(
        f"- {tool.slug}｜{tool.name}｜{tool.summary}"
        for tool in repo.all()
        if set(tool.use_cases) & set(candidate.proposed_use_cases)
    )
    title = f"请为候选工具 {slug} 生成 {count} 条黄金评测用例草案。"
    return f"""你是 pmbox 的工具推荐评测编辑器。{title}

候选名称：{candidate.name}
解决问题：{candidate.problem}
差异边界：{candidate.differentiation}
触发短语：{'；'.join(candidate.trigger_phrases)}

相邻正式工具：
{adjacent or '- 无'}

要求：
1. 仅输出合法 JSON 数组，不要 Markdown 围栏或解释。
2. 每条包含 id/query/context/family/case_type/critical/acceptable_top1/required_top3/
   forbidden_top3/requires_tools/tags。
3. 所有用例 requires_tools 必须包含 {slug}，使其只在候选预演或发布后启用。
4. 至少 8 条正例、2 条 boundary、2 条 negative；至少一半不能复制 trigger_phrases 原句。
5. 正例 required_top3 必须包含 {slug}；关键强场景 acceptable_top1 包含 {slug}。
6. negative 用例 forbidden_top3 包含 {slug}，用于验证误召回。
7. 明确覆盖与相邻工具的分流，不要把工具名直接写进 query。
8. AI 输出只是待人工审核草案，不得自动更新黄金集或基线。
"""
