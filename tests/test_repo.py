"""ToolsRepository 与知识库工具测试。"""

from __future__ import annotations

import json

import pytest

from pm_agent.agent.llm import FakeLlmClient, demo_script_for_user_text
from pm_agent.agent.loop import handle_user_turn
from pm_agent.agent.prompts import MAX_CLARIFY_ROUNDS, get_system_prompt
from pm_agent.agent.session import SessionMode, SessionState
from pm_agent.config import REPO_ROOT
from pm_agent.knowledge.categories import BOOST_EXPECTED_USE_CASE
from pm_agent.knowledge.repo import FALLBACK_RECOMMEND_REASON, ToolsRepository
from pm_agent.tools.bootstrap import build_registry
from pm_agent.tools.registry import ToolRegistry


def _registry(repo: ToolsRepository, state: SessionState | None = None):
    session = state or SessionState()
    return build_registry(
        repo,
        session=session,
        output_dir=REPO_ROOT / "output",
    )


# 正式库高频写厚目标（其余保留条目不强制厚度）
TOP10_THICK_SLUGS = frozenset(
    {
        "project-charter",
        "risk-register",
        "stakeholder-register",
        "raci-matrix",
        "lessons-learned-register",
        "decision-matrix",
        "decision-record",
        "sbi-feedback",
        "five-whys",
        "pre-mortem",
    }
)


def test_repo_loads_all_tools() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    assert len(repo) == 29
    assert repo.exists("project-charter")
    assert repo.exists("risk-register")
    assert repo.exists("decision-record")
    assert repo.exists("decision-matrix")
    assert repo.exists("swot-analysis")
    assert repo.exists("gantt-chart")
    assert repo.exists("stakeholder-register")
    assert repo.exists("after-action-review")
    assert repo.exists("start-stop-continue")
    assert repo.exists("blameless-postmortem")
    assert repo.exists("knowledge-handover")
    assert repo.exists("status-report")
    assert repo.exists("one-page-project-narrative")
    assert repo.exists("decision-request-memo")
    assert repo.exists("stakeholder-progress-note")
    assert repo.exists("project-experience-case-outline")
    assert not repo.exists("wbs")
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
    assert len(repo) == 29
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
    assert repo.boost_rules
    for rule in repo.boost_rules:
        expected = BOOST_EXPECTED_USE_CASE[rule.reason]
        tool = repo.get_by_slug(rule.slugs[0])
        assert tool is not None, rule.slugs[0]
        assert expected in tool.use_cases, (rule.slugs[0], tool.use_cases, expected)


def test_recommendation_boosts_slugs_in_formal_catalog() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    formal = {t.slug for t in repo.all()}
    referenced = set(repo.fallback_slugs)
    for rule in repo.boost_rules:
        referenced.update(rule.slugs)
    assert referenced <= formal


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
    assert payload.get("match_strength") == "strong"


def test_system_prompt_discovery_gate_on_idle() -> None:
    prompt = get_system_prompt(clarify_count=0, mode=SessionMode.IDLE)
    assert "发现与推荐闸门" in prompt
    assert "禁止" in prompt and "随便聊" in prompt
    assert "优先调用 recommend_tools" in prompt
    assert "口头判死刑" in prompt or "未拿到工具返回前" in prompt


def test_recommend_empty_question_is_weak() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = _registry(repo)
    payload = json.loads(
        registry.execute("recommend_tools", {"question": "   ", "context": ""})
    )
    assert payload["tools"] == []
    assert payload["match_strength"] == "weak"
    assert "暂时匹配不到" in payload["instruction"]
    assert "闲聊" in payload["instruction"]


def test_recommend_fallback_is_weak_match() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = _registry(repo)
    # 无触发语/boost 的乱码，应落入 fallback
    payload = json.loads(
        registry.execute(
            "recommend_tools",
            {"question": "zzzxqqq999 unrelated gibberish xyzzy"},
        )
    )
    assert payload["tools"]
    assert payload["match_strength"] == "weak"
    assert all(t["reason"] == FALLBACK_RECOMMEND_REASON for t in payload["tools"])
    assert "不要把下列工具说成强相关首选" in payload["instruction"]
    assert "闲聊" in payload["instruction"]


def test_recommend_strong_match_for_立项() -> None:
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    registry = _registry(repo)
    payload = json.loads(
        registry.execute("recommend_tools", {"question": "下周立项，还没正式授权"})
    )
    assert payload["tools"]
    assert payload["match_strength"] == "strong"
    assert "instruction" not in payload
    slugs = {t["slug"] for t in payload["tools"]}
    assert "project-charter" in slugs


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


def test_new_communication_tools_exist() -> None:
    """回归测试：新发布的沟通类工具存在于正式库中。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    new_slugs = {
        "sbi-feedback",
        "pyramid-principle",
        "cross-functional-alignment",
        "conflict-resolution-process",
        "difficult-conversation-prep",
    }
    for slug in new_slugs:
        assert repo.exists(slug), f"缺少新工具：{slug}"


def test_search_finds_sbi_feedback() -> None:
    """回归测试：用户反馈类卡点应命中 SBI 反馈模型。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("怎么给负面反馈又不伤关系")
    slugs = {t.slug for t in hits}
    assert "sbi-feedback" in slugs


def test_search_finds_difficult_conversation_prep() -> None:
    """回归测试：开口难类卡点应命中高难度对话准备。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("这话我不知道怎么开口说")
    slugs = {t.slug for t in hits}
    assert "difficult-conversation-prep" in slugs


def test_search_finds_cross_functional_alignment() -> None:
    """回归测试：跨部门理解不一致应命中跨部门对齐会。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("两个团队对同一个需求理解完全不一样")
    slugs = {t.slug for t in hits}
    assert "cross-functional-alignment" in slugs


def test_search_finds_conflict_resolution() -> None:
    """回归测试：团队冲突类卡点应命中冲突解决流程。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("两个组因为资源分配吵起来了")
    slugs = {t.slug for t in hits}
    assert "conflict-resolution-process" in slugs


def test_recommend_communication_dilemma() -> None:
    """回归测试：冲突类卡点推荐应包含冲突解决流程。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question("两个组因为资源分配冲突吵起来了，影响交付了")
    slugs = {t.slug for t, _ in ranked}
    assert "conflict-resolution-process" in slugs
    assert 1 <= len(ranked) <= 3


def test_recommend_feedback_dilemma() -> None:
    """回归测试：反馈类卡点推荐应包含 SBI 反馈模型。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question("怎么给负面反馈又不伤关系")
    slugs = {t.slug for t, _ in ranked}
    assert "sbi-feedback" in slugs
    assert 1 <= len(ranked) <= 3


def test_new_retrospective_tools_exist() -> None:
    """回归测试：复盘与学习家族已发布工具存在于正式库。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    for slug in (
        "after-action-review",
        "start-stop-continue",
        "blameless-postmortem",
        "knowledge-handover",
    ):
        assert repo.exists(slug), f"缺少新工具：{slug}"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("这个活动刚结束，想快速复盘一下", "after-action-review"),
        ("迭代结束了，想开个轻量复盘", "start-stop-continue"),
        ("出了大事故，复盘变成追责会", "blameless-postmortem"),
        ("项目要交给运维了，不知道交什么", "knowledge-handover"),
    ],
)
def test_recommend_retrospective_queries_top1(query: str, expected: str) -> None:
    """回归：复盘家族典型原话 Top1 应命中对应工具。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question(query, limit=3)
    assert ranked
    assert ranked[0][0].slug == expected


def test_search_finds_after_action_review() -> None:
    """回归测试：活动结束复盘应命中 AAR。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("发布刚结束想对照原计划和实际")
    assert "after-action-review" in {t.slug for t in hits}


def test_search_finds_knowledge_handover() -> None:
    """回归测试：移交运维类卡点应命中知识移交。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    hits = repo.search("原团队要撤，怕知识断档")
    assert "knowledge-handover" in {t.slug for t in hits}


def test_new_upward_reporting_tools_exist() -> None:
    """回归测试：向上管理与汇报家族已发布工具存在于正式库。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    for slug in (
        "status-report",
        "one-page-project-narrative",
        "decision-request-memo",
        "stakeholder-progress-note",
        "project-experience-case-outline",
    ):
        assert repo.exists(slug), f"缺少新工具：{slug}"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("周五例行同步，读者要一眼看到进展、偏差和需要支持的事", "status-report"),
        ("想给周边团队发一页对齐认知，讲清项目本身而非本周偏差", "one-page-project-narrative"),
        ("预算超支要赞助人书面授权，对方时间紧必须看完就能批复", "decision-request-memo"),
        ("想给老板三句话：结论进展、卡点、需不需要他出手", "stakeholder-progress-note"),
        ("想把这次交付经历写成同行能读完的经验文章提纲", "project-experience-case-outline"),
    ],
)
def test_recommend_upward_reporting_queries_top3(query: str, expected: str) -> None:
    """回归：向上管理与汇报典型卡点应命中对应工具 Top3。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question(query, limit=3)
    slugs = {tool.slug for tool, _ in ranked}
    assert expected in slugs
    assert 1 <= len(ranked) <= 3


@pytest.mark.parametrize(
    ("query", "context", "expected"),
    [
        (
            "两个团队已经公开争吵并拒绝合作，需要中立人协调资源分歧",
            "冲突已经影响交付。",
            "conflict-resolution-process",
        ),
        (
            "双方已经拒绝沟通并公开争夺资源，需要中立方介入和升级机制",
            "冲突已经影响交付。",
            "conflict-resolution-process",
        ),
        (
            "产品和设计僵持一周，双方拒绝再谈，需要第三方主持折中和升级规则",
            "普通一对一反馈已无法解决。",
            "conflict-resolution-process",
        ),
        (
            "下属这周两次未按约定更新任务，我该怎样就事论事地提醒",
            "关系正常，希望形成具体改进约定。",
            "sbi-feedback",
        ),
        (
            "我只需要提醒同事一次具体行为及其影响，双方关系正常",
            "没有持续矛盾，也不需中立人介入。",
            "sbi-feedback",
        ),
        (
            "客户和交付团队对范围各执一词，争议公开化且项目停摆",
            "需要识别利益分歧并形成仲裁路径。",
            "conflict-resolution-process",
        ),
        (
            "三个供应商共同交付一个模块，但彼此不知道接口和时间依赖",
            "需要固定议程和可追踪行动项。",
            "cross-functional-alignment",
        ),
        (
            "产品和研发对接口定义理解不同，需要把依赖、责任人和行动项对齐",
            "不是写汇报材料。",
            "cross-functional-alignment",
        ),
        (
            "我知道必须谈裁员安排，但担心对方的反应，想先准备开场和底线",
            "对话尚未开始。",
            "difficult-conversation-prep",
        ),
        (
            "要拒绝老板的不合理要求，我想预演他沉默、反击或施压时怎么回应",
            "目标是先做好对话准备，不是立即升级。",
            "difficult-conversation-prep",
        ),
        (
            "我的邮件堆了很多事实，读者看完仍不知道建议是什么",
            "希望重组为结论、理由和证据。",
            "pyramid-principle",
        ),
        (
            "高管只有三十秒，我要先说结论，再用三点证据支撑",
            "用于方案审批汇报。",
            "pyramid-principle",
        ),
    ],
)
def test_recommend_confusion_pair_queries_top1(
    query: str,
    context: str,
    expected: str,
) -> None:
    """回归：基线混淆对应用例的 Top1 应命中期望工具。"""
    repo = ToolsRepository.from_json_path(REPO_ROOT / "data" / "tools.json")
    ranked = repo.recommend_by_question(query, context=context, limit=3)
    assert ranked
    assert ranked[0][0].slug == expected


def test_clarify_count_increments_on_question_without_tools() -> None:
    registry = ToolRegistry()
    llm = FakeLlmClient([{"content": "请问你现在卡在哪个阶段？"}])
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
    system_texts = [m.get("content", "") for m in state.messages if m.get("role") == "system"]
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
    system_texts = [m.get("content", "") for m in state.messages if m.get("role") == "system"]
    assert not any("澄清已达上限" in t for t in system_texts)
