"""pytest 共享 fixture。"""

from __future__ import annotations

from pm_agent.knowledge.matching import TriggerMatchRule, build_trigger_match_rules_for_tool


def sample_trigger_rules(*phrases: str) -> list[TriggerMatchRule]:
    """测试用最小 trigger_match_rules。"""

    cleaned = [p.strip() for p in phrases if p.strip()]
    if cleaned:
        rules = build_trigger_match_rules_for_tool(cleaned)
        if rules:
            return rules
    return [TriggerMatchRule(all_of=["测试"], any_of=["测试"])]
