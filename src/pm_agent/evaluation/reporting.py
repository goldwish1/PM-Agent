"""评测报告的 JSON 持久化与 Markdown 渲染。"""

from __future__ import annotations

import json
from pathlib import Path

from pm_agent.evaluation.models import (
    CaseChangeKind,
    ComparisonReport,
    EvaluationReport,
    GateResult,
)


def load_report(path: Path | str) -> EvaluationReport:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"评测基线不存在：{file_path}")
    return EvaluationReport.model_validate_json(file_path.read_text(encoding="utf-8"))


def write_report_json(path: Path | str, report: EvaluationReport) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_comparison_bundle(
    output_dir: Path | str,
    *,
    name: str,
    current: EvaluationReport,
    candidate: EvaluationReport | None = None,
    comparison: ComparisonReport | None = None,
    gate: GateResult | None = None,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{name}.json"
    markdown_path = directory / f"{name}.md"
    payload = {
        "current": current.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json") if candidate else None,
        "comparison": comparison.model_dump(mode="json") if comparison else None,
        "gate": gate.model_dump(mode="json") if gate else None,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_markdown(current, candidate, comparison, gate),
        encoding="utf-8",
    )
    return json_path, markdown_path


def render_markdown(
    current: EvaluationReport,
    candidate: EvaluationReport | None = None,
    comparison: ComparisonReport | None = None,
    gate: GateResult | None = None,
) -> str:
    lines = ["# 工具推荐命中评测", "", "## 当前指标", ""]
    lines.extend(_summary_lines(current))
    if candidate:
        lines.extend(["", "## 候选指标", ""])
        lines.extend(_summary_lines(candidate))
    if gate:
        lines.extend(
            [
                "",
                "## 发布门禁",
                "",
                "- 结论：" + ("通过" if gate.passed else "阻断"),
            ]
        )
        for issue in gate.issues:
            case = f"（{issue.case_id}）" if issue.case_id else ""
            lines.append(f"- {issue.severity.value} · {issue.code}{case}：{issue.message}")
    if comparison:
        lines.extend(["", "## 变化用例", ""])
        changed = [
            change
            for change in comparison.changes
            if change.kind
            not in (CaseChangeKind.UNCHANGED, CaseChangeKind.SKIPPED)
        ]
        if not changed:
            lines.append("- 无变化")
        for change in changed:
            before = ", ".join(change.before_rankings) or "-"
            after = ", ".join(change.after_rankings) or "-"
            lines.append(
                f"- {change.kind.value} · {change.case_id}：{before} → {after}；"
                f"{change.query}"
            )
    lines.append("")
    return "\n".join(lines)


def _summary_lines(report: EvaluationReport) -> list[str]:
    summary = report.summary
    return [
        f"- 用例：{summary.active_cases} 启用 / {summary.skipped_cases} 跳过",
        f"- Top 1：{summary.top1_accuracy:.1%}（{summary.top1_passed}/{summary.top1_cases}）",
        f"- Top 3：{summary.top3_recall:.1%}（{summary.top3_passed}/{summary.top3_cases}）",
        f"- MRR：{summary.mrr:.3f}",
        "- 禁止工具误召回："
        f"{summary.forbidden_violation_rate:.1%} "
        f"（{summary.forbidden_violations}/{summary.forbidden_cases}）",
        f"- 数据集摘要：{report.dataset_digest}",
        f"- 工具库摘要：{report.tools_digest}",
    ]
