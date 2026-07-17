"""实用场景分类常量测试。"""

from __future__ import annotations

import pytest

from pm_agent.knowledge.categories import (
    USE_CASE_ORDER,
    VALID_USE_CASES,
    format_use_cases_label,
    validate_use_cases,
)


def test_use_case_order_has_eleven_entries() -> None:
    assert len(USE_CASE_ORDER) == 11
    assert USE_CASE_ORDER[-1] == "流程规范（参考）"
    assert set(USE_CASE_ORDER) == set(VALID_USE_CASES)


def test_validate_use_cases_rejects_empty() -> None:
    with pytest.raises(ValueError, match="至少需要一个"):
        validate_use_cases([])


def test_validate_use_cases_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="非法 use_cases"):
        validate_use_cases(["决策与分析", "不存在场景"])


def test_format_use_cases_label_sorts_by_order() -> None:
    label = format_use_cases_label(["风险与问题", "立项与授权"])
    assert label == "立项与授权，风险与问题"
