"""note_consulting_fact：在陪跑讨论中沉淀结构化事实。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class NoteConsultingFactArgs(BaseModel):
    fact: str = Field(
        description=(
            "简洁的关键项目事实，例如「预算约 50 万，需在 8 月底前完成立项」"
        )
    )


def register_note_consulting_fact(
    registry: ToolRegistry,
    state: SessionState,
) -> None:
    def _execute(args: NoteConsultingFactArgs) -> str:
        fact = args.fact.strip()
        if not fact:
            return json.dumps(
                {
                    "ok": False,
                    "error": "fact 不能为空。",
                },
                ensure_ascii=False,
            )
        if state.mode != SessionMode.CONSULTING:
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        "当前不在陪跑讨论（CONSULTING）模式，无法沉淀事实。"
                        "请先对可起草工具调用 start_consulting。"
                    ),
                    "mode": state.mode.value,
                },
                ensure_ascii=False,
            )

        state.consulting_notes.append(fact)
        return json.dumps(
            {
                "ok": True,
                "notes_count": len(state.consulting_notes),
                "consulting_notes": list(state.consulting_notes),
            },
            ensure_ascii=False,
        )

    registry.register(
        ToolSpec(
            name="note_consulting_fact",
            description=(
                "陪跑讨论中，当获得有价值的项目背景信息时调用，"
                "结构化沉淀事实供后续起草提炼字段使用。"
            ),
            parameters_model=NoteConsultingFactArgs,
            execute=_execute,
            category="consult",
            pure=False,
        )
    )
