"""get_tool_detail：按 slug 返回工具详情。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class GetToolDetailArgs(BaseModel):
    slug: str = Field(description="工具 slug，例如 project-charter、risk-register")


def register_get_tool_detail(registry: ToolRegistry, repo: ToolsRepository) -> None:
    def _execute(args: GetToolDetailArgs) -> str:
        tool = repo.get_by_slug(args.slug.strip())
        if tool is None:
            known = ", ".join(sorted(t.slug for t in repo.all())[:8])
            return (
                f"错误：未知 slug「{args.slug}」。不要编造库外工具。"
                f"可先 search_tools；示例 slug：{known}…"
            )
        payload = {
            "slug": tool.slug,
            "name": tool.name,
            "name_en": tool.name_en,
            "process_group": tool.process_group,
            "knowledge_area": tool.knowledge_area,
            "summary": tool.summary,
            "description": tool.description,
            "steps": tool.steps,
            "scenarios": tool.scenarios,
            "draftable": tool.draftable,
            "note": (
                "本 MVP 支持自动起草"
                if tool.draftable
                else "本 MVP 仅支持查看说明与推荐，不支持自动起草"
            ),
        }
        return json.dumps(payload, ensure_ascii=False)

    registry.register(
        ToolSpec(
            name="get_tool_detail",
            description=(
                "按 slug 查看单个工具的详细说明、步骤与适用场景。"
                "用户询问某个具体工具时使用。"
            ),
            parameters_model=GetToolDetailArgs,
            execute=_execute,
            category="knowledge",
            pure=True,
        )
    )
