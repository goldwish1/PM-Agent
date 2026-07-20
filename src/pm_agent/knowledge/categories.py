"""工具库实用场景分类（唯一运行时分类维度）。"""

from __future__ import annotations

# id -> 显示名
USE_CASE_BY_ID: dict[str, str] = {
    "charter": "立项与授权",
    "scope": "范围与需求",
    "schedule": "进度与排期",
    "cost": "成本与预算",
    "risk": "风险与问题",
    "stakeholder": "干系人与协作",
    "communication": "沟通与汇报",
    "decision": "决策与分析",
    "change": "变更与管控",
    "closure": "收尾与复盘",
    "reference": "流程规范（参考）",
}

USE_CASE_ORDER: tuple[str, ...] = tuple(USE_CASE_BY_ID.values())

VALID_USE_CASES: frozenset[str] = frozenset(USE_CASE_ORDER)

# keyword_boost 语义场景 -> 期望 use_case 显示名（用于一致性测试）
BOOST_EXPECTED_USE_CASE: dict[str, str] = {
    "与立项授权/启动阶段高度相关": "立项与授权",
    "与风险识别与应对相关": "风险与问题",
    "与进度规划/赶工相关": "进度与排期",
    "与范围与需求澄清相关": "范围与需求",
    "与干系人管理相关": "干系人与协作",
    "与项目收尾相关": "收尾与复盘",
    "与冲突升级与中立协调相关": "干系人与协作",
    "与一对一行为反馈相关": "沟通与汇报",
    "与跨团队对齐与依赖同步相关": "干系人与协作",
    "与结论先行的结构化汇报相关": "沟通与汇报",
    "与高难度对话准备相关": "沟通与汇报",
    "与周期性项目状态同步相关": "沟通与汇报",
    "与方案决策/权衡相关": "决策与分析",
}


def validate_use_cases(cases: list[str], *, slug: str = "") -> None:
    """校验 use_cases 非空且均为合法场景名。"""
    if not cases:
        prefix = f"工具「{slug}」" if slug else "工具"
        raise ValueError(f"{prefix} 至少需要一个 use_cases 条目")
    invalid = [c for c in cases if c not in VALID_USE_CASES]
    if invalid:
        prefix = f"工具「{slug}」" if slug else "工具"
        raise ValueError(f"{prefix} 含非法 use_cases：{invalid}")


def format_use_cases_label(cases: list[str]) -> str:
    """搜索/列表展示用：按 USE_CASE_ORDER 排序后逗号连接。"""
    order = {name: i for i, name in enumerate(USE_CASE_ORDER)}
    sorted_cases = sorted(cases, key=lambda c: order.get(c, 999))
    return "，".join(sorted_cases)
