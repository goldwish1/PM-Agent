"""工具推荐离线评测的数据模型。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CaseType(StrEnum):
    """黄金用例类型。"""

    TYPICAL = "typical"
    PARAPHRASE = "paraphrase"
    BOUNDARY = "boundary"
    NEGATIVE = "negative"


class EvaluationCase(BaseModel):
    """一条工具推荐黄金用例。"""

    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    context: str = ""
    family: str = Field(min_length=1)
    case_type: CaseType
    critical: bool = False
    acceptable_top1: list[str] = Field(default_factory=list)
    required_top3: list[str] = Field(default_factory=list)
    forbidden_top3: list[str] = Field(default_factory=list)
    requires_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_expectations(self) -> EvaluationCase:
        if not (self.acceptable_top1 or self.required_top3 or self.forbidden_top3):
            raise ValueError("至少需要 acceptable_top1、required_top3 或 forbidden_top3")
        return self

    @property
    def relevant_tools(self) -> set[str]:
        return set(self.acceptable_top1) | set(self.required_top3)


class CaseResult(BaseModel):
    """单条用例的实际排名与判定。"""

    case_id: str
    query: str
    family: str
    case_type: CaseType
    critical: bool
    active: bool
    skipped_reason: str = ""
    rankings: list[str] = Field(default_factory=list)
    top1_pass: bool | None = None
    top3_pass: bool | None = None
    reciprocal_rank: float | None = None
    forbidden_hits: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        if not self.active:
            return True
        checks = [value for value in (self.top1_pass, self.top3_pass) if value is not None]
        return all(checks) and not self.forbidden_hits


class EvaluationSummary(BaseModel):
    """一轮评测的聚合指标。"""

    total_cases: int
    active_cases: int
    skipped_cases: int
    top1_cases: int
    top1_passed: int
    top1_accuracy: float
    top3_cases: int
    top3_passed: int
    top3_recall: float
    mrr_cases: int
    mrr: float
    forbidden_cases: int
    forbidden_violations: int
    forbidden_violation_rate: float
    confusion: dict[str, int] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    """可持久化且可作为基线的一轮评测报告。"""

    dataset_digest: str
    tools_digest: str
    summary: EvaluationSummary
    results: list[CaseResult]


class CaseChangeKind(StrEnum):
    """同一用例在两个版本间的变化类型。"""

    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED_NEUTRAL = "changed-neutral"
    UNCHANGED = "unchanged"
    NEWLY_ACTIVATED = "newly-activated"
    SKIPPED = "skipped"


class CaseChange(BaseModel):
    """一条用例的版本差异。"""

    case_id: str
    query: str
    critical: bool
    kind: CaseChangeKind
    before_rankings: list[str] = Field(default_factory=list)
    after_rankings: list[str] = Field(default_factory=list)
    before_passed: bool
    after_passed: bool
    new_forbidden_hits: list[str] = Field(default_factory=list)


class ComparisonReport(BaseModel):
    """当前版本与候选版本的完整差异。"""

    before: EvaluationSummary
    after: EvaluationSummary
    changes: list[CaseChange]


class GateSeverity(StrEnum):
    """回归门禁问题级别。"""

    BLOCKING = "blocking"
    WARNING = "warning"


class GateIssue(BaseModel):
    """一条发布门禁问题。"""

    code: str
    message: str
    severity: GateSeverity
    case_id: str | None = None


class GateResult(BaseModel):
    """发布门禁判定。"""

    passed: bool
    issues: list[GateIssue] = Field(default_factory=list)
