"""组装并注册阶段可用的 Agent 工具。"""

from __future__ import annotations

from pathlib import Path

from pm_agent.agent.session import SessionState
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.demo import register_demo_tools
from pm_agent.tools.detail import register_get_tool_detail
from pm_agent.tools.draft_charter import register_draft_project_charter
from pm_agent.tools.draft_risk import register_draft_risk_register
from pm_agent.tools.export_md import register_export_markdown
from pm_agent.tools.recommend import register_recommend_tools
from pm_agent.tools.registry import ToolRegistry
from pm_agent.tools.search import register_search_tools


def build_registry(
    repo: ToolsRepository,
    *,
    session: SessionState,
    output_dir: Path,
    include_demo_tools: bool = True,
) -> ToolRegistry:
    """注册知识库 + 起草/导出工具；可选保留 echo/add。"""
    registry = ToolRegistry()
    register_search_tools(registry, repo)
    register_get_tool_detail(registry, repo)
    register_recommend_tools(registry, repo)
    register_draft_project_charter(registry, session)
    register_draft_risk_register(registry, session)
    register_export_markdown(registry, session, output_dir)
    if include_demo_tools:
        register_demo_tools(registry)
    return registry


def build_registry_from_path(
    tools_json_path: Path | str,
    *,
    session: SessionState,
    output_dir: Path,
    include_demo_tools: bool = True,
) -> tuple[ToolRegistry, ToolsRepository]:
    repo = ToolsRepository.from_json_path(tools_json_path)
    return (
        build_registry(
            repo,
            session=session,
            output_dir=Path(output_dir),
            include_demo_tools=include_demo_tools,
        ),
        repo,
    )
