"""PM 工具库运营：候选池、质量门禁、AI 提示词与发布。"""

from __future__ import annotations

import json
import os
import tempfile
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from pm_agent.knowledge.categories import USE_CASE_ORDER, validate_use_cases
from pm_agent.knowledge.repo import PmTool, ToolsRepository


class CandidateStatus(StrEnum):
    """候选工具生命周期。"""

    INBOX = "inbox"
    DRAFTED = "drafted"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class QualityScore(BaseModel):
    """工具准入评分：五项各 0～2 分。"""

    trigger_clarity: int = Field(ge=0, le=2)
    actionability: int = Field(ge=0, le=2)
    output_clarity: int = Field(ge=0, le=2)
    boundary_clarity: int = Field(ge=0, le=2)
    recommendation_value: int = Field(ge=0, le=2)

    @property
    def total(self) -> int:
        return sum(self.model_dump().values())


class ToolCandidate(BaseModel):
    """尚未进入正式工具库的运营态候选。"""

    slug: str
    name: str
    family: str
    problem: str
    trigger_phrases: list[str] = Field(default_factory=list)
    differentiation: str
    proposed_use_cases: list[str] = Field(default_factory=list, min_length=1)
    status: CandidateStatus = CandidateStatus.INBOX
    quality_score: QualityScore | None = None
    review_notes: list[str] = Field(default_factory=list)
    tool: PmTool | None = None


def load_candidates(path: Path | str) -> list[ToolCandidate]:
    """读取并校验候选池。"""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"候选池文件不存在：{file_path}")
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("tool_candidates.json 根节点必须是数组")
    candidates = [ToolCandidate.model_validate(item) for item in raw]
    _ensure_unique_slugs(candidates, source="候选池")
    return candidates


def strict_tool_issues(tool: PmTool, *, trigger_phrases: list[str] | None = None) -> list[str]:
    """检查新工具是否达到可发布的内容厚度。"""
    issues: list[str] = []
    phrases = trigger_phrases if trigger_phrases is not None else tool.trigger_phrases

    for label in ("何时用：", "何时别用：", "常见坑："):
        if label not in tool.description:
            issues.append(f"description 缺少「{label}」")
    if not 5 <= len(tool.steps) <= 8:
        issues.append("steps 必须为 5～8 条")
    elif any("→" not in step for step in tool.steps):
        issues.append("每条 step 必须使用「动作 → 产出」格式")
    if not 6 <= len(tool.scenarios) <= 12:
        issues.append("scenarios 必须为 6～12 条")
    if tool.scenarios and not any(
        marker in scenario for scenario in tool.scenarios for marker in ("易混", "反例")
    ):
        issues.append("scenarios 至少需要一条易混或反例")
    if len({phrase.strip() for phrase in phrases if phrase.strip()}) < 3:
        issues.append("至少需要 3 条不重复的 trigger_phrases")
    return issues


def candidate_issues(
    candidate: ToolCandidate,
    repo: ToolsRepository,
    *,
    require_approved: bool = False,
) -> list[str]:
    """返回候选的全部质量问题；空列表表示通过。"""
    issues: list[str] = []
    try:
        validate_use_cases(candidate.proposed_use_cases, slug=candidate.slug)
    except ValueError as exc:
        issues.append(str(exc))

    exists = repo.exists(candidate.slug)
    if candidate.status == CandidateStatus.PUBLISHED:
        if not exists:
            issues.append("状态为 published，但正式工具库中不存在")
    elif exists:
        issues.append("slug 已存在于正式工具库")

    if candidate.tool is None:
        issues.append("缺少完整 tool 草案")
    else:
        if candidate.tool.slug != candidate.slug:
            issues.append("候选 slug 与 tool.slug 不一致")
        if candidate.tool.name != candidate.name:
            issues.append("候选 name 与 tool.name 不一致")
        if set(candidate.tool.use_cases) != set(candidate.proposed_use_cases):
            issues.append("proposed_use_cases 与 tool.use_cases 不一致")
        issues.extend(
            strict_tool_issues(candidate.tool, trigger_phrases=candidate.trigger_phrases)
        )

    if require_approved:
        if candidate.status != CandidateStatus.APPROVED:
            issues.append("发布前状态必须为 approved")
        if candidate.quality_score is None:
            issues.append("发布前必须完成质量评分")
        elif candidate.quality_score.total < 8:
            issues.append("质量评分必须达到 8/10")
    return issues


def validate_catalog(
    candidates: list[ToolCandidate],
    repo: ToolsRepository,
) -> dict[str, list[str]]:
    """校验整个候选池，返回 slug -> 问题列表。"""
    result: dict[str, list[str]] = {}
    for candidate in candidates:
        issues = candidate_issues(candidate, repo)
        if issues:
            result[candidate.slug] = issues
    return result


def build_generation_prompt(
    *,
    family: str,
    count: int,
    repo: ToolsRepository,
    candidates: list[ToolCandidate],
) -> str:
    """生成可交给任意 AI 的、带仓库上下文的候选生成提示词。"""
    existing = "\n".join(
        f"- {tool.slug}｜{tool.name}｜{tool.summary}" for tool in repo.all()
    )
    pending = "\n".join(
        f"- {item.slug}｜{item.name}｜{item.status.value}" for item in candidates
    ) or "- 无"
    use_cases = "、".join(USE_CASE_ORDER)
    return f"""你是 pmbox 的 PM 工具库编辑器。请生成 {count} 个“{family}”家族的高实用性候选工具。

目标不是介绍理论，而是让项目经理遇到真实卡点后，10 分钟内可以开始使用。

## 硬性约束
1. 仅输出合法 JSON 数组，不要 Markdown 代码围栏或解释。
2. 每个对象必须符合 ToolCandidate 结构，status 固定为 drafted，quality_score 为 null。
3. tool 必须是完整正式条目，包含 slug/name/name_en/summary/description/steps/scenarios，
    以及 draftable/use_cases/trigger_phrases。
4. description 必须同时包含“何时用：”“何时别用：”“常见坑：”。
5. steps 为 5～8 条，每条严格使用“动作 → 产出”格式。
6. scenarios 为 6～12 条口语场景，至少含一条标注“易混”或“反例”的边界场景。
7. trigger_phrases 至少 3 条，必须像用户会说出的原话，而不是分类关键词。
8. use_cases 只能从以下集合选择：{use_cases}。
9. 默认 draftable=false；只有已存在专用 draft_* 实现时才可设为 true。
10. 禁止复制、改名或轻微改写现有工具；differentiation 必须说明与最近邻工具的边界。

## 候选对象字段
slug, name, family, problem, trigger_phrases, differentiation, proposed_use_cases,
status, quality_score, review_notes, tool。

## 已发布工具（必须去重）
{existing}

## 候选池已有工具（必须去重）
{pending}
"""


def ingest_candidates(
    pool_path: Path | str,
    incoming_path: Path | str,
) -> list[ToolCandidate]:
    """将 AI 生成的候选合并到候选池；拒绝重复和越权状态。"""
    pool = load_candidates(pool_path)
    incoming = load_candidates(incoming_path)
    known = {item.slug for item in pool}
    duplicates = sorted({item.slug for item in incoming if item.slug in known})
    if duplicates:
        raise ValueError(f"候选 slug 已存在：{duplicates}")
    forbidden = [
        item.slug
        for item in incoming
        if item.status not in (CandidateStatus.INBOX, CandidateStatus.DRAFTED)
    ]
    if forbidden:
        raise ValueError(f"导入候选不得预设为已批准/已发布：{forbidden}")
    merged = [*pool, *incoming]
    _ensure_unique_slugs(merged, source="合并后的候选池")
    write_candidates(pool_path, merged)
    return merged


def review_candidate(
    pool_path: Path | str,
    tools_path: Path | str,
    slug: str,
    score: QualityScore,
    *,
    approve: bool = False,
    note: str = "",
) -> ToolCandidate:
    """记录评分；批准时强制执行内容门禁。"""
    candidates = load_candidates(pool_path)
    repo = ToolsRepository.from_json_path(tools_path)
    index = _candidate_index(candidates, slug)
    candidate = candidates[index]
    notes = [*candidate.review_notes]
    if note.strip():
        notes.append(note.strip())
    status = CandidateStatus.APPROVED if approve else CandidateStatus.REVIEW
    updated = candidate.model_copy(
        update={"quality_score": score, "review_notes": notes, "status": status}
    )
    if approve:
        issues = candidate_issues(updated, repo, require_approved=True)
        if issues:
            raise ValueError(_format_issues(slug, issues))
    candidates[index] = updated
    write_candidates(pool_path, candidates)
    return updated


def promote_candidate(
    pool_path: Path | str,
    tools_path: Path | str,
    slug: str,
    *,
    dry_run: bool = False,
) -> PmTool:
    """发布单个已批准候选；dry-run 只校验不写盘。"""
    candidates = load_candidates(pool_path)
    repo = ToolsRepository.from_json_path(tools_path)
    index = _candidate_index(candidates, slug)
    candidate = candidates[index]
    issues = candidate_issues(candidate, repo, require_approved=True)
    if issues:
        raise ValueError(_format_issues(slug, issues))
    assert candidate.tool is not None
    tool = candidate.tool.model_copy(
        update={"trigger_phrases": list(candidate.trigger_phrases)}
    )
    if dry_run:
        return tool

    tools_file = Path(tools_path)
    pool_file = Path(pool_path)
    raw_tools = json.loads(tools_file.read_text(encoding="utf-8"))
    raw_tools.append(tool.model_dump(exclude_none=True))
    candidates[index] = candidate.model_copy(update={"status": CandidateStatus.PUBLISHED})

    original_tools = tools_file.read_text(encoding="utf-8")
    _atomic_write_json(tools_file, raw_tools)
    try:
        write_candidates(pool_file, candidates)
    except Exception:
        tools_file.write_text(original_tools, encoding="utf-8")
        raise
    return tool


def write_candidates(path: Path | str, candidates: list[ToolCandidate]) -> None:
    """稳定格式写回候选池。"""
    _atomic_write_json(
        Path(path),
        [item.model_dump(mode="json", exclude_none=True) for item in candidates],
    )


def _candidate_index(candidates: list[ToolCandidate], slug: str) -> int:
    for index, candidate in enumerate(candidates):
        if candidate.slug == slug:
            return index
    raise ValueError(f"候选池中不存在 slug「{slug}」")


def _ensure_unique_slugs(items: list[ToolCandidate], *, source: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item.slug in seen:
            duplicates.add(item.slug)
        seen.add(item.slug)
    if duplicates:
        raise ValueError(f"{source}存在重复 slug：{sorted(duplicates)}")


def _format_issues(slug: str, issues: list[str]) -> str:
    return f"候选「{slug}」未通过质量门禁：" + "；".join(issues)


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
