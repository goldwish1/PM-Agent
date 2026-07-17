"""draft_decision_record：合并决策记录草稿并返回预览摘要。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.agent.session import (
    PLACEHOLDER,
    DecisionDraft,
    SessionMode,
    SessionState,
)
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class DraftDecisionRecordArgs(BaseModel):
    """字段皆可选：增量合并；空值不覆盖。"""

    decision_title: str | None = Field(default=None, description="决策标题")
    context: str | None = Field(default=None, description="背景与问题陈述")
    options_considered: str | None = Field(
        default=None, description="考虑过的备选方案"
    )
    decision: str | None = Field(default=None, description="最终决定")
    rationale: str | None = Field(default=None, description="决策依据与权衡理由")
    consequences: str | None = Field(default=None, description="预期影响与后果")
    decision_maker: str | None = Field(default=None, description="决策人")
    decision_date: str | None = Field(default=None, description="决策日期")
    status: str | None = Field(default=None, description="状态（拟定/已生效/已废弃）")
    reset: bool = Field(
        default=False,
        description="若为 true，先清空为全「待补充」再合并本次字段",
    )


def register_draft_decision_record(
    registry: ToolRegistry,
    state: SessionState,
) -> None:
    def _execute(args: DraftDecisionRecordArgs) -> str:
        if args.reset or state.decision_draft is None:
            state.decision_draft = DecisionDraft()

        patch = args.model_dump(exclude={"reset"}, exclude_none=True)
        state.decision_draft = state.ensure_decision_draft().merge_patch(patch)
        state.mode = SessionMode.DRAFTING_DECISION

        draft = state.decision_draft
        missing = draft.missing_fields()
        has_notes = bool(state.consulting_notes)
        note = (
            "缺字段可用「待补充」占位，不阻塞导出。"
            "预览后请用户确认，再调用 export_markdown(doc_type=decision)。"
            if missing
            else "关键字段已基本齐全。请先向用户展示预览，"
            "用户确认后再 export_markdown。"
        )
        if has_notes:
            note = (
                "已有陪跑沉淀，应基于 consulting_notes 提炼字段而非空白追问。"
                + note
            )
        payload = {
            "ok": True,
            "preview": draft.preview_lines(),
            "missing_fields": missing,
            "consulting_notes_available": has_notes,
            "note": note,
            "placeholder": PLACEHOLDER,
        }
        if has_notes:
            payload["consulting_notes"] = list(state.consulting_notes)
        return json.dumps(payload, ensure_ascii=False)

    registry.register(
        ToolSpec(
            name="draft_decision_record",
            description=(
                "起草/更新决策记录草稿：增量合并字段并返回终端预览摘要。"
                "仅用于决策记录；其他工具不可起草。"
            ),
            parameters_model=DraftDecisionRecordArgs,
            execute=_execute,
            category="draft",
            pure=False,
        )
    )
