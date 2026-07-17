"""ToolsRepository：加载与查询 data/tools.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PmTool(BaseModel):
    """对应 tools.json 单条工具。"""

    slug: str
    name: str
    name_en: str = ""
    process_group: str = ""
    knowledge_area: str = ""
    summary: str = ""
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    draftable: bool = False
    template: dict[str, Any] | None = None
    template_fields: list[str] | None = None
    table_config: dict[str, Any] | None = None


class ToolsRepository:
    """进程内只读知识库（启动加载一次即可）。"""

    def __init__(self, tools: list[PmTool]) -> None:
        self._tools = list(tools)
        self._by_slug = {t.slug: t for t in self._tools}

    @classmethod
    def from_json_path(cls, path: Path | str) -> ToolsRepository:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"工具库文件不存在：{file_path}")
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("tools.json 根节点必须是数组")
        tools = [PmTool.model_validate(item) for item in raw]
        return cls(tools)

    def __len__(self) -> int:
        return len(self._tools)

    def all(self) -> list[PmTool]:
        return list(self._tools)

    def exists(self, slug: str) -> bool:
        return slug in self._by_slug

    def get_by_slug(self, slug: str) -> PmTool | None:
        return self._by_slug.get(slug)

    def list_summaries(self) -> list[dict[str, str]]:
        return [self._summary_dict(t) for t in self._tools]

    def search(self, keyword: str, *, limit: int = 8) -> list[PmTool]:
        """按关键词在名称/摘要/场景/过程组等字段中检索。"""
        query = keyword.strip().lower()
        if not query:
            return []

        tokens = [t for t in query.replace("，", " ").replace(",", " ").split() if t]
        if not tokens:
            tokens = [query]

        scored: list[tuple[int, PmTool]] = []
        for tool in self._tools:
            hay = " ".join(
                [
                    tool.slug,
                    tool.name,
                    tool.name_en,
                    tool.process_group,
                    tool.knowledge_area,
                    tool.summary,
                    tool.description,
                    " ".join(tool.scenarios),
                    " ".join(tool.steps),
                ]
            ).lower()
            score = 0
            for token in tokens:
                if token in hay:
                    score += 2 if token in tool.slug or token in tool.name.lower() else 1
            if score:
                scored.append((score, tool))

        scored.sort(key=lambda item: (-item[0], item[1].slug))
        return [tool for _, tool in scored[: max(1, limit)]]

    def recommend_by_question(
        self,
        question: str,
        *,
        context: str = "",
        limit: int = 3,
    ) -> list[tuple[PmTool, str]]:
        """基于卡点文本做启发式打分，返回 (工具, 理由) 最多 limit 条。"""
        text = f"{question} {context}".strip().lower()
        if not text:
            return []

        keyword_boosts: list[tuple[list[str], list[str], str]] = [
            (
                ["立项", "授权", "章程", "启动", "kickoff", "批准"],
                ["project-charter", "stakeholder-register", "assumption-log"],
                "与立项授权/启动阶段高度相关",
            ),
            (
                ["风险", "不确定", "担心", "隐患", "risk"],
                ["risk-register", "risk-management-plan", "risk-report"],
                "与风险识别与应对相关",
            ),
            (
                ["进度", "排期", "延期", "工期", "里程碑", "甘特"],
                ["gantt-chart", "activity-list", "network-diagram"],
                "与进度规划/赶工相关",
            ),
            (
                ["范围", "需求", "验收", "边界"],
                ["project-scope-statement", "wbs", "requirements-documentation"],
                "与范围与需求澄清相关",
            ),
            (
                ["成本", "预算", "超支", "花费"],
                ["cost-baseline", "cost-management-plan", "earned-value-analysis"],
                "与成本预算与绩效相关",
            ),
            (
                ["干系人", "老板", "跨部门", "推动"],
                ["stakeholder-register", "stakeholder-engagement-plan", "raci-matrix"],
                "与干系人管理相关",
            ),
            (
                ["变更", "改需求", "change"],
                ["change-request", "change-management-plan", "issue-log"],
                "与变更控制相关",
            ),
            (
                ["结项", "收尾", "移交", "关闭"],
                ["project-closure-document", "final-report", "transition-plan"],
                "与项目收尾相关",
            ),
            (
                ["沟通", "汇报", "周报", "状态"],
                ["status-report", "communications-management-plan"],
                "与沟通与状态同步相关",
            ),
            (
                ["决策", "选方案", "拿不定主意", "trade-off", "怎么选", "纠结", "权衡"],
                ["decision-matrix", "swot-analysis", "pre-mortem", "decision-record"],
                "与方案决策/权衡相关",
            ),
        ]

        scores: dict[str, float] = {t.slug: 0.0 for t in self._tools}
        reasons: dict[str, str] = {}

        for keywords, slugs, reason in keyword_boosts:
            if any(k.lower() in text for k in keywords):
                for i, slug in enumerate(slugs):
                    if slug in scores:
                        scores[slug] += 10 - i
                        reasons.setdefault(slug, reason)

        # 通用检索分
        for tool in self.search(question, limit=12):
            scores[tool.slug] += 3
            reasons.setdefault(tool.slug, f"与「{tool.summary}」语义接近")

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        results: list[tuple[PmTool, str]] = []
        for slug, score in ranked:
            if score <= 0:
                continue
            tool = self._by_slug.get(slug)
            if tool is None:
                continue
            reason = reasons.get(slug, tool.summary)
            results.append((tool, reason))
            if len(results) >= max(1, min(3, limit)):
                break

        # 若完全无匹配，回退到启动常见三件套里的前 1～2 个
        if not results:
            fallback = ["project-charter", "stakeholder-register", "risk-register"]
            for slug in fallback[:2]:
                tool = self._by_slug.get(slug)
                if tool:
                    results.append((tool, "信息有限，先从通用启动/规划工具切入"))
        return results

    @staticmethod
    def _summary_dict(tool: PmTool) -> dict[str, str]:
        return {
            "slug": tool.slug,
            "name": tool.name,
            "summary": tool.summary,
            "process_group": tool.process_group,
            "knowledge_area": tool.knowledge_area,
        }
