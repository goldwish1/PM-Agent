"""draft_risk_register：维护 1～3 条风险登记册草稿。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.agent.session import (
    MAX_RISK_ITEMS,
    PLACEHOLDER,
    RiskItem,
    RiskRegisterDraft,
    SessionMode,
    SessionState,
)
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class RiskItemInput(BaseModel):
    risk_id: str | None = Field(default=None, description="风险 ID，如 R01")
    description: str | None = Field(default=None, description="风险描述")
    cause: str | None = Field(default=None, description="原因")
    probability: str | None = Field(default=None, description="概率（高/中/低或数值）")
    impact: str | None = Field(default=None, description="影响（高/中/低或数值）")
    score: str | None = Field(default=None, description="评分")
    response: str | None = Field(default=None, description="应对策略")
    owner: str | None = Field(default=None, description="责任人")
    status: str | None = Field(default=None, description="状态")


class DraftRiskRegisterArgs(BaseModel):
    items: list[RiskItemInput] = Field(
        default_factory=list,
        description="要新增或按 risk_id 更新的风险条目",
    )
    replace_all: bool = Field(
        default=False,
        description="若为 true，用本次 items 替换整个登记册",
    )
    clear: bool = Field(default=False, description="清空全部条目")


def _merge_item(existing: RiskItem | None, patch: RiskItemInput, idx: int) -> RiskItem:
    base = existing.model_dump() if existing else RiskItem().model_dump()
    data = patch.model_dump(exclude_none=True)
    for key, value in data.items():
        text = str(value).strip()
        if text:
            base[key] = text
    if not base.get("risk_id"):
        base["risk_id"] = f"R{idx:02d}"
    return RiskItem.model_validate(base)


def register_draft_risk_register(
    registry: ToolRegistry,
    state: SessionState,
) -> None:
    def _execute(args: DraftRiskRegisterArgs) -> str:
        warning = ""
        if args.clear:
            state.risk_draft = RiskRegisterDraft(items=[])
            state.mode = SessionMode.DRAFTING_RISK
            return json.dumps(
                {
                    "ok": True,
                    "preview": ["（已清空）"],
                    "count": 0,
                    "note": "风险登记册已清空。可继续添加 1～3 条。",
                },
                ensure_ascii=False,
            )

        draft = state.ensure_risk_draft()

        if args.replace_all:
            new_items: list[RiskItem] = []
            for i, patch in enumerate(args.items, start=1):
                new_items.append(_merge_item(None, patch, i))
            if len(new_items) > MAX_RISK_ITEMS:
                warning = (
                    f"MVP 请先保留 1～{MAX_RISK_ITEMS} 条；"
                    f"已截断为前 {MAX_RISK_ITEMS} 条。"
                )
                new_items = new_items[:MAX_RISK_ITEMS]
            draft = RiskRegisterDraft(items=new_items)
        else:
            items = list(draft.items)
            for patch in args.items:
                matched_idx = None
                if patch.risk_id:
                    for i, existing in enumerate(items):
                        if existing.risk_id == patch.risk_id.strip():
                            matched_idx = i
                            break
                if matched_idx is not None:
                    items[matched_idx] = _merge_item(
                        items[matched_idx], patch, matched_idx + 1
                    )
                else:
                    if len(items) >= MAX_RISK_ITEMS:
                        warning = (
                            f"错误指令：MVP 请先保留 1～{MAX_RISK_ITEMS} 条。"
                            "请先合并/删减后再新增，或 replace_all=true 重建。"
                        )
                        break
                    items.append(_merge_item(None, patch, len(items) + 1))
            draft = RiskRegisterDraft(items=items)

        state.risk_draft = draft
        state.mode = SessionMode.DRAFTING_RISK
        has_notes = bool(state.consulting_notes)
        note = "预览后请用户确认，再调用 export_markdown(doc_type=risk_register)。"
        if has_notes:
            note = (
                "已有陪跑沉淀，应基于 consulting_notes 提炼条目而非空白追问。"
                + note
            )
        payload = {
            "ok": warning == "" or warning.startswith("MVP"),
            "preview": draft.preview_lines(),
            "count": len(draft.items),
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
            name="draft_risk_register",
            description=(
                "起草/更新风险登记册：按条目 upsert，MVP 建议 1～3 条。"
                "超过 3 条会拒绝新增或截断并提示。"
            ),
            parameters_model=DraftRiskRegisterArgs,
            execute=_execute,
            category="draft",
            pure=False,
        )
    )
