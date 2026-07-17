"""start_consulting：进入陪跑讨论态，返回工具 steps/scenarios 素材。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.registry import ToolRegistry, ToolSpec


class StartConsultingArgs(BaseModel):
    tool_slug: str = Field(
        description=(
            "可起草工具的 slug，例如 project-charter、risk-register、"
            "decision-matrix、decision-record"
        )
    )


def register_start_consulting(
    registry: ToolRegistry,
    repo: ToolsRepository,
    state: SessionState,
) -> None:
    def _execute(args: StartConsultingArgs) -> str:
        slug = args.tool_slug.strip()
        tool = repo.get_by_slug(slug)
        if tool is None:
            known = ", ".join(sorted(t.slug for t in repo.all())[:8])
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"未知 slug「{slug}」。不要编造库外工具。"
                        f"可先 search_tools；示例 slug：{known}…"
                    ),
                },
                ensure_ascii=False,
            )
        if not tool.draftable:
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"「{tool.name}」不支持陪跑讨论与自动起草。"
                        "本 MVP 仅支持项目章程、风险登记册、决策矩阵与决策记录；"
                        "可 get_tool_detail 查看说明，或改选可起草工具。"
                    ),
                    "draftable": False,
                    "slug": tool.slug,
                    "name": tool.name,
                },
                ensure_ascii=False,
            )

        state.mode = SessionMode.CONSULTING
        state.consulting_tool_slug = tool.slug
        payload = {
            "ok": True,
            "slug": tool.slug,
            "name": tool.name,
            "steps": tool.steps,
            "scenarios": tool.scenarios,
            "mode": state.mode.value,
            "note": (
                "已进入陪跑讨论。以下 steps/scenarios 仅作素材线索，"
                "请结合用户情境主动追问并给出个性化建议，禁止原样复述。"
                "讨论中获得有价值背景时调用 note_consulting_fact 沉淀。"
            ),
        }
        return json.dumps(payload, ensure_ascii=False)

    registry.register(
        ToolSpec(
            name="start_consulting",
            description=(
                "当用户对可起草工具（项目章程/风险登记册/决策矩阵/决策记录）"
                "表达「怎么用」或希望深入讨论使用思路时调用："
                "进入陪跑模式并返回步骤/场景素材。"
            ),
            parameters_model=StartConsultingArgs,
            execute=_execute,
            category="consult",
            pure=False,
        )
    )
