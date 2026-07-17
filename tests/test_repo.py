"""ToolsRepository 与知识库工具测试。"""

from __future__ import annotations

import json

from pm_agent.agent.llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.prompts import MAX_CLARIFY_ROUNDS
from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.config import REPO_ROOT
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
    assert len(repo) == 40
    assert repo.exists("project-charter")
    assert repo.exists("risk-register")
    assert repo.exists("decision-record")
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
