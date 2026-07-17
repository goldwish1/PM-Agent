"""陪跑咨询类 Agent 工具：进入讨论 / 沉淀事实。"""

from pm_agent.tools.consult.note_fact import register_note_consulting_fact
from pm_agent.tools.consult.start_consulting import register_start_consulting

__all__ = [
    "register_note_consulting_fact",
    "register_start_consulting",
]
