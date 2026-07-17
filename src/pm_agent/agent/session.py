"""会话状态：messages、澄清计数、章程/风险/决策/矩阵草稿。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

PLACEHOLDER = "待补充"
MAX_RISK_ITEMS = 3
MAX_MATRIX_CRITERIA = 6
MAX_MATRIX_OPTIONS = 5


class SessionMode(StrEnum):
    """会话模式。"""

    IDLE = "idle"
    CLARIFYING = "clarifying"
    RECOMMENDING = "recommending"
    CONSULTING = "consulting"
    DRAFTING_CHARTER = "drafting_charter"
    DRAFTING_RISK = "drafting_risk"
    DRAFTING_DECISION = "drafting_decision"
    DRAFTING_DECISION_MATRIX = "drafting_decision_matrix"
    PREVIEW = "preview"


ChatMessage = dict[str, Any]


class CharterDraft(BaseModel):
    """项目章程草稿（缺省为「待补充」）。"""

    project_name: str = PLACEHOLDER
    sponsor: str = PLACEHOLDER
    project_manager: str = PLACEHOLDER
    business_case: str = PLACEHOLDER
    high_level_scope: str = PLACEHOLDER
    milestones: str = PLACEHOLDER
    budget: str = PLACEHOLDER
    risks: str = PLACEHOLDER
    signature: str = PLACEHOLDER

    def merge_patch(self, patch: dict[str, str | None]) -> CharterDraft:
        data = self.model_dump()
        for key, value in patch.items():
            if key not in data:
                continue
            if value is None:
                continue
            text = str(value).strip()
            if text:
                data[key] = text
        return CharterDraft.model_validate(data)

    def missing_fields(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if v == PLACEHOLDER]

    def preview_lines(self) -> list[str]:
        labels = {
            "project_name": "项目名称",
            "sponsor": "发起人",
            "project_manager": "项目经理",
            "business_case": "商业论证",
            "high_level_scope": "高层级范围",
            "milestones": "里程碑",
            "budget": "预算",
            "risks": "主要风险",
            "signature": "签字栏",
        }
        return [f"- {labels[k]}：{v}" for k, v in self.model_dump().items()]


class RiskItem(BaseModel):
    """单条风险。"""

    risk_id: str = ""
    description: str = PLACEHOLDER
    cause: str = PLACEHOLDER
    probability: str = PLACEHOLDER
    impact: str = PLACEHOLDER
    score: str = PLACEHOLDER
    response: str = PLACEHOLDER
    owner: str = PLACEHOLDER
    status: str = PLACEHOLDER


class RiskRegisterDraft(BaseModel):
    """风险登记册草稿（MVP 建议 1～3 条）。"""

    items: list[RiskItem] = Field(default_factory=list)

    def preview_lines(self) -> list[str]:
        if not self.items:
            return ["（尚无风险条目）"]
        lines: list[str] = []
        for idx, item in enumerate(self.items, start=1):
            rid = item.risk_id or f"R{idx}"
            lines.append(
                f"{idx}. [{rid}] {item.description} | 概率={item.probability} "
                f"影响={item.impact} | 应对={item.response} | 责任人={item.owner}"
            )
        return lines


class DecisionDraft(BaseModel):
    """决策记录草稿（缺省为「待补充」）。"""

    decision_title: str = PLACEHOLDER
    context: str = PLACEHOLDER
    options_considered: str = PLACEHOLDER
    decision: str = PLACEHOLDER
    rationale: str = PLACEHOLDER
    consequences: str = PLACEHOLDER
    decision_maker: str = PLACEHOLDER
    decision_date: str = PLACEHOLDER
    status: str = PLACEHOLDER

    def merge_patch(self, patch: dict[str, str | None]) -> DecisionDraft:
        data = self.model_dump()
        for key, value in patch.items():
            if key not in data:
                continue
            if value is None:
                continue
            text = str(value).strip()
            if text:
                data[key] = text
        return DecisionDraft.model_validate(data)

    def missing_fields(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if v == PLACEHOLDER]

    def preview_lines(self) -> list[str]:
        labels = {
            "decision_title": "决策标题",
            "context": "背景与问题",
            "options_considered": "备选方案",
            "decision": "最终决定",
            "rationale": "决策依据",
            "consequences": "预期影响",
            "decision_maker": "决策人",
            "decision_date": "决策日期",
            "status": "状态",
        }
        return [f"- {labels[k]}：{v}" for k, v in self.model_dump().items()]


class MatrixCriterion(BaseModel):
    """决策矩阵评价准则。"""

    criterion_id: str = ""
    name: str = PLACEHOLDER
    weight: str = PLACEHOLDER


class MatrixOption(BaseModel):
    """决策矩阵备选方案及打分。"""

    option_id: str = ""
    name: str = PLACEHOLDER
    scores: dict[str, str] = Field(default_factory=dict)
    weighted_total: str = PLACEHOLDER


class DecisionMatrixDraft(BaseModel):
    """决策矩阵草稿。"""

    title: str = PLACEHOLDER
    context: str = PLACEHOLDER
    criteria: list[MatrixCriterion] = Field(default_factory=list)
    options: list[MatrixOption] = Field(default_factory=list)
    recommended_option: str = PLACEHOLDER
    rationale: str = PLACEHOLDER

    def merge_patch(self, patch: dict[str, str | None]) -> DecisionMatrixDraft:
        data = self.model_dump()
        for key, value in patch.items():
            if key not in data or key in ("criteria", "options"):
                continue
            if value is None:
                continue
            text = str(value).strip()
            if text:
                data[key] = text
        return DecisionMatrixDraft.model_validate(data)

    def preview_lines(self) -> list[str]:
        lines = [
            f"- 标题：{self.title}",
            f"- 背景：{self.context}",
            f"- 准则数：{len(self.criteria)}",
            f"- 方案数：{len(self.options)}",
            f"- 推荐方案：{self.recommended_option}",
            f"- 依据：{self.rationale}",
        ]
        for idx, criterion in enumerate(self.criteria, start=1):
            cid = criterion.criterion_id or f"C{idx:02d}"
            lines.append(f"  · [{cid}] {criterion.name}（权重 {criterion.weight}）")
        for idx, option in enumerate(self.options, start=1):
            oid = option.option_id or f"O{idx:02d}"
            lines.append(
                f"  · [{oid}] {option.name} | 加权总分={option.weighted_total}"
            )
        return lines


@dataclass
class SessionState:
    """进程内会话（关进程即丢）。"""

    messages: list[ChatMessage] = field(default_factory=list)
    mode: SessionMode = SessionMode.IDLE
    clarify_count: int = 0
    charter_draft: CharterDraft | None = None
    risk_draft: RiskRegisterDraft | None = None
    decision_draft: DecisionDraft | None = None
    matrix_draft: DecisionMatrixDraft | None = None
    consulting_tool_slug: str | None = None
    consulting_notes: list[str] = field(default_factory=list)

    def append(self, message: ChatMessage) -> None:
        self.messages.append(message)

    def ensure_charter_draft(self) -> CharterDraft:
        if self.charter_draft is None:
            self.charter_draft = CharterDraft()
        return self.charter_draft

    def ensure_risk_draft(self) -> RiskRegisterDraft:
        if self.risk_draft is None:
            self.risk_draft = RiskRegisterDraft()
        return self.risk_draft

    def ensure_decision_draft(self) -> DecisionDraft:
        if self.decision_draft is None:
            self.decision_draft = DecisionDraft()
        return self.decision_draft

    def ensure_matrix_draft(self) -> DecisionMatrixDraft:
        if self.matrix_draft is None:
            self.matrix_draft = DecisionMatrixDraft()
        return self.matrix_draft
