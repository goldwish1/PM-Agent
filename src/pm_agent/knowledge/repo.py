"""ToolsRepository：加载与查询 data/tools.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pm_agent.config import REPO_ROOT
from pm_agent.knowledge.categories import USE_CASE_ORDER, validate_use_cases
from pm_agent.knowledge.matching import (
    TriggerMatchRule,
    expand_keyword,
    load_synonyms,
    match_trigger_rules,
    tokenize_query_for_search,
)

DEFAULT_BOOSTS_PATH = REPO_ROOT / "data" / "recommendation_boosts.json"

# 得分全 0 时的兜底推荐理由；recommend_tools 据此标 match_strength=weak
FALLBACK_RECOMMEND_REASON = "信息有限，先从通用启动工具切入"


class BoostRule(BaseModel):
    """推荐启发式单条场景桶。"""

    keywords: list[str] = Field(min_length=1)
    slugs: list[str] = Field(min_length=1)
    reason: str


class RecommendationBoostsConfig(BaseModel):
    """data/recommendation_boosts.json 根结构。"""

    fallback_slugs: list[str] = Field(min_length=1)
    boosts: list[BoostRule] = Field(min_length=1)


def load_recommendation_boosts(path: Path | str) -> RecommendationBoostsConfig:
    """加载并校验推荐启发式配置。"""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"推荐启发式文件不存在：{file_path}")
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("recommendation_boosts.json 根节点必须是对象")
    return RecommendationBoostsConfig.model_validate(raw)


def hardcoded_recommendation_slugs(
    boosts_path: Path | str | None = None,
) -> frozenset[str]:
    """返回推荐启发式配置引用的全部 slug。"""
    config = load_recommendation_boosts(boosts_path or DEFAULT_BOOSTS_PATH)
    slugs: set[str] = set(config.fallback_slugs)
    for rule in config.boosts:
        slugs.update(rule.slugs)
    return frozenset(slugs)


class PmTool(BaseModel):
    """对应 tools.json 单条工具。"""

    slug: str
    name: str
    name_en: str = ""
    use_cases: list[str] = Field(default_factory=list, min_length=1)
    summary: str = ""
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    trigger_phrases: list[str] = Field(default_factory=list)
    trigger_match_rules: list[TriggerMatchRule] = Field(default_factory=list, min_length=1)
    draftable: bool = False
    template: dict[str, Any] | None = None
    template_fields: list[str] | None = None
    table_config: dict[str, Any] | None = None


class ToolsRepository:
    """进程内只读知识库（启动加载一次即可）。"""

    def __init__(
        self,
        tools: list[PmTool],
        *,
        boosts: list[BoostRule] | None = None,
        fallback_slugs: list[str] | None = None,
    ) -> None:
        self._tools = list(tools)
        self._by_slug = {t.slug: t for t in self._tools}
        self._boosts = list(boosts or [])
        self._fallback_slugs = list(fallback_slugs or [])
        self._synonyms = load_synonyms()

    @classmethod
    def from_json_path(
        cls,
        path: Path | str,
        boosts_path: Path | str | None = None,
    ) -> ToolsRepository:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"工具库文件不存在：{file_path}")
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("tools.json 根节点必须是数组")
        tools = [PmTool.model_validate(item) for item in raw]
        slugs = [tool.slug for tool in tools]
        if len(slugs) != len(set(slugs)):
            duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
            raise ValueError(f"tools.json 存在重复 slug：{duplicates}")
        for tool in tools:
            validate_use_cases(tool.use_cases, slug=tool.slug)

        resolved_boosts = (
            Path(boosts_path)
            if boosts_path is not None
            else file_path.parent / "recommendation_boosts.json"
        )
        if boosts_path is not None or resolved_boosts.is_file():
            config = load_recommendation_boosts(resolved_boosts)
            known = set(slugs)
            missing = sorted(
                {
                    slug
                    for slug in [
                        *config.fallback_slugs,
                        *(s for r in config.boosts for s in r.slugs),
                    ]
                    if slug not in known
                }
            )
            if missing:
                raise ValueError(
                    f"recommendation_boosts.json 引用了正式库不存在的 slug：{missing}"
                )
            return cls(
                tools,
                boosts=config.boosts,
                fallback_slugs=config.fallback_slugs,
            )
        return cls(tools)

    @property
    def boost_rules(self) -> list[BoostRule]:
        return list(self._boosts)

    @property
    def fallback_slugs(self) -> list[str]:
        return list(self._fallback_slugs)

    def __len__(self) -> int:
        return len(self._tools)

    def all(self) -> list[PmTool]:
        return list(self._tools)

    def exists(self, slug: str) -> bool:
        return slug in self._by_slug

    def get_by_slug(self, slug: str) -> PmTool | None:
        return self._by_slug.get(slug)

    def list_by_use_case(self, use_case: str) -> list[PmTool]:
        """返回属于某实用场景的全部工具（按 slug 排序）。"""
        return sorted(
            (t for t in self._tools if use_case in t.use_cases),
            key=lambda t: t.slug,
        )

    def list_summaries(self) -> list[dict[str, str | list[str] | bool]]:
        return [self._summary_dict(t) for t in self._tools]

    def search(self, keyword: str, *, limit: int = 8) -> list[PmTool]:
        """按关键词在名称/摘要/场景/use_cases 等字段中检索。"""
        query = keyword.strip().lower()
        if not query:
            return []

        tokens = tokenize_query_for_search(query)

        scored: list[tuple[int, PmTool]] = []
        for tool in self._tools:
            hay = " ".join(
                [
                    tool.slug,
                    tool.name,
                    tool.name_en,
                    " ".join(tool.use_cases),
                    tool.summary,
                    tool.description,
                    " ".join(tool.scenarios),
                    " ".join(tool.steps),
                    " ".join(tool.trigger_phrases),
                    " ".join(
                        kw
                        for rule in tool.trigger_match_rules
                        for kw in (*rule.all_of, *rule.any_of)
                    ),
                ]
            ).lower()
            score = 0
            for token in tokens:
                variants = expand_keyword(token, synonyms=self._synonyms)
                hit_variant = next((v for v in variants if v.lower() in hay), None)
                if hit_variant is not None:
                    score_delta = (
                        2 if hit_variant in tool.slug or hit_variant in tool.name.lower() else 1
                    )
                    score += score_delta
                for use_case in tool.use_cases:
                    if token in use_case.lower():
                        score += 2
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

        scores: dict[str, float] = {t.slug: 0.0 for t in self._tools}
        reasons: dict[str, str] = {}

        for tool in self._tools:
            if match_trigger_rules(
                text, tool.trigger_match_rules, synonyms=self._synonyms
            ):
                scores[tool.slug] += 12
                reasons.setdefault(tool.slug, "与用户口语卡点规则命中")

        for rule in self._boosts:
            if any(k.lower() in text for k in rule.keywords):
                for i, slug in enumerate(rule.slugs):
                    if slug in scores:
                        scores[slug] += 10 - i
                        reasons.setdefault(slug, rule.reason)

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

        if not results:
            for slug in self._fallback_slugs[:2]:
                tool = self._by_slug.get(slug)
                if tool:
                    results.append((tool, FALLBACK_RECOMMEND_REASON))
        return results

    @staticmethod
    def _summary_dict(tool: PmTool) -> dict[str, str | list[str] | bool]:
        return {
            "slug": tool.slug,
            "name": tool.name,
            "summary": tool.summary,
            "use_cases": tool.use_cases,
            "draftable": tool.draftable,
        }

    @staticmethod
    def use_case_display_order() -> tuple[str, ...]:
        return USE_CASE_ORDER
