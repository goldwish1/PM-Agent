#!/usr/bin/env python3
"""PM 工具库运营 CLI：生成提示词、导入、评审、校验与发布候选。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from pm_agent.evaluation.comparison import compare_reports
from pm_agent.evaluation.dataset import load_evaluation_cases
from pm_agent.evaluation.gates import evaluate_baseline_gate
from pm_agent.evaluation.models import EvaluationReport, GateResult, GateSeverity
from pm_agent.evaluation.reporting import (
    load_report,
    write_comparison_bundle,
    write_report_json,
)
from pm_agent.evaluation.service import (
    build_evaluation_prompt,
    evaluate_candidate,
    evaluate_current,
)
from pm_agent.evaluation.trigger_diagnostics import suggest_any_of_keywords
from pm_agent.evaluation.views import write_baseline_views, write_cases_views
from pm_agent.knowledge.catalog_ops import (
    CandidateStatus,
    MigrationStatusReport,
    QualityScore,
    RetireResult,
    build_generation_prompt,
    discard_candidate,
    ingest_candidates,
    load_candidates,
    migrate_trigger_rules,
    migration_status,
    promote_candidate,
    retire_tool,
    review_candidate,
    validate_catalog,
    validate_formal_tools,
)
from pm_agent.knowledge.repo import ToolsRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS = REPO_ROOT / "data" / "tools.json"
DEFAULT_ARCHIVE = REPO_ROOT / "data" / "tools.archive.json"
DEFAULT_CANDIDATES = REPO_ROOT / "data" / "tool_candidates.json"
DEFAULT_CASES = REPO_ROOT / "data" / "evaluation" / "tool_recommendation_cases.json"
DEFAULT_BASELINE = REPO_ROOT / "data" / "evaluation" / "baseline.json"
DEFAULT_EVALUATION_OUTPUT = REPO_ROOT / "output" / "evaluation"


def _score(value: str) -> QualityScore:
    try:
        values = [int(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("评分必须是 5 个逗号分隔的整数") from exc
    if len(values) != 5:
        raise argparse.ArgumentTypeError("评分必须包含 5 项，例如 2,2,2,1,2")
    try:
        return QualityScore(
            trigger_clarity=values[0],
            actionability=values[1],
            output_clarity=values[2],
            boundary_clarity=values[3],
            recommendation_value=values[4],
        )
    except ValidationError as exc:
        raise argparse.ArgumentTypeError("每项评分必须在 0～2 之间") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运营 pmbox 的 PM 工具候选池")
    parser.add_argument("--tools", type=Path, default=DEFAULT_TOOLS)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--evaluation-output",
        type=Path,
        default=DEFAULT_EVALUATION_OUTPUT,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="浏览候选工具")
    list_parser.add_argument("--status", choices=[item.value for item in CandidateStatus])

    commands.add_parser("validate", help="校验候选池与正式库")

    prompt_parser = commands.add_parser("prompt", help="生成带仓库上下文的 AI 提示词")
    prompt_parser.add_argument("--family", required=True, help="本轮工具家族，例如沟通与冲突")
    prompt_parser.add_argument("--count", type=int, default=6)
    prompt_parser.add_argument("--output", type=Path)

    ingest_parser = commands.add_parser("ingest", help="导入 AI 生成的候选 JSON")
    ingest_parser.add_argument("file", type=Path)

    review_parser = commands.add_parser("review", help="评分并评审候选")
    review_parser.add_argument("slug")
    review_parser.add_argument("--scores", required=True, type=_score)
    review_parser.add_argument("--approve", action="store_true")
    review_parser.add_argument("--note", default="")

    promote_parser = commands.add_parser("promote", help="发布已批准候选")
    promote_parser.add_argument("slug")
    promote_parser.add_argument("--dry-run", action="store_true")

    retire_parser = commands.add_parser("retire", help="从正式库下架并归档")
    retire_parser.add_argument("slug")
    retire_parser.add_argument("--dry-run", action="store_true")
    retire_parser.add_argument(
        "--yes",
        action="store_true",
        help="确认写盘；未指定时只打印计划",
    )
    retire_parser.add_argument(
        "--force",
        action="store_true",
        help="绕过 draftable / 推荐启发式配置 slug 门禁",
    )
    retire_parser.add_argument(
        "--keep-cases",
        action="store_true",
        help="不下架联动清理黄金用例（仅调试）",
    )
    retire_parser.add_argument("--note", default="")

    discard_parser = commands.add_parser("discard", help="从候选池移除条目")
    discard_parser.add_argument("slug")
    discard_parser.add_argument("--dry-run", action="store_true")
    discard_parser.add_argument(
        "--yes",
        action="store_true",
        help="确认写盘；未指定时只打印计划",
    )

    evaluate_parser = commands.add_parser("evaluate", help="评测当前正式工具库")
    evaluate_parser.add_argument("--family")
    evaluate_parser.add_argument("--tag")

    candidate_parser = commands.add_parser(
        "evaluate-candidate",
        help="对已批准候选运行正式库/候选库 A/B 评测",
    )
    candidate_parser.add_argument("slug")

    baseline_parser = commands.add_parser(
        "update-baseline",
        help="审核黄金集后显式更新正式库受控基线",
    )
    baseline_parser.add_argument(
        "--yes",
        action="store_true",
        help="确认覆盖基线；未指定时只显示当前指标",
    )

    eval_prompt_parser = commands.add_parser(
        "eval-prompt",
        help="为候选生成待人工审核的黄金用例提示词",
    )
    eval_prompt_parser.add_argument("slug")
    eval_prompt_parser.add_argument("--count", type=int, default=12)
    eval_prompt_parser.add_argument("--output", type=Path)

    suggest_parser = commands.add_parser(
        "suggest-triggers",
        help="根据评测失败案例反推触发关键词（建议补到 trigger_match_rules 的 any_of）",
    )
    suggest_parser.add_argument("slug")
    suggest_parser.add_argument(
        "--formal",
        action="store_true",
        help="针对正式库工具生成建议（不使用候选 A/B）",
    )
    suggest_parser.add_argument("--max", type=int, default=10)
    suggest_parser.add_argument("--output", type=Path)

    commands.add_parser(
        "migration-status",
        help="列出尚未写入显式 trigger_match_rules 的正式库/候选 slug",
    )

    migrate_parser = commands.add_parser(
        "migrate-rules",
        help="为正式库与候选池写入 trigger_match_rules（默认跳过已有规则）",
    )
    migrate_parser.add_argument("--dry-run", action="store_true")
    migrate_parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已有 trigger_match_rules",
    )
    migrate_parser.add_argument(
        "--yes",
        action="store_true",
        help="确认写盘；未指定时仅打印计划",
    )
    migrate_parser.add_argument(
        "slugs",
        nargs="*",
        help="可选：仅迁移指定 slug",
    )

    commands.add_parser(
        "export-cases",
        help="导出黄金用例的 Markdown/HTML 可读视图",
    )
    commands.add_parser(
        "export-baseline",
        help="导出正式基线的 Markdown/HTML 可读视图",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except (FileNotFoundError, ValueError, ValidationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    if args.command == "list":
        candidates = load_candidates(args.candidates)
        if args.status:
            candidates = [item for item in candidates if item.status.value == args.status]
        for item in candidates:
            score = item.quality_score.total if item.quality_score else "-"
            print(f"{item.slug}\t{item.status.value}\t{score}/10\t{item.family}\t{item.name}")
        print(f"共 {len(candidates)} 个候选")
        return 0

    if args.command == "validate":
        repo = ToolsRepository.from_json_path(args.tools)
        candidates = load_candidates(args.candidates)
        issues = validate_catalog(candidates, repo)
        formal_issues = validate_formal_tools(args.tools)
        if formal_issues:
            issues = {**issues, **formal_issues}
        if not issues:
            print(f"ok: 正式工具 {len(repo)} 个，候选 {len(candidates)} 个")
            return 0
        for slug, messages in issues.items():
            print(f"{slug}:", file=sys.stderr)
            for message in messages:
                print(f"  - {message}", file=sys.stderr)
        return 1

    if args.command == "migration-status":
        report = migration_status(args.tools, args.candidates)
        print(
            f"正式库：{report.formal_migrated}/{report.formal_total} 已迁移"
            f"（待迁移 {len(report.formal_pending)}）"
        )
        if report.formal_pending:
            for slug in report.formal_pending:
                print(f"  - {slug}")
        print(
            f"候选池：{report.candidate_migrated}/{report.candidate_total} 已迁移"
            f"（待迁移 {len(report.candidate_pending)}）"
        )
        if report.candidate_pending:
            for slug in report.candidate_pending:
                print(f"  - {slug}")
        return 0 if report.complete else 2

    if args.command == "migrate-rules":
        before = migration_status(args.tools, args.candidates)
        _print_migration_plan(before, slugs=args.slugs or None)
        if args.dry_run:
            migrate_trigger_rules(
                args.tools,
                args.candidates,
                dry_run=True,
                slugs=args.slugs or None,
                force=args.force,
            )
            print("dry-run: 未写盘")
            return 0
        if not args.yes:
            print("未写盘；确认后加 --yes")
            return 2
        after = migrate_trigger_rules(
            args.tools,
            args.candidates,
            dry_run=False,
            slugs=args.slugs or None,
            force=args.force,
        )
        print(
            f"ok: 正式库 {after.formal_migrated}/{after.formal_total}；"
            f"候选池 {after.candidate_migrated}/{after.candidate_total}"
        )
        return 0 if after.complete else 2

    if args.command == "prompt":
        if not 1 <= args.count <= 12:
            raise ValueError("count 必须在 1～12 之间")
        text = build_generation_prompt(
            family=args.family,
            count=args.count,
            repo=ToolsRepository.from_json_path(args.tools),
            candidates=load_candidates(args.candidates),
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"已写入提示词：{args.output}")
        else:
            print(text)
        return 0

    if args.command == "ingest":
        merged = ingest_candidates(args.candidates, args.file)
        print(f"ok: 候选池现有 {len(merged)} 个工具")
        return 0

    if args.command == "review":
        candidate = review_candidate(
            args.candidates,
            args.tools,
            args.slug,
            args.scores,
            approve=args.approve,
            note=args.note,
        )
        print(
            f"ok: {candidate.slug} → {candidate.status.value} ({candidate.quality_score.total}/10)"
        )
        return 0

    if args.command == "evaluate":
        bundle = evaluate_current(
            args.tools,
            args.cases,
            family=args.family,
            tag=args.tag,
        )
        gate = None
        comparison = None
        if not args.family and not args.tag and args.baseline.is_file():
            baseline = load_report(args.baseline)
            gate = evaluate_baseline_gate(baseline, bundle.current, bundle.cases)
            if baseline.dataset_digest == bundle.current.dataset_digest:
                comparison = compare_reports(baseline, bundle.current)
        paths = write_comparison_bundle(
            args.evaluation_output,
            name="current",
            current=bundle.current,
            comparison=comparison,
            gate=gate,
        )
        _print_summary(bundle.current)
        print(f"报告：{paths[1]}")
        if gate:
            _print_gate(gate)
            return 0 if gate.passed else 2
        return 0

    if args.command == "evaluate-candidate":
        bundle = evaluate_candidate(
            args.tools,
            args.candidates,
            args.cases,
            args.slug,
        )
        paths = write_comparison_bundle(
            args.evaluation_output,
            name=f"candidate-{args.slug}",
            current=bundle.current,
            candidate=bundle.candidate,
            comparison=bundle.comparison,
            gate=bundle.gate,
        )
        print("当前正式库：")
        _print_summary(bundle.current)
        print("加入候选后：")
        _print_summary(bundle.candidate)
        print(f"报告：{paths[1]}")
        _print_gate(bundle.gate)
        return 0 if bundle.gate and bundle.gate.passed else 2

    if args.command == "suggest-triggers":
        if args.max < 1:
            raise ValueError("--max 必须是正整数")

        if args.formal:
            bundle = evaluate_current(args.tools, args.cases)
            repo = ToolsRepository.from_json_path(args.tools)
            tool = repo.get_by_slug(args.slug)
            if tool is None:
                raise ValueError(f"正式库不存在工具 slug：{args.slug}")
            suggestions = suggest_any_of_keywords(
                tool=tool,
                cases=bundle.cases,
                report=bundle.current,
                tool_slug=args.slug,
                max_suggestions=args.max,
            )
        else:
            bundle = evaluate_candidate(
                args.tools,
                args.candidates,
                args.cases,
                args.slug,
            )
            tool = promote_candidate(
                args.candidates,
                args.tools,
                args.slug,
                dry_run=True,
            )
            suggestions = suggest_any_of_keywords(
                tool=tool,
                cases=bundle.cases,
                report=bundle.candidate,
                tool_slug=args.slug,
                max_suggestions=args.max,
            )

        payload = {
            "slug": args.slug,
            "formal": bool(args.formal),
            "max_suggestions": args.max,
            "suggestions": suggestions,
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"已写入建议：{args.output}")

        if suggestions:
            print("建议关键词（补充到 any_of）：")
            for kw in suggestions:
                print(f"- {kw}")
        else:
            print("未发现需要补词的失败用例（或关键词已全部覆盖）。")
        return 0

    if args.command == "update-baseline":
        bundle = evaluate_current(args.tools, args.cases)
        _print_summary(bundle.current)
        if not args.yes:
            print("未写入基线；审核黄金集后加 --yes 确认")
            return 2
        write_report_json(args.baseline, bundle.current)
        view_paths = write_baseline_views(bundle.current, args.evaluation_output)
        print(f"ok: 基线已更新：{args.baseline}")
        print(f"基线视图：{view_paths[0]} ；{view_paths[1]}")
        return 0

    if args.command == "export-cases":
        cases = load_evaluation_cases(args.cases)
        paths = write_cases_views(cases, args.evaluation_output)
        print(f"用例视图：{paths[0]} ；{paths[1]}")
        return 0

    if args.command == "export-baseline":
        report = load_report(args.baseline)
        paths = write_baseline_views(report, args.evaluation_output)
        print(f"基线视图：{paths[0]} ；{paths[1]}")
        return 0

    if args.command == "eval-prompt":
        if not 12 <= args.count <= 30:
            raise ValueError("count 必须在 12～30 之间")
        text = build_evaluation_prompt(
            args.candidates,
            args.tools,
            args.slug,
            count=args.count,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"已写入评测提示词：{args.output}")
        else:
            print(text)
        return 0

    if args.command == "promote":
        current_bundle = evaluate_current(args.tools, args.cases)
        baseline = load_report(args.baseline)
        baseline_gate = evaluate_baseline_gate(
            baseline,
            current_bundle.current,
            current_bundle.cases,
        )
        candidate_bundle = evaluate_candidate(
            args.tools,
            args.candidates,
            args.cases,
            args.slug,
        )
        combined_gate = _combine_gates(baseline_gate, candidate_bundle.gate)
        paths = write_comparison_bundle(
            args.evaluation_output,
            name=f"promote-{args.slug}",
            current=candidate_bundle.current,
            candidate=candidate_bundle.candidate,
            comparison=candidate_bundle.comparison,
            gate=combined_gate,
        )
        _print_gate(combined_gate)
        print(f"评测报告：{paths[1]}")
        if not combined_gate.passed:
            print("error: 推荐命中门禁未通过，禁止发布", file=sys.stderr)
            return 2
        tool = promote_candidate(
            args.candidates,
            args.tools,
            args.slug,
            dry_run=args.dry_run,
        )
        action = "校验通过（未写盘）" if args.dry_run else "已发布"
        print(f"ok: {tool.slug}「{tool.name}」{action}")
        return 0

    if args.command == "retire":
        preview = retire_tool(
            args.tools,
            args.archive,
            args.slug,
            candidates_path=args.candidates,
            cases_path=args.cases,
            dry_run=True,
            note=args.note,
            force=args.force,
            keep_cases=args.keep_cases,
        )
        _print_retire_plan(preview, keep_cases=args.keep_cases)
        if args.dry_run:
            print("dry-run: 未写盘")
            return 0
        if not args.yes:
            print("未写盘；确认后加 --yes")
            return 2
        result = retire_tool(
            args.tools,
            args.archive,
            args.slug,
            candidates_path=args.candidates,
            cases_path=args.cases,
            dry_run=False,
            note=args.note,
            force=args.force,
            keep_cases=args.keep_cases,
        )
        print(f"ok: {result.tool.slug}「{result.tool.name}」已归档至 {args.archive}")
        if result.candidate_updated:
            print(f"候选池 {result.tool.slug} → rejected")
        if result.scrub and result.scrub.affected_case_ids:
            print(
                f"评测用例：删除 {len(result.scrub.removed_case_ids)}，"
                f"改写 {len(result.scrub.updated_case_ids)}"
            )
            print("请运行 evaluate，确认后再 update-baseline --yes")
        if result.blocked_reasons:
            print("已用 --force 绕过：")
            for reason in result.blocked_reasons:
                print(f"  - {reason}")
        return 0

    if args.command == "discard":
        candidate = discard_candidate(
            args.candidates,
            args.tools,
            args.slug,
            dry_run=True,
        )
        print(
            f"计划丢弃候选：{candidate.slug}「{candidate.name}」（status={candidate.status.value}）"
        )
        if args.dry_run:
            print("dry-run: 未写盘")
            return 0
        if not args.yes:
            print("未写盘；确认后加 --yes")
            return 2
        discard_candidate(args.candidates, args.tools, args.slug, dry_run=False)
        print(f"ok: 已从候选池移除 {args.slug}")
        return 0

    raise ValueError(f"未知命令：{args.command}")


def _print_migration_plan(
    report: MigrationStatusReport,
    *,
    slugs: list[str] | None,
) -> None:
    if slugs:
        print(f"计划迁移 slug：{', '.join(slugs)}")
    print(
        f"正式库待迁移 {len(report.formal_pending)} / {report.formal_total}；"
        f"候选池待迁移 {len(report.candidate_pending)} / {report.candidate_total}"
    )


def _print_retire_plan(result: RetireResult, *, keep_cases: bool) -> None:
    print(f"计划下架：{result.tool.slug}「{result.tool.name}」→ 归档库")
    if result.candidate_updated:
        print("候选池同 slug 将改为 rejected")
    if keep_cases:
        print("评测用例：保持不变（--keep-cases）")
    elif result.scrub is None:
        print("评测用例：无变更")
    else:
        print(
            f"评测用例：受影响 {len(result.scrub.affected_case_ids)}，"
            f"将删除 {len(result.scrub.removed_case_ids)}，"
            f"将改写 {len(result.scrub.updated_case_ids)}"
        )
    if result.blocked_reasons:
        print("安全提示（已要求 --force）：")
        for reason in result.blocked_reasons:
            print(f"  - {reason}")


def _print_summary(report: EvaluationReport | None) -> None:
    if report is None:
        return
    summary = report.summary
    print(
        f"用例 {summary.active_cases} 启用/{summary.skipped_cases} 跳过；"
        f"Top1 {summary.top1_accuracy:.1%}；Top3 {summary.top3_recall:.1%}；"
        f"MRR {summary.mrr:.3f}；误召回 {summary.forbidden_violation_rate:.1%}"
    )


def _print_gate(gate: GateResult | None) -> None:
    if gate is None:
        return
    print("门禁：" + ("通过" if gate.passed else "阻断"))
    for issue in gate.issues:
        print(f"  - {issue.severity.value} · {issue.code}: {issue.message}")


def _combine_gates(first: GateResult, second: GateResult | None) -> GateResult:
    issues = list(first.issues)
    if second:
        issues.extend(second.issues)
    return GateResult(
        passed=not any(issue.severity == GateSeverity.BLOCKING for issue in issues),
        issues=issues,
    )


if __name__ == "__main__":
    raise SystemExit(main())
