"""CLI /tools：只读浏览知识库（目录 / 详情 / 搜索）。"""

from __future__ import annotations

from collections import defaultdict

from pm_agent.knowledge.repo import PmTool, ToolsRepository

PROCESS_GROUP_ORDER: tuple[str, ...] = ("启动", "规划", "执行", "监控", "收尾")


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
    """按过程组列出全部工具。"""
    by_group: dict[str, list[PmTool]] = defaultdict(list)
    for tool in repo.all():
        group = tool.process_group or "未分类"
        by_group[group].append(tool)

    lines: list[str] = [f"知识库工具共 {len(repo)} 个：", ""]
    ordered_groups = [g for g in PROCESS_GROUP_ORDER if g in by_group]
    extra = sorted(g for g in by_group if g not in PROCESS_GROUP_ORDER)
    for group in ordered_groups + extra:
        tools = sorted(by_group[group], key=lambda t: t.slug)
        lines.append(f"## {group}（{len(tools)}）")
        for tool in tools:
            draft = " · draftable" if tool.draftable else ""
            lines.append(f"  {tool.slug}  {tool.name}{draft}")
        lines.append("")
    lines.append("提示：/tools <slug> 看详情；/tools <关键词> 本地搜索。")
    return "\n".join(lines).rstrip() + "\n"


def format_tool_detail(tool: PmTool) -> str:
    """打印单条工具完整字段。"""
    steps = "\n".join(f"  - {s}" for s in tool.steps) or "  （无）"
    scenarios = "\n".join(f"  - {s}" for s in tool.scenarios) or "  （无）"
    return (
        f"slug: {tool.slug}\n"
        f"name: {tool.name}\n"
        f"name_en: {tool.name_en}\n"
        f"process_group: {tool.process_group}\n"
        f"knowledge_area: {tool.knowledge_area}\n"
        f"draftable: {tool.draftable}\n"
        f"summary: {tool.summary}\n"
        f"description: {tool.description}\n"
        f"steps:\n{steps}\n"
        f"scenarios:\n{scenarios}\n"
    )


def format_tools_search(repo: ToolsRepository, keyword: str) -> str:
    """关键词搜索摘要列表。"""
    hits = repo.search(keyword, limit=12)
    if not hits:
        return f"未找到与「{keyword}」匹配的工具。可用 /tools 查看全部。\n"
    lines: list[str] = [f"搜索「{keyword}」命中 {len(hits)} 条：", ""]
    for tool in hits:
        draft = " · draftable" if tool.draftable else ""
        lines.append(
            f"  {tool.slug}  {tool.name}  [{tool.process_group}/{tool.knowledge_area}]"
            f"{draft}"
        )
        if tool.summary:
            lines.append(f"    {tool.summary}")
    lines.append("")
    lines.append("提示：/tools <slug> 查看完整字段。")
    return "\n".join(lines).rstrip() + "\n"
