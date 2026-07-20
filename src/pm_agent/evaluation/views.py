"""黄金用例与基线报告的 Markdown / HTML 可读视图。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from html import escape
from pathlib import Path

from pm_agent.evaluation.models import CaseResult, EvaluationCase, EvaluationReport

_CASES_CSS = """
:root { color-scheme: light dark; }
body {
  font-family: ui-sans-serif, system-ui, sans-serif;
  margin: 1.5rem;
  line-height: 1.45;
}
h1, h2 { margin-top: 1.5rem; }
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 1rem 0;
  align-items: end;
}
.controls label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
}
input, select { padding: 0.35rem 0.5rem; min-width: 10rem; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75rem 0 1.25rem;
  font-size: 0.9rem;
}
th, td {
  border: 1px solid #8884;
  padding: 0.4rem 0.55rem;
  text-align: left;
  vertical-align: top;
}
th { background: #8881; }
tr.hidden { display: none; }
.summary { margin: 0.5rem 0 1rem; }
.muted { opacity: 0.75; font-size: 0.85rem; }
code { font-size: 0.85em; }
"""

_BASELINE_CSS = (
    _CASES_CSS
    + """
.kpi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}
.kpi div {
  border: 1px solid #8884;
  border-radius: 0.4rem;
  padding: 0.75rem;
}
.kpi strong {
  display: block;
  font-size: 1.25rem;
  margin-top: 0.25rem;
}
.fail { background: #f4433614; }
.pass { background: #4caf5014; }
.skip { opacity: 0.7; }
"""
)


def render_cases_markdown(cases: list[EvaluationCase]) -> str:
    """将黄金用例渲染为 Markdown。"""
    lines = [
        "# 工具推荐黄金评测用例",
        "",
        "> 由 JSON 导出的可读视图，请勿手改。",
        "> 真相源：`data/evaluation/tool_recommendation_cases.json`",
        "",
        f"- 总数：{len(cases)}",
    ]
    for family, count in _count_by(cases, lambda c: c.family):
        lines.append(f"- 家族 `{family}`：{count}")
    for case_type, count in _count_by(cases, lambda c: c.case_type.value):
        lines.append(f"- 类型 `{case_type}`：{count}")
    lines.append("")

    by_family: dict[str, list[EvaluationCase]] = {}
    for case in cases:
        by_family.setdefault(case.family, []).append(case)

    for family in sorted(by_family):
        lines.extend(
            [
                f"## {family}",
                "",
                "| id | query | type | critical | Top1 | Top3 必含 | Top3 禁止 | requires | tags |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for case in by_family[family]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(case.id),
                        _md_cell(case.query),
                        case.case_type.value,
                        "是" if case.critical else "",
                        _md_list(case.acceptable_top1),
                        _md_list(case.required_top3),
                        _md_list(case.forbidden_top3),
                        _md_list(case.requires_tools),
                        _md_list(case.tags),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_cases_html(cases: list[EvaluationCase]) -> str:
    """将黄金用例渲染为可筛选的单文件 HTML。"""
    family_options = sorted({case.family for case in cases})
    type_options = sorted({case.case_type.value for case in cases})
    summary_bits = [f"<li>总数：{len(cases)}</li>"]
    for family, count in _count_by(cases, lambda c: c.family):
        summary_bits.append(f"<li>家族 <code>{escape(family)}</code>：{count}</li>")
    for case_type, count in _count_by(cases, lambda c: c.case_type.value):
        summary_bits.append(f"<li>类型 <code>{escape(case_type)}</code>：{count}</li>")

    by_family: dict[str, list[EvaluationCase]] = {}
    for case in cases:
        by_family.setdefault(case.family, []).append(case)

    sections: list[str] = []
    for family in sorted(by_family):
        rows = []
        for case in by_family[family]:
            search = " ".join(
                [
                    case.id,
                    case.query,
                    case.context,
                    case.case_type.value,
                    *case.acceptable_top1,
                    *case.required_top3,
                    *case.forbidden_top3,
                    *case.requires_tools,
                    *case.tags,
                ]
            ).lower()
            rows.append(
                "<tr "
                f'data-family="{escape(case.family, quote=True)}" '
                f'data-type="{escape(case.case_type.value, quote=True)}" '
                f'data-search="{escape(search, quote=True)}">'
                f"<td><code>{escape(case.id)}</code></td>"
                f"<td>{escape(case.query)}"
                + (f'<div class="muted">{escape(case.context)}</div>' if case.context else "")
                + "</td>"
                f"<td>{escape(case.case_type.value)}</td>"
                f"<td>{'是' if case.critical else ''}</td>"
                f"<td>{_html_list(case.acceptable_top1)}</td>"
                f"<td>{_html_list(case.required_top3)}</td>"
                f"<td>{_html_list(case.forbidden_top3)}</td>"
                f"<td>{_html_list(case.requires_tools)}</td>"
                f"<td>{_html_list(case.tags)}</td>"
                "</tr>"
            )
        sections.append(
            f"<h2>{escape(family)}</h2>"
            "<table><thead><tr>"
            "<th>id</th><th>query</th><th>type</th><th>critical</th>"
            "<th>Top1</th><th>Top3 必含</th><th>Top3 禁止</th>"
            "<th>requires</th><th>tags</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    family_opts = "".join(
        f'<option value="{escape(item, quote=True)}">{escape(item)}</option>'
        for item in family_options
    )
    type_opts = "".join(
        f'<option value="{escape(item, quote=True)}">{escape(item)}</option>'
        for item in type_options
    )
    script = """
<script>
const q = document.getElementById('q');
const family = document.getElementById('family');
const type = document.getElementById('type');
function applyFilter() {
  const needle = (q.value || '').trim().toLowerCase();
  const fam = family.value;
  const typ = type.value;
  document.querySelectorAll('tbody tr').forEach((row) => {
    const okFamily = !fam || row.dataset.family === fam;
    const okType = !typ || row.dataset.type === typ;
    const okSearch = !needle || (row.dataset.search || '').includes(needle);
    row.classList.toggle('hidden', !(okFamily && okType && okSearch));
  });
}
[q, family, type].forEach((el) => el.addEventListener('input', applyFilter));
[family, type].forEach((el) => el.addEventListener('change', applyFilter));
</script>
"""
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        "<title>工具推荐黄金评测用例</title>"
        f"<style>{_CASES_CSS}</style></head><body>"
        "<h1>工具推荐黄金评测用例</h1>"
        '<p class="muted">由 JSON 导出的可读视图，请勿手改。'
        "真相源：<code>data/evaluation/tool_recommendation_cases.json</code></p>"
        f'<ul class="summary">{"".join(summary_bits)}</ul>'
        '<div class="controls">'
        '<label>搜索<input id="q" type="search" '
        'placeholder="id / query / slug…"></label>'
        '<label>家族<select id="family"><option value="">全部</option>'
        f"{family_opts}</select></label>"
        '<label>类型<select id="type"><option value="">全部</option>'
        f"{type_opts}</select></label>"
        "</div>" + "".join(sections) + script + "</body></html>\n"
    )


def render_baseline_markdown(report: EvaluationReport) -> str:
    """将基线报告渲染为 Markdown。"""
    summary = report.summary
    lines = [
        "# 工具推荐评测基线",
        "",
        "> 由 JSON 导出的可读视图，请勿手改。真相源：`data/evaluation/baseline.json`",
        "",
        "## 指标",
        "",
        f"- 用例：{summary.active_cases} 启用 / {summary.skipped_cases} 跳过"
        f"（共 {summary.total_cases}）",
        f"- Top 1：{summary.top1_accuracy:.1%}（{summary.top1_passed}/{summary.top1_cases}）",
        f"- Top 3：{summary.top3_recall:.1%}（{summary.top3_passed}/{summary.top3_cases}）",
        f"- MRR：{summary.mrr:.3f}",
        "- 禁止工具误召回："
        f"{summary.forbidden_violation_rate:.1%} "
        f"（{summary.forbidden_violations}/{summary.forbidden_cases}）",
        f"- 数据集摘要：`{report.dataset_digest}`",
        f"- 工具库摘要：`{report.tools_digest}`",
        "",
        "## 混淆对",
        "",
    ]
    if summary.confusion:
        lines.extend(["| 期望 → 实际 Top1 | 次数 |", "| --- | --- |"])
        for pair, count in sorted(summary.confusion.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {_md_cell(pair)} | {count} |")
    else:
        lines.append("- 无")
    lines.extend(["", "## 失败用例", ""])
    failed = [item for item in report.results if _is_failed(item)]
    if not failed:
        lines.append("- 无")
    else:
        lines.extend(_result_table_md(failed))
    lines.extend(["", "## 全部结果", ""])
    lines.extend(_result_table_md(report.results))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_baseline_html(report: EvaluationReport) -> str:
    """将基线报告渲染为可筛选的单文件 HTML。"""
    summary = report.summary
    confusion_rows = (
        "".join(
            f"<tr><td>{escape(pair)}</td><td>{count}</td></tr>"
            for pair, count in sorted(
                summary.confusion.items(), key=lambda item: (-item[1], item[0])
            )
        )
        or "<tr><td colspan='2'>无</td></tr>"
    )

    failed = [item for item in report.results if _is_failed(item)]
    failed_section = (
        "<p>无</p>"
        if not failed
        else "<table><thead>"
        + _result_table_head()
        + "</thead><tbody>"
        + "".join(_result_row_html(item) for item in failed)
        + "</tbody></table>"
    )
    all_rows = "".join(_result_row_html(item) for item in report.results)
    script = """
<script>
const q = document.getElementById('q');
const onlyFail = document.getElementById('only-fail');
function applyFilter() {
  const needle = (q.value || '').trim().toLowerCase();
  const failOnly = onlyFail.checked;
  document.querySelectorAll('table.all-results tbody tr').forEach((row) => {
    const okFail = !failOnly || row.dataset.failed === '1';
    const okSearch = !needle || (row.dataset.search || '').includes(needle);
    row.classList.toggle('hidden', !(okFail && okSearch));
  });
}
q.addEventListener('input', applyFilter);
onlyFail.addEventListener('change', applyFilter);
</script>
"""
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        "<title>工具推荐评测基线</title>"
        f"<style>{_BASELINE_CSS}</style></head><body>"
        "<h1>工具推荐评测基线</h1>"
        '<p class="muted">由 JSON 导出的可读视图，请勿手改。'
        "真相源：<code>data/evaluation/baseline.json</code></p>"
        '<div class="kpi">'
        f"<div>启用 / 跳过<strong>{summary.active_cases} / {summary.skipped_cases}</strong></div>"
        f"<div>Top 1<strong>{summary.top1_accuracy:.1%}</strong>"
        f"<span class='muted'>{summary.top1_passed}/{summary.top1_cases}</span></div>"
        f"<div>Top 3<strong>{summary.top3_recall:.1%}</strong>"
        f"<span class='muted'>{summary.top3_passed}/{summary.top3_cases}</span></div>"
        f"<div>MRR<strong>{summary.mrr:.3f}</strong></div>"
        f"<div>误召回<strong>{summary.forbidden_violation_rate:.1%}</strong>"
        f"<span class='muted'>{summary.forbidden_violations}/{summary.forbidden_cases}</span></div>"
        "</div>"
        f'<p class="muted">数据集 <code>{escape(report.dataset_digest)}</code><br>'
        f"工具库 <code>{escape(report.tools_digest)}</code></p>"
        "<h2>混淆对</h2>"
        "<table><thead><tr><th>期望 → 实际 Top1</th><th>次数</th></tr></thead>"
        f"<tbody>{confusion_rows}</tbody></table>"
        "<h2>失败用例</h2>" + failed_section + "<h2>全部结果</h2>"
        '<div class="controls">'
        '<label>搜索<input id="q" type="search" placeholder="id / query / slug…"></label>'
        '<label><span>仅失败</span><input id="only-fail" type="checkbox"></label>'
        "</div>"
        '<table class="all-results"><thead>'
        + _result_table_head()
        + "</thead><tbody>"
        + all_rows
        + "</tbody></table>"
        + script
        + "</body></html>\n"
    )


def write_cases_views(
    cases: list[EvaluationCase],
    output_dir: Path | str,
) -> tuple[Path, Path]:
    """写出 cases.md 与 cases.html。"""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    md_path = directory / "cases.md"
    html_path = directory / "cases.html"
    md_path.write_text(render_cases_markdown(cases), encoding="utf-8")
    html_path.write_text(render_cases_html(cases), encoding="utf-8")
    return md_path, html_path


def write_baseline_views(
    report: EvaluationReport,
    output_dir: Path | str,
) -> tuple[Path, Path]:
    """写出 baseline.md 与 baseline.html。"""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    md_path = directory / "baseline.md"
    html_path = directory / "baseline.html"
    md_path.write_text(render_baseline_markdown(report), encoding="utf-8")
    html_path.write_text(render_baseline_html(report), encoding="utf-8")
    return md_path, html_path


def _count_by(
    cases: list[EvaluationCase],
    key: Callable[[EvaluationCase], str],
) -> list[tuple[str, int]]:
    counter = Counter(key(case) for case in cases)
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _md_list(values: list[str]) -> str:
    return ", ".join(_md_cell(item) for item in values) if values else ""


def _html_list(values: list[str]) -> str:
    if not values:
        return ""
    return ", ".join(f"<code>{escape(item)}</code>" for item in values)


def _is_failed(result: CaseResult) -> bool:
    if not result.active:
        return False
    if result.forbidden_hits:
        return True
    if result.top1_pass is False:
        return True
    if result.top3_pass is False:
        return True
    return False


def _result_table_md(results: list[CaseResult]) -> list[str]:
    lines = [
        "| id | query | active | Top1 | Top3 | RR | rankings | forbidden | skip |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item.case_id),
                    _md_cell(item.query),
                    "是" if item.active else "跳过",
                    _bool_cell(item.top1_pass),
                    _bool_cell(item.top3_pass),
                    "" if item.reciprocal_rank is None else f"{item.reciprocal_rank:.3f}",
                    _md_list(item.rankings),
                    _md_list(item.forbidden_hits),
                    _md_cell(item.skipped_reason),
                ]
            )
            + " |"
        )
    return lines


def _bool_cell(value: bool | None) -> str:
    if value is None:
        return ""
    return "通过" if value else "失败"


def _result_table_head() -> str:
    return (
        "<tr><th>id</th><th>query</th><th>状态</th><th>Top1</th><th>Top3</th>"
        "<th>RR</th><th>rankings</th><th>forbidden</th><th>skip</th></tr>"
    )


def _result_row_html(item: CaseResult) -> str:
    failed = "1" if _is_failed(item) else "0"
    search = " ".join(
        [
            item.case_id,
            item.query,
            item.family,
            item.case_type.value,
            *item.rankings,
            *item.forbidden_hits,
            item.skipped_reason,
        ]
    ).lower()
    status = "启用" if item.active else "跳过"
    css = "fail" if _is_failed(item) else ("skip" if not item.active else "pass")
    rr = "" if item.reciprocal_rank is None else f"{item.reciprocal_rank:.3f}"
    return (
        f'<tr class="{css}" data-failed="{failed}" '
        f'data-search="{escape(search, quote=True)}">'
        f"<td><code>{escape(item.case_id)}</code></td>"
        f"<td>{escape(item.query)}</td>"
        f"<td>{status}</td>"
        f"<td>{escape(_bool_cell(item.top1_pass))}</td>"
        f"<td>{escape(_bool_cell(item.top3_pass))}</td>"
        f"<td>{rr}</td>"
        f"<td>{_html_list(item.rankings)}</td>"
        f"<td>{_html_list(item.forbidden_hits)}</td>"
        f"<td>{escape(item.skipped_reason)}</td>"
        "</tr>"
    )
