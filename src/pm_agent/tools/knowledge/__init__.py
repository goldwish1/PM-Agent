"""知识库类 Agent 工具：检索 / 推荐 / 详情。"""

from pm_agent.tools.knowledge.detail import register_get_tool_detail
from pm_agent.tools.knowledge.recommend import register_recommend_tools
from pm_agent.tools.knowledge.search import register_search_tools

__all__ = [
    "register_get_tool_detail",
    "register_recommend_tools",
    "register_search_tools",
]
