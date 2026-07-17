"""起草类 Agent 工具：项目章程 / 风险登记册 / 决策记录 / 决策矩阵。"""

from pm_agent.tools.draft.charter import register_draft_project_charter
from pm_agent.tools.draft.decision import register_draft_decision_record
from pm_agent.tools.draft.matrix import register_draft_decision_matrix
from pm_agent.tools.draft.risk import register_draft_risk_register

__all__ = [
    "register_draft_project_charter",
    "register_draft_risk_register",
    "register_draft_decision_record",
    "register_draft_decision_matrix",
]
