"""cli_tools：/tools 目录 / 详情 / 搜索格式化。"""

from __future__ import annotations

from conftest import sample_trigger_rules
from pm_agent.cli_tools import (
    format_tool_detail,
    format_tools_catalog,
    format_tools_reply,
    format_tools_search,
    is_tools_command,
    parse_tools_arg,
)
from pm_agent.knowledge.repo import PmTool, ToolsRepository


def _sample_repo() -> ToolsRepository:
    return ToolsRepository(
        [
            PmTool(
                slug="project-charter",
                name="项目章程",
                name_en="Project Charter",
                use_cases=["立项与授权"],
                summary="正式授权项目",
                description="立项授权核心依据。",
                steps=["明确目的", "获得签字"],
                scenarios=["项目启动", "下周要立项"],
                trigger_match_rules=sample_trigger_rules("下周要立项"),
                draftable=True,
            ),
            PmTool(
                slug="risk-register",
                name="风险登记册",
                name_en="Risk Register",
                use_cases=["风险与问题"],
                summary="记录并跟踪风险",
                description="识别与应对风险。",
                steps=["识别风险", "评估影响"],
                scenarios=["担心延期", "风险很多"],
                trigger_match_rules=sample_trigger_rules("担心延期"),
                draftable=True,
            ),
            PmTool(
                slug="status-report",
                name="项目状态报告",
                name_en="Status Report",
                use_cases=["沟通与汇报"],
                summary="同步项目状态",
                description="周报式状态同步。",
                steps=["汇总进度", "标出风险"],
                scenarios=["要写周报"],
                trigger_match_rules=sample_trigger_rules("要写周报"),
                draftable=False,
            ),
        ]
    )


def test_is_tools_command() -> None:
    assert is_tools_command("/tools")
    assert is_tools_command("/tools project-charter")
    assert is_tools_command("/tools 立项")
    assert not is_tools_command("/tool")
    assert not is_tools_command("/toolshed")
    assert not is_tools_command("/help")


def test_parse_tools_arg() -> None:
    assert parse_tools_arg("/tools") == ""
    assert parse_tools_arg("/tools project-charter") == "project-charter"
    assert parse_tools_arg("/tools  立项  ") == "立项"


def test_format_catalog_groups_by_use_case_and_draftable() -> None:
    text = format_tools_catalog(_sample_repo())
    assert "知识库工具共 3 个（按实用场景）" in text
    assert "## 立项与授权（1）" in text
    assert "## 风险与问题（1）" in text
    assert "## 沟通与汇报（1）" in text
    assert "- `project-charter`  项目章程 · draftable" in text
    assert "- `status-report`  项目状态报告" in text
    assert "· draftable" in text
    assert "`status-report`  项目状态报告 · draftable" not in text


def test_format_detail_by_slug() -> None:
    repo = _sample_repo()
    text = format_tools_reply(repo, "/tools project-charter")
    assert "## `project-charter` · 项目章程" in text
    assert "**use_cases**: 立项与授权" in text
    assert "**draftable**: True" in text
    assert "正式授权项目" in text
    assert "明确目的" in text
    assert "下周要立项" in text
    assert "process_group" not in text


def test_format_search_by_keyword() -> None:
    repo = _sample_repo()
    text = format_tools_reply(repo, "/tools 立项")
    assert "搜索「立项」" in text
    assert "`project-charter`" in text
    assert "[立项与授权]" in text


def test_format_search_no_hit() -> None:
    text = format_tools_search(_sample_repo(), "宇宙飞船")
    assert "未找到与「宇宙飞船」匹配的工具" in text


def test_format_tool_detail_empty_lists() -> None:
    tool = PmTool(
        slug="x",
        name="空",
        use_cases=["范围与需求"],
        steps=[],
        scenarios=[],
        trigger_match_rules=sample_trigger_rules("空"),
    )
    text = format_tool_detail(tool)
    assert "### steps\n\n- （无）" in text
    assert "### scenarios\n\n- （无）" in text
