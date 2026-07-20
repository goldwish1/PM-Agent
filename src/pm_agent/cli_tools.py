"""CLI /tools：只读浏览知识库（目录 / 详情 / 搜索）。"""

from __future__ import annotations

from collections import defaultdict

from pm_agent.knowledge.categories import format_use_cases_label
from pm_agent.knowledge.repo import PmTool, ToolsRepository


def is_tools_command(raw: str) -> bool:
    """识别 /tools 或 /tools <参数>（避免误伤其它指令）。"""
    return raw == "/tools" or raw.startswith("/tools ")


def parse_tools_arg(raw: str) -> str:
    """取出 /tools 后的参数；无参返回空串。"""
    if raw == "/tools":
        return ""
    if raw.startswith("/tools "):
        return raw[len("/tools ") :].strip()
    return ""


def format_tools_reply(repo: ToolsRepository, raw: str) -> str:
    """根据 /tools 输入生成完整回复文本。"""
    arg = parse_tools_arg(raw)
    if not arg:
        return format_tools_catalog(repo)
    hit = repo.get_by_slug(arg)
    if hit is not None:
        return format_tool_detail(hit)
    return format_tools_search(repo, arg)


def format_tools_catalog(repo: ToolsRepository) -> str:
    """按实用场景列出全部工具（Markdown，供 Rich 渲染）。"""
    by_case: dict[str, list[PmTool]] = defaultdict(list)
    for tool in repo.all():
        for use_case in tool.use_cases:
            by_case[use_case].append(tool)

    lines: list[str] = [f"知识库工具共 {len(repo)} 个（按实用场景）：", ""]
    for use_case in repo.use_case_display_order():
        tools = by_case.get(use_case)
        if not tools:
            continue
        unique = sorted({t.slug: t for t in tools}.values(), key=lambda t: t.slug)
        lines.append(f"## {use_case}（{len(unique)}）")
        lines.append("")
        for tool in unique:
            draft = " · draftable" if tool.draftable else ""
            lines.append(f"- `{tool.slug}`  {tool.name}{draft}")
        lines.append("")
    lines.append("提示：`/tools <slug>` 看详情；`/tools <关键词>` 本地搜索。")
    return "\n".join(lines).rstrip() + "\n"


def format_tool_detail(tool: PmTool) -> str:
    """打印单条工具完整字段（Markdown）。"""
    use_cases = format_use_cases_label(tool.use_cases)
    if tool.steps:
        steps = "\n".join(f"- {s}" for s in tool.steps)
    else:
        steps = "- （无）"
    if tool.scenarios:
        scenarios = "\n".join(f"- {s}" for s in tool.scenarios)
    else:
        scenarios = "- （无）"
    return (
        f"## `{tool.slug}` · {tool.name}\n"
        f"\n"
        f"- **name_en**: {tool.name_en or '（无）'}\n"
        f"- **use_cases**: {use_cases}\n"
        f"- **draftable**: {tool.draftable}\n"
        f"\n"
        f"### summary\n"
        f"\n"
        f"{tool.summary or '（无）'}\n"
        f"\n"
        f"### description\n"
        f"\n"
        f"{tool.description or '（无）'}\n"
        f"\n"
        f"### steps\n"
        f"\n"
        f"{steps}\n"
        f"\n"
        f"### scenarios\n"
        f"\n"
        f"{scenarios}\n"
    )


def format_tools_search(repo: ToolsRepository, keyword: str) -> str:
    """关键词搜索摘要列表（Markdown）。"""
    hits = repo.search(keyword, limit=12)
    if not hits:
        return f"未找到与「{keyword}」匹配的工具。可用 `/tools` 查看全部。\n"
    lines: list[str] = [f"搜索「{keyword}」命中 {len(hits)} 条：", ""]
    for tool in hits:
        draft = " · draftable" if tool.draftable else ""
        cases = format_use_cases_label(tool.use_cases)
        lines.append(f"- `{tool.slug}`  {tool.name}  [{cases}]{draft}")
        if tool.summary:
            lines.append(f"  {tool.summary}")
    lines.append("")
    lines.append("提示：`/tools <slug>` 查看完整字段。")
    return "\n".join(lines).rstrip() + "\n"
