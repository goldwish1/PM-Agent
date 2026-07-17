"""draft_decision_matrix：维护决策矩阵草稿（准则/方案/打分）。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.agent.session import (
    MAX_MATRIX_CRITERIA,
    MAX_MATRIX_OPTIONS,
    PLACEHOLDER,
    DecisionMatrixDraft,
    MatrixCriterion,
    MatrixOption,
    SessionMode,
    SessionState,
)
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class CriterionInput(BaseModel):
    criterion_id: str | None = Field(default=None, description="准则 ID，如 C01")
    name: str | None = Field(default=None, description="准则名称")
    weight: str | None = Field(default=None, description="权重，如 30%")


class OptionInput(BaseModel):
    option_id: str | None = Field(default=None, description="方案 ID，如 O01")
    name: str | None = Field(default=None, description="方案名称")
    scores: dict[str, str] | None = Field(
        default=None,
        description="各准则得分，key 为 criterion_id",
    )
    weighted_total: str | None = Field(default=None, description="加权总分")


class DraftDecisionMatrixArgs(BaseModel):
    title: str | None = Field(default=None, description="决策矩阵标题")
    context: str | None = Field(default=None, description="背景与要决策的问题")
    recommended_option: str | None = Field(default=None, description="推荐方案")
    rationale: str | None = Field(default=None, description="推荐依据与权衡理由")
    criteria: list[CriterionInput] = Field(
        default_factory=list,
        description="要新增或按 criterion_id 更新的准则",
    )
    options: list[OptionInput] = Field(
        default_factory=list,
        description="要新增或按 option_id 更新的方案及打分",
    )
    replace_criteria: bool = Field(
        default=False,
        description="若为 true，用本次 criteria 替换全部准则",
    )
    replace_options: bool = Field(
        default=False,
        description="若为 true，用本次 options 替换全部方案",
    )
    reset: bool = Field(
        default=False,
        description="若为 true，先清空草稿再合并本次字段",
    )


def _merge_criterion(
    existing: MatrixCriterion | None,
    patch: CriterionInput,
    idx: int,
) -> MatrixCriterion:
    base = existing.model_dump() if existing else MatrixCriterion().model_dump()
    data = patch.model_dump(exclude_none=True)
    for key, value in data.items():
        text = str(value).strip()
        if text:
            base[key] = text
    if not base.get("criterion_id"):
        base["criterion_id"] = f"C{idx:02d}"
    return MatrixCriterion.model_validate(base)


def _merge_option(
    existing: MatrixOption | None,
    patch: OptionInput,
    idx: int,
) -> MatrixOption:
    base = existing.model_dump() if existing else MatrixOption().model_dump()
    data = patch.model_dump(exclude_none=True)
    scores_patch = data.pop("scores", None)
    for key, value in data.items():
        text = str(value).strip()
        if text:
            base[key] = text
    if scores_patch:
        merged_scores = dict(base.get("scores") or {})
        for cid, score in scores_patch.items():
            text = str(score).strip()
            if text:
                merged_scores[str(cid).strip()] = text
        base["scores"] = merged_scores
    if not base.get("option_id"):
        base["option_id"] = f"O{idx:02d}"
    return MatrixOption.model_validate(base)


def register_draft_decision_matrix(
    registry: ToolRegistry,
    state: SessionState,
) -> None:
    def _execute(args: DraftDecisionMatrixArgs) -> str:
        warning = ""
        if args.reset or state.matrix_draft is None:
            state.matrix_draft = DecisionMatrixDraft()

        draft = state.ensure_matrix_draft()
        flat_patch = args.model_dump(
            exclude={
                "reset",
                "criteria",
                "options",
                "replace_criteria",
                "replace_options",
            },
            exclude_none=True,
        )
        draft = draft.merge_patch(flat_patch)

        if args.replace_criteria:
            new_criteria: list[MatrixCriterion] = []
            for i, patch in enumerate(args.criteria, start=1):
                new_criteria.append(_merge_criterion(None, patch, i))
            if len(new_criteria) > MAX_MATRIX_CRITERIA:
                warning = (
                    f"MVP 建议准则不超过 {MAX_MATRIX_CRITERIA} 条；"
                    f"已截断为前 {MAX_MATRIX_CRITERIA} 条。"
                )
                new_criteria = new_criteria[:MAX_MATRIX_CRITERIA]
            draft = draft.model_copy(update={"criteria": new_criteria})
        elif args.criteria:
            criteria = list(draft.criteria)
            for patch in args.criteria:
                matched_idx = None
                if patch.criterion_id:
                    for i, existing in enumerate(criteria):
                        if existing.criterion_id == patch.criterion_id.strip():
                            matched_idx = i
                            break
                if matched_idx is not None:
                    criteria[matched_idx] = _merge_criterion(
                        criteria[matched_idx], patch, matched_idx + 1
                    )
                else:
                    if len(criteria) >= MAX_MATRIX_CRITERIA:
                        warning = (
                            f"错误指令：MVP 建议准则不超过 {MAX_MATRIX_CRITERIA} 条。"
                            "请先合并/删减后再新增，或 replace_criteria=true 重建。"
                        )
                        break
                    criteria.append(_merge_criterion(None, patch, len(criteria) + 1))
            draft = draft.model_copy(update={"criteria": criteria})

        if args.replace_options:
            new_options: list[MatrixOption] = []
            for i, patch in enumerate(args.options, start=1):
                new_options.append(_merge_option(None, patch, i))
            if len(new_options) > MAX_MATRIX_OPTIONS:
                warning = (
                    f"MVP 建议方案不超过 {MAX_MATRIX_OPTIONS} 个；"
                    f"已截断为前 {MAX_MATRIX_OPTIONS} 个。"
                )
                new_options = new_options[:MAX_MATRIX_OPTIONS]
            draft = draft.model_copy(update={"options": new_options})
        elif args.options:
            options = list(draft.options)
            for patch in args.options:
                matched_idx = None
                if patch.option_id:
                    for i, existing in enumerate(options):
                        if existing.option_id == patch.option_id.strip():
                            matched_idx = i
                            break
                if matched_idx is not None:
                    options[matched_idx] = _merge_option(
                        options[matched_idx], patch, matched_idx + 1
                    )
                else:
                    if len(options) >= MAX_MATRIX_OPTIONS:
                        warning = (
                            f"错误指令：MVP 建议方案不超过 {MAX_MATRIX_OPTIONS} 个。"
                            "请先合并/删减后再新增，或 replace_options=true 重建。"
                        )
                        break
                    options.append(_merge_option(None, patch, len(options) + 1))
            draft = draft.model_copy(update={"options": options})

        state.matrix_draft = draft
        state.mode = SessionMode.DRAFTING_DECISION_MATRIX

        has_notes = bool(state.consulting_notes)
        note = "预览后请用户确认，再调用 export_markdown(doc_type=decision_matrix)。"
        if has_notes:
            note = (
                "已有陪跑沉淀，应基于 consulting_notes 提炼准则/方案/打分而非空白追问。"
                + note
            )
        payload = {
            "ok": warning == "" or warning.startswith("MVP"),
            "preview": draft.preview_lines(),
            "criteria_count": len(draft.criteria),
            "options_count": len(draft.options),
            "warning": warning,
            "placeholder": PLACEHOLDER,
            "consulting_notes_available": has_notes,
            "note": note,
        }
        if has_notes:
            payload["consulting_notes"] = list(state.consulting_notes)
        return json.dumps(payload, ensure_ascii=False)

    registry.register(
        ToolSpec(
            name="draft_decision_matrix",
            description=(
                "起草/更新决策矩阵草稿：增量合并准则、方案与打分，返回终端预览摘要。"
                "仅用于决策矩阵；其他工具不可起草。"
            ),
            parameters_model=DraftDecisionMatrixArgs,
            execute=_execute,
            category="draft",
            pure=False,
        )
    )
