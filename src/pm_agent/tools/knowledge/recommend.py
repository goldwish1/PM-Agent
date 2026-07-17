"""recommend_tools：推荐 1～3 个库内工具（slug 白名单校验）。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.knowledge.categories import format_use_cases_label
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class RecommendToolsArgs(BaseModel):
    question: str = Field(description="用户卡点/问题原话")
    context: str = Field(default="", description="补充上下文（可选）")
    candidate_slugs: list[str] = Field(
        default_factory=list,
        description=(
            "可选：你提议的工具 slug 列表（1～3 个）。"
            "必须来自工具库；非法 slug 会被过滤。"
            "若不确定可留空，由工具按关键词启发式推荐。"
        ),
    )


def _filter_whitelist(
    repo: ToolsRepository,
    slugs: list[str],
) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for raw in slugs:
        slug = raw.strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        if repo.exists(slug):
            valid.append(slug)
        else:
            rejected.append(slug)
    return valid[:3], rejected


def register_recommend_tools(registry: ToolRegistry, repo: ToolsRepository) -> None:
    def _execute(args: RecommendToolsArgs) -> str:
        rejected: list[str] = []
        tools_out: list[dict[str, str | list[str] | bool]] = []
        reasoning_parts: list[str] = []

        if args.candidate_slugs:
            valid, rejected = _filter_whitelist(repo, args.candidate_slugs)
            for slug in valid:
                tool = repo.get_by_slug(slug)
                if tool is None:
                    continue
                cases = format_use_cases_label(tool.use_cases)
                tools_out.append(
                    {
                        "slug": tool.slug,
                        "name": tool.name,
                        "summary": tool.summary,
                        "use_cases": tool.use_cases,
                        "reason": f"与用户卡点匹配，属于{cases}场景",
                        "draftable": tool.draftable,
                    }
                )
            if valid:
                reasoning_parts.append(
                    "已按候选 slug 白名单校验并富化库内工具信息。"
                )
            if rejected:
                reasoning_parts.append(
                    "已丢弃非法/库外 slug：" + ", ".join(rejected) + "。"
                    "禁止编造工具名。"
                )

        if not tools_out:
            ranked = repo.recommend_by_question(
                args.question,
                context=args.context,
                limit=3,
            )
            for tool, reason in ranked:
                tools_out.append(
                    {
                        "slug": tool.slug,
                        "name": tool.name,
                        "summary": tool.summary,
                        "use_cases": tool.use_cases,
                        "reason": reason,
                        "draftable": tool.draftable,
                    }
                )
            reasoning_parts.append(
                "基于卡点关键词在库内启发式匹配 1～3 个工具。"
            )

        if not tools_out:
            return json.dumps(
                {
                    "reasoning": "无法从库内匹配到可靠推荐。",
                    "tools": [],
                    "rejected_slugs": rejected,
                    "instruction": "请补充卡点类型（如立项、风险、决策、汇报）后重试；"
                    "不要编造库外工具。",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "reasoning": " ".join(reasoning_parts),
                "tools": tools_out,
                "rejected_slugs": rejected,
            },
            ensure_ascii=False,
        )

    registry.register(
        ToolSpec(
            name="recommend_tools",
            description=(
                "根据用户工作卡点推荐 1～3 个 PMBOK 库内工具，并给出理由。"
                "仅返回白名单内 slug；禁止编造库外工具。"
            ),
            parameters_model=RecommendToolsArgs,
            execute=_execute,
            category="knowledge",
            pure=True,
        )
    )
