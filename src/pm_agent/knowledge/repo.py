"""ToolsRepository：加载与查询 data/tools.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pm_agent.knowledge.categories import USE_CASE_ORDER, validate_use_cases

# 推荐启发式硬编码 slug；下架工具时需人工同步，否则 retire 默认拦截。
KEYWORD_BOOSTS: list[tuple[list[str], list[str], str]] = [
    (
        ["立项", "授权", "章程", "启动", "kickoff", "批准"],
        ["project-charter", "stakeholder-register", "raci-matrix"],
        "与立项授权/启动阶段高度相关",
    ),
    (
        ["风险", "不确定", "隐患", "risk", "担心延期", "风险担心"],
        ["risk-register", "risk-report", "pre-mortem"],
        "与风险识别与应对相关",
    ),
    (
        ["进度", "排期", "延期", "工期", "里程碑", "甘特"],
        ["gantt-chart", "moscow-prioritization", "decision-matrix"],
        "与进度规划/赶工相关",
    ),
    (
        ["范围", "需求", "验收", "边界"],
        ["moscow-prioritization", "cross-functional-alignment", "decision-matrix"],
        "与范围与需求澄清相关",
    ),
    (
        ["成本", "预算", "超支", "花费", "外采", "自研"],
        ["decision-matrix", "swot-analysis", "decision-record"],
        "与方案决策/权衡相关",
    ),
    (
        ["干系人", "干系人登记", "影响方", "跨部门推动"],
        ["stakeholder-register", "raci-matrix", "force-field-analysis"],
        "与干系人管理相关",
    ),
    (
        ["变更", "改需求", "change"],
        ["decision-record", "five-whys", "raci-matrix"],
        "与方案决策/权衡相关",
    ),
    (
        ["结项", "正式关闭", "关闭项目", "收尾清单"],
        ["lessons-learned-register", "decision-record", "risk-report"],
        "与项目收尾相关",
    ),
    (
        [
            "可检索",
            "经验教训",
            "写成条目",
            "踩坑写成",
            "沉淀给",
            "教训登记",
        ],
        ["lessons-learned-register", "decision-record", "five-whys"],
        "与项目收尾相关",
    ),
    (
        [
            "活动刚结束",
            "上线完了",
            "四个问题",
            "原计划",
            "对照实际",
            "演练完",
            "发布刚结束",
            "趁热",
            "行动后复盘",
            "计划与实际",
            "成败说法不一",
            "活动复盘",
        ],
        ["after-action-review", "lessons-learned-register", "decision-record"],
        "与项目收尾相关",
    ),
    (
        [
            "迭代结束",
            "轻量复盘",
            "开始/停止/继续",
            "该开始",
            "该停止",
            "该继续",
            "起停续",
            "Sprint 收尾",
            "三列",
            "双周一次的复盘",
            "协作节奏",
        ],
        ["start-stop-continue", "lessons-learned-register", "decision-record"],
        "与项目收尾相关",
    ),
    (
        [
            "追责会",
            "无责",
            "故障复盘",
            "不敢说实话",
            "还原时间线",
            "系统根因",
            "事后分析",
            "谁的锅",
            "重大事故",
            "线上重大",
        ],
        ["blameless-postmortem", "five-whys", "lessons-learned-register"],
        "与项目收尾相关",
    ),
    (
        [
            "交给运维",
            "交接会",
            "知识断档",
            "移交包",
            "接任",
            "撤场",
            "知识移交",
            "不会运维",
            "跟岗",
            "接手后",
        ],
        ["knowledge-handover", "lessons-learned-register", "raci-matrix"],
        "与项目收尾相关",
    ),
    (
        [
            "假设失败",
            "假设已经失败",
            "倒推可能",
            "事前验尸",
            "预判翻车",
            "还没启动就想假设",
        ],
        ["pre-mortem", "risk-register", "risk-report"],
        "与风险识别与应对相关",
    ),
    (
        [
            "争吵",
            "僵持",
            "拒绝合作",
            "拒绝再谈",
            "拒绝沟通",
            "中立人协调",
            "中立方介入",
            "第三方主持",
            "第三方",
            "升级规则",
            "升级机制",
            "停摆",
            "公开争夺",
            "公开争吵",
            "各执一词",
            "争议公开",
            "影响交付",
        ],
        [
            "conflict-resolution-process",
            "difficult-conversation-prep",
            "sbi-feedback",
        ],
        "与冲突升级与中立协调相关",
    ),
    (
        [
            "负面反馈",
            "就事论事",
            "具体行为",
            "提醒同事",
            "提醒下属",
            "指出问题",
            "客观指出",
            "行为反馈",
            "不伤关系",
            "打断别人",
        ],
        [
            "sbi-feedback",
            "difficult-conversation-prep",
            "pyramid-principle",
        ],
        "与一对一行为反馈相关",
    ),
    (
        [
            "对齐",
            "接口",
            "责任人",
            "跨部门",
            "联调",
            "共同交付",
            "供应商",
            "行动项",
            "时间依赖",
            "依赖项",
        ],
        [
            "cross-functional-alignment",
            "raci-matrix",
            "stakeholder-register",
        ],
        "与跨团队对齐与依赖同步相关",
    ),
    (
        [
            "证据",
            "金字塔",
            "三十秒",
            "高管",
            "没有重点",
            "不知道建议",
            "邮件堆",
            "先说结论",
            "结论先行",
        ],
        [
            "pyramid-principle",
            "decision-record",
            "lessons-learned-register",
        ],
        "与结论先行的结构化汇报相关",
    ),
    (
        [
            "不知道怎么开口",
            "我想预演",
            "预演他",
            "准备开场",
            "开场和底线",
            "拒绝老板",
            "谈裁员",
            "担心对方",
            "高难度对话",
            "怎么回应",
        ],
        [
            "difficult-conversation-prep",
            "sbi-feedback",
            "pyramid-principle",
        ],
        "与高难度对话准备相关",
    ),
    (
        ["周报", "状态同步", "项目状态"],
        [
            "pyramid-principle",
            "sbi-feedback",
            "cross-functional-alignment",
        ],
        "与日常状态同步相关",
    ),
    (
        ["决策", "选方案", "拿不定主意", "trade-off", "怎么选", "纠结", "权衡"],
        ["decision-matrix", "swot-analysis", "pre-mortem", "decision-record"],
        "与方案决策/权衡相关",
    ),
    (
        ["连续追问", "为什么定位", "定位根因", "5 why", "五个为什么"],
        ["five-whys", "decision-record", "risk-register"],
        "与方案决策/权衡相关",
    ),
]
FALLBACK_SLUGS: list[str] = [
    "project-charter",
    "stakeholder-register",
    "risk-register",
]


def hardcoded_recommendation_slugs() -> frozenset[str]:
    """返回推荐启发式硬编码引用的全部 slug。"""
    slugs: set[str] = set(FALLBACK_SLUGS)
    for _keywords, boost_slugs, _reason in KEYWORD_BOOSTS:
        slugs.update(boost_slugs)
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
        slugs = [tool.slug for tool in tools]
        if len(slugs) != len(set(slugs)):
            duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
            raise ValueError(f"tools.json 存在重复 slug：{duplicates}")
        for tool in tools:
            validate_use_cases(tool.use_cases, slug=tool.slug)
        return cls(tools)

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
                    " ".join(tool.use_cases),
                    tool.summary,
                    tool.description,
                    " ".join(tool.scenarios),
                    " ".join(tool.steps),
                    " ".join(tool.trigger_phrases),
                ]
            ).lower()
            score = 0
            for token in tokens:
                if token in hay:
                    score += 2 if token in tool.slug or token in tool.name.lower() else 1
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
            if any(
                phrase.strip().lower() in text
                for phrase in tool.trigger_phrases
                if phrase.strip()
            ):
                scores[tool.slug] += 12
                reasons.setdefault(tool.slug, "与用户口语卡点直接匹配")

        for keywords, slugs, reason in KEYWORD_BOOSTS:
            if any(k.lower() in text for k in keywords):
                for i, slug in enumerate(slugs):
                    if slug in scores:
                        scores[slug] += 10 - i
                        reasons.setdefault(slug, reason)

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
            for slug in FALLBACK_SLUGS[:2]:
                tool = self._by_slug.get(slug)
                if tool:
                    results.append((tool, "信息有限，先从通用启动工具切入"))
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
