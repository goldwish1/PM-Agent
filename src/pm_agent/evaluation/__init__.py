"""pmbox 工具推荐离线评测。"""

from pm_agent.evaluation.comparison import compare_reports
from pm_agent.evaluation.dataset import load_evaluation_cases
from pm_agent.evaluation.gates import evaluate_baseline_gate, evaluate_regression_gate
from pm_agent.evaluation.runner import run_evaluation

__all__ = [
    "compare_reports",
    "evaluate_baseline_gate",
    "evaluate_regression_gate",
    "load_evaluation_cases",
    "run_evaluation",
]
