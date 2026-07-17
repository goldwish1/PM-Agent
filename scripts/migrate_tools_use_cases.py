#!/usr/bin/env python3
"""一次性迁移：tools.json 增加 use_cases，删除 process_group / knowledge_area。"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = REPO_ROOT / "data" / "tools.json"

USE_CASES_BY_SLUG: dict[str, list[str]] = {
    "project-charter": ["立项与授权"],
    "stakeholder-register": ["立项与授权", "干系人与协作"],
    "assumption-log": ["立项与授权", "风险与问题"],
    "benefits-management-plan": ["立项与授权", "流程规范（参考）"],
    "project-management-plan": ["流程规范（参考）"],
    "scope-management-plan": ["流程规范（参考）", "范围与需求"],
    "requirements-documentation": ["范围与需求"],
    "requirements-traceability-matrix": ["范围与需求"],
    "project-scope-statement": ["范围与需求"],
    "wbs": ["范围与需求"],
    "schedule-management-plan": ["流程规范（参考）", "进度与排期"],
    "activity-list": ["进度与排期"],
    "network-diagram": ["进度与排期"],
    "gantt-chart": ["进度与排期"],
    "cost-management-plan": ["流程规范（参考）", "成本与预算"],
    "cost-baseline": ["成本与预算"],
    "quality-management-plan": ["流程规范（参考）"],
    "resource-management-plan": ["流程规范（参考）", "干系人与协作"],
    "raci-matrix": ["干系人与协作"],
    "communications-management-plan": ["流程规范（参考）", "沟通与汇报"],
    "risk-management-plan": ["流程规范（参考）", "风险与问题"],
    "risk-register": ["风险与问题"],
    "procurement-management-plan": ["流程规范（参考）"],
    "stakeholder-engagement-plan": ["流程规范（参考）", "干系人与协作"],
    "change-management-plan": ["流程规范（参考）", "变更与管控"],
    "deliverables": ["范围与需求"],
    "issue-log": ["风险与问题"],
    "lessons-learned-register": ["收尾与复盘"],
    "team-charter": ["干系人与协作"],
    "quality-checklists": ["范围与需求"],
    "status-report": ["沟通与汇报"],
    "earned-value-analysis": ["成本与预算", "进度与排期"],
    "variance-analysis": ["进度与排期", "成本与预算"],
    "change-request": ["变更与管控"],
    "risk-report": ["风险与问题", "沟通与汇报"],
    "final-report": ["收尾与复盘", "沟通与汇报"],
    "project-closure-document": ["收尾与复盘"],
    "acceptance-document": ["收尾与复盘", "范围与需求"],
    "transition-plan": ["收尾与复盘"],
    "decision-matrix": ["决策与分析"],
    "swot-analysis": ["决策与分析"],
    "pre-mortem": ["决策与分析", "风险与问题"],
    "moscow-prioritization": ["决策与分析", "范围与需求"],
    "five-whys": ["决策与分析", "风险与问题"],
    "force-field-analysis": ["决策与分析", "干系人与协作"],
    "six-thinking-hats": ["决策与分析", "干系人与协作"],
    "decision-record": ["决策与分析"],
}


def main() -> None:
    raw = json.loads(TOOLS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("tools.json 根节点必须是数组")

    slugs_in_file = {item["slug"] for item in raw}
    missing = set(USE_CASES_BY_SLUG) - slugs_in_file
    extra = slugs_in_file - set(USE_CASES_BY_SLUG)
    if missing:
        raise SystemExit(f"映射表缺少 slug: {sorted(missing)}")
    if extra:
        raise SystemExit(f"映射表多余 slug: {sorted(extra)}")

    out: list[dict] = []
    for item in raw:
        slug = item["slug"]
        new_item = {k: v for k, v in item.items() if k not in ("process_group", "knowledge_area")}
        new_item["use_cases"] = USE_CASES_BY_SLUG[slug]
        out.append(new_item)

    TOOLS_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Migrated {len(out)} tools -> {TOOLS_PATH}")


if __name__ == "__main__":
    main()
