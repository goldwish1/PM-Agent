"""draft_project_charter：合并项目章程草稿并返回预览摘要。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.agent.session import (
    PLACEHOLDER,
    CharterDraft,
    SessionMode,
    SessionState,
)
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class DraftProjectCharterArgs(BaseModel):
    """字段皆可选：增量合并；空值不覆盖。"""

    project_name: str | None = Field(default=None, description="项目名称")
    sponsor: str | None = Field(default=None, description="发起人")
    project_manager: str | None = Field(default=None, description="项目经理")
    business_case: str | None = Field(default=None, description="商业论证")
    high_level_scope: str | None = Field(default=None, description="高层级范围")
    milestones: str | None = Field(default=None, description="主要里程碑")
    budget: str | None = Field(default=None, description="预算概览")
    risks: str | None = Field(default=None, description="主要风险（高层）")
    signature: str | None = Field(default=None, description="签字栏")
    reset: bool = Field(
        default=False,
        description="若为 true，先清空为全「待补充」再合并本次字段",
    )


def register_draft_project_charter(
    registry: ToolRegistry,
    state: SessionState,
) -> None:
    def _execute(args: DraftProjectCharterArgs) -> str:
        if args.reset or state.charter_draft is None:
            state.charter_draft = CharterDraft()

        patch = args.model_dump(exclude={"reset"}, exclude_none=True)
        state.charter_draft = state.ensure_charter_draft().merge_patch(patch)
        state.mode = SessionMode.DRAFTING_CHARTER

        draft = state.charter_draft
        missing = draft.missing_fields()
        payload = {
            "ok": True,
            "preview": draft.preview_lines(),
            "missing_fields": missing,
            "note": (
                "缺字段可用「待补充」占位，不阻塞导出。"
                "预览后请用户确认，再调用 export_markdown(doc_type=charter)。"
                if missing
                else "关键字段已基本齐全。请先向用户展示预览，"
                "用户确认后再 export_markdown。"
            ),
            "placeholder": PLACEHOLDER,
        }
        return json.dumps(payload, ensure_ascii=False)

    registry.register(
        ToolSpec(
            name="draft_project_charter",
            description=(
                "起草/更新项目章程草稿：增量合并字段并返回终端预览摘要。"
                "仅用于项目章程；其他工具不可起草。"
            ),
            parameters_model=DraftProjectCharterArgs,
            execute=_execute,
            category="draft",
            pure=False,
        )
    )
