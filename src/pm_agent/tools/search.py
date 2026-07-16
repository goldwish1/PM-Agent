"""search_tools：按关键词检索工具库摘要。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class SearchToolsArgs(BaseModel):
    query: str = Field(description="检索关键词，例如「立项」「风险」「进度」")
    limit: int = Field(default=5, ge=1, le=15, description="最多返回条数")


def register_search_tools(registry: ToolRegistry, repo: ToolsRepository) -> None:
    def _execute(args: SearchToolsArgs) -> str:
        hits = repo.search(args.query, limit=args.limit)
        if not hits:
            return json.dumps(
                {
                    "query": args.query,
                    "tools": [],
                    "instruction": "未检索到匹配工具。请换关键词（阶段/卡点类型），"
                    "或直接调用 recommend_tools。",
                },
                ensure_ascii=False,
            )
        payload = {
            "query": args.query,
            "tools": [ToolsRepository._summary_dict(t) for t in hits],
        }
        return json.dumps(payload, ensure_ascii=False)

    registry.register(
        ToolSpec(
            name="search_tools",
            description=(
                "按关键词检索 PMBOK 工具库摘要（slug/名称/过程组/知识领域/一句话用途）。"
                "在推荐前可用它缩小候选范围。"
            ),
            parameters_model=SearchToolsArgs,
            execute=_execute,
            category="knowledge",
            pure=True,
        )
    )
