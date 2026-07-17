"""ToolsRepository 与知识库工具测试。"""

from __future__ import annotations

import json

from pm_agent.agent.llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.prompts import MAX_CLARIFY_ROUNDS
from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.config import REPO_ROOT
from pm_agent.knowledge.categories import BOOST_EXPECTED_USE_CASE
from pm_agent.knowledge.repo import ToolsRepository
from pm_agent.tools.bootstrap import build_registry
from pm_agent.tools.registry import ToolRegistry


def _registry(repo: ToolsRepository, state: SessionState | None = None):
    session = state or SessionState()
    return build_registry(
        repo,
        session=session,
        output_dir=REPO_ROOT / "output",
    )


# 首批写厚目标：推荐/陪跑高频工具（其余条目不强制厚度）
TOP10_THICK_SLUGS = frozenset(
    {
        "project-charter",
        "risk-register",
        "stakeholder-register",
        "wbs",
        "raci-matrix",
        "issue-log",
        "change-management-plan",
        "status-report",
        "requirements-documentation",
        "lessons-learned-register",
    }
)


def test_repo_loads_all_tools() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    assert len(repo) == 47
    assert repo.exists("project-charter")
    assert repo.exists("risk-register")
    assert repo.exists("decision-record")
    assert repo.exists("decision-matrix")
    assert repo.exists("swot-analysis")
    charter = repo.get_by_slug("project-charter")
    assert charter is not None
    assert charter.name == "项目章程"
    assert charter.draftable is True


def test_top10_tools_meet_thickness_floor() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    slugs = {t.slug for t in repo.all()}
    assert TOP10_THICK_SLUGS <= slugs
    assert len({t.slug for t in repo.all()}) == len(repo)

    for slug in sorted(TOP10_THICK_SLUGS):
        tool = repo.get_by_slug(slug)
        assert tool is not None
        assert len(tool.description) >= 80, slug
        assert 5 <= len(tool.steps) <= 8, slug
        assert 6 <= len(tool.scenarios) <= 12, slug


def test_repo_search_finds_charter() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("立项授权")
    slugs = {t.slug for t in hits}
    assert "project-charter" in slugs


def test_all_tools_have_valid_use_cases() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    assert len(repo) == 47
    for tool in repo.all():
        assert tool.use_cases
        assert all(isinstance(c, str) and c for c in tool.use_cases)


def test_repo_search_by_use_case_name() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("决策")
    slugs = {t.slug for t in hits}
    assert "decision-matrix" in slugs


def test_list_by_use_case() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    tools = repo.list_by_use_case("决策与分析")
    slugs = {t.slug for t in tools}
    assert "decision-matrix" in slugs
    assert "decision-record" in slugs


def test_keyword_boosts_align_with_use_cases() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    boosts: list[tuple[list[str], str]] = [
        (
            ["project-charter", "stakeholder-register", "assumption-log"],
            "与立项授权/启动阶段高度相关",
        ),
        (
            ["risk-register", "risk-management-plan", "risk-report"],
            "与风险识别与应对相关",
        ),
        (
            ["gantt-chart", "activity-list", "network-diagram"],
            "与进度规划/赶工相关",
        ),
        (
            ["project-scope-statement", "wbs", "requirements-documentation"],
            "与范围与需求澄清相关",
        ),
        (
            ["cost-baseline", "cost-management-plan", "earned-value-analysis"],
            "与成本预算与绩效相关",
        ),
        (
            ["stakeholder-register", "stakeholder-engagement-plan", "raci-matrix"],
            "与干系人管理相关",
        ),
        (
            ["change-request", "change-management-plan", "issue-log"],
            "与变更控制相关",
        ),
        (
            ["project-closure-document", "final-report", "transition-plan"],
            "与项目收尾相关",
        ),
        (
            ["status-report", "communications-management-plan"],
            "与沟通与状态同步相关",
        ),
        (
            ["decision-matrix", "swot-analysis", "pre-mortem", "decision-record"],
            "与方案决策/权衡相关",
        ),
    ]
    for slugs, reason in boosts:
        expected = BOOST_EXPECTED_USE_CASE[reason]
        tool = repo.get_by_slug(slugs[0])
        assert tool is not None, slugs[0]
        assert expected in tool.use_cases, (slugs[0], tool.use_cases, expected)


def test_recommend_rejects_unknown_slug() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = _registry(repo)
    raw = registry.execute(
        "recommend_tools",
        {
            "question": "下周立项",
            "candidate_slugs": [
                "project-charter",
                "made-up-tool",
                "unicorn-framework",
            ],
        },
    )
    payload = json.loads(raw)
    assert payload["tools"]
    returned = {t["slug"] for t in payload["tools"]}
    assert "project-charter" in returned
    assert "made-up-tool" not in returned
    assert "unicorn-framework" in payload["rejected_slugs"]


def test_recommend_heuristic_for_立项() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question("下周立项，不知道从哪下手")
    slugs = [t.slug for t, _ in ranked]
    assert "project-charter" in slugs
    assert 1 <= len(ranked) <= 3


def test_recommend_decision_dilemma() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question("自研还是外采拿不定主意")
    slugs = {t.slug for t, _ in ranked}
    assert "decision-matrix" in slugs or "decision-record" in slugs
    assert 1 <= len(ranked) <= 3


def test_fake_立项_script_calls_recommend() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    state = SessionState()
    registry = _registry(repo, state)
    text = "下周立项，不知道从哪下手"
    llm = FakeLlmClient(demo_script_for_user_text(text))
    reply = handle_user_turn(text, state, llm, registry, max_iterations=10)

    assert "项目章程" in reply
    tool_names = [m.get("name") for m in state.messages if m.get("role") == "tool"]
    assert "recommend_tools" in tool_names


def test_clarify_count_increments_on_question_without_tools() -> None:
    registry = ToolRegistry()
    llm = FakeLlmClient(
        [{"content": "请问你现在卡在哪个阶段？"}]
    )
    state = SessionState()
    handle_user_turn("嗯", state, llm, registry, max_iterations=3)
    assert state.clarify_count == 1
    assert state.mode == SessionMode.CLARIFYING


def test_clarify_force_reminder_after_max() -> None:
    registry = ToolRegistry()
    state = SessionState()
    state.clarify_count = MAX_CLARIFY_ROUNDS
    llm = FakeLlmClient([{"content": "只能空回复"}])
    handle_user_turn("还是不清楚", state, llm, registry, max_iterations=3)
    system_texts = [
        m.get("content", "")
        for m in state.messages
        if m.get("role") == "system"
    ]
    assert any("澄清已达上限" in t for t in system_texts)


def test_clarify_skipped_in_consulting_mode() -> None:
    registry = ToolRegistry()
    llm = FakeLlmClient([{"content": "经济压力打几分？A/B/C？"}])
    state = SessionState(
        mode=SessionMode.CONSULTING,
        consulting_tool_slug="decision-matrix",
    )
    handle_user_turn("A 6 B 1 C 10", state, llm, registry, max_iterations=3)
    assert state.clarify_count == 0
    assert state.mode == SessionMode.CONSULTING


def test_clarify_force_reminder_skipped_in_drafting_mode() -> None:
    registry = ToolRegistry()
    state = SessionState(
        mode=SessionMode.DRAFTING_DECISION_MATRIX,
        clarify_count=MAX_CLARIFY_ROUNDS,
    )
    llm = FakeLlmClient([{"content": "矩阵已更新，是否确认导出？"}])
    handle_user_turn("先2后3", state, llm, registry, max_iterations=3)
    system_texts = [
        m.get("content", "")
        for m in state.messages
        if m.get("role") == "system"
    ]
    assert not any("澄清已达上限" in t for t in system_texts)
