from __future__ import annotations

from pm_agent.knowledge.matching import (
    TriggerMatchRule,
    build_trigger_match_rules_for_tool,
    derive_trigger_match_rules_from_phrases,
    match_trigger_rule,
    match_trigger_rules,
    tokenize_query_for_search,
)


def test_match_trigger_rule_all_of_any_of_with_synonyms() -> None:
    rule = TriggerMatchRule(all_of=["客户"], any_of=["拒绝"])
    synonyms = {
        "客户": {"客户", "老板", "甲方"},
        "老板": {"客户", "老板", "甲方"},
    }
    assert match_trigger_rule("老板拒绝了", rule, synonyms=synonyms) is True


def test_match_trigger_rule_requires_all_of() -> None:
    rule = TriggerMatchRule(all_of=["客户"], any_of=["拒绝"])
    assert match_trigger_rule("拒绝了", rule, synonyms={}) is False


def test_match_trigger_rules_any_of_rules() -> None:
    rule1 = TriggerMatchRule(all_of=["客户"], any_of=["拒绝"])
    rule2 = TriggerMatchRule(all_of=["变更"], any_of=["影响"])
    assert (
        match_trigger_rules("收到变更会影响排期", [rule1, rule2], synonyms={}) is True
    )


def test_build_trigger_match_rules_includes_exact_phrases() -> None:
    phrases = ["需求越加越多，又不敢拒绝"]
    rules = build_trigger_match_rules_for_tool(phrases)
    assert any(r.all_of == [phrases[0]] for r in rules)


def test_derive_trigger_match_rules_from_phrases_is_non_empty() -> None:
    phrases = [
        "客户口头说先做，但没有正式变更流程",
        "老板口头先做，没有正式变更流程",
        "口头承诺客户加功能，但没有正式变更",
    ]
    rules = derive_trigger_match_rules_from_phrases(phrases)
    assert rules
    rule = rules[0]
    assert rule.all_of
    assert rule.any_of


def test_tokenize_query_for_search_no_spaces() -> None:
    tokens = tokenize_query_for_search("怎么给负面反馈又不伤关系")
    assert tokens

