"""工具库持续生长系统：候选、门禁、提示词与发布。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pm_agent.knowledge.catalog_ops import (
    CandidateStatus,
    QualityScore,
    ToolCandidate,
    build_generation_prompt,
    candidate_issues,
    load_candidates,
    promote_candidate,
    review_candidate,
    strict_tool_issues,
)
from pm_agent.knowledge.repo import PmTool, ToolsRepository


def _valid_tool(slug: str = "active-listening") -> PmTool:
    return PmTool(
        slug=slug,
        name="积极倾听",
        name_en="Active Listening",
        summary="通过复述、澄清与确认理解减少沟通偏差",
        description=(
            "何时用：对方表达复杂顾虑或双方理解不一致时。"
            "何时别用：需要立即执行安全处置时。"
            "常见坑：急着给建议；只复述字面内容；没有确认下一步。"
        ),
        steps=[
            "暂停判断并完整听取对方表达 → 产出原始信息摘要",
            "复述事实与关键观点 → 产出理解确认句",
            "识别并命名可能的感受与顾虑 → 产出情绪线索",
            "用开放问题澄清含糊信息 → 产出待确认事项",
            "总结双方一致与分歧 → 产出对齐清单",
            "确认下一步行动与责任人 → 产出行动约定",
        ],
        scenarios=[
            "对方说了很多，我抓不到真正诉求",
            "跨部门双方都觉得自己被误解",
            "成员抱怨项目安排但不愿直接提要求",
            "会议里大家急着反驳，没有人确认理解",
            "我总忍不住先给解决方案",
            "需要先听清老板真正担心什么",
            "只需给一次具体行为反馈——使用 SBI（易混）",
        ],
        trigger_phrases=[
            "我不知道对方真正想要什么",
            "沟通会上大家都在说但没人听",
            "我总是忍不住马上给建议",
        ],
        draftable=False,
        use_cases=["沟通与汇报", "干系人与协作"],
    )


def _candidate(status: CandidateStatus = CandidateStatus.DRAFTED) -> ToolCandidate:
    tool = _valid_tool()
    return ToolCandidate(
        slug=tool.slug,
        name=tool.name,
        family="沟通与冲突",
        problem="复杂沟通中先理解对方，减少误判和无效建议。",
        trigger_phrases=tool.trigger_phrases,
        differentiation="区别于 SBI：本工具先理解完整诉求，不以输出反馈为主。",
        proposed_use_cases=tool.use_cases,
        status=status,
        tool=tool,
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _setup_files(tmp_path: Path) -> tuple[Path, Path]:
    tools_path = tmp_path / "tools.json"
    candidates_path = tmp_path / "tool_candidates.json"
    existing = PmTool(
        slug="status-report",
        name="项目状态报告",
        summary="同步项目状态",
        use_cases=["沟通与汇报"],
    )
    _write_json(tools_path, [existing.model_dump(exclude_none=True)])
    _write_json(
        candidates_path,
        [_candidate().model_dump(mode="json", exclude_none=True)],
    )
    return tools_path, candidates_path


def test_strict_tool_quality_gate() -> None:
    assert strict_tool_issues(_valid_tool()) == []
    thin = _valid_tool().model_copy(
        update={"description": "适合沟通", "steps": ["听"], "scenarios": ["沟通"]}
    )
    issues = strict_tool_issues(thin)
    assert any("何时用" in issue for issue in issues)
    assert any("steps" in issue for issue in issues)
    assert any("scenarios" in issue for issue in issues)


def test_candidate_requires_score_and_approval_for_publish(tmp_path: Path) -> None:
    tools_path, _ = _setup_files(tmp_path)
    issues = candidate_issues(
        _candidate(),
        ToolsRepository.from_json_path(tools_path),
        require_approved=True,
    )
    assert "发布前状态必须为 approved" in issues
    assert "发布前必须完成质量评分" in issues


def test_review_rejects_score_below_eight(tmp_path: Path) -> None:
    tools_path, candidates_path = _setup_files(tmp_path)
    low_score = QualityScore(
        trigger_clarity=1,
        actionability=1,
        output_clarity=1,
        boundary_clarity=1,
        recommendation_value=1,
    )
    with pytest.raises(ValueError, match="8/10"):
        review_candidate(
            candidates_path,
            tools_path,
            "active-listening",
            low_score,
            approve=True,
        )
    assert load_candidates(candidates_path)[0].status == CandidateStatus.DRAFTED


def test_dry_run_then_promote_and_search_trigger(tmp_path: Path) -> None:
    tools_path, candidates_path = _setup_files(tmp_path)
    score = QualityScore(
        trigger_clarity=2,
        actionability=2,
        output_clarity=2,
        boundary_clarity=1,
        recommendation_value=1,
    )
    review_candidate(
        candidates_path,
        tools_path,
        "active-listening",
        score,
        approve=True,
        note="测试批准",
    )
    tools_before = tools_path.read_text(encoding="utf-8")
    pool_before = candidates_path.read_text(encoding="utf-8")

    promote_candidate(candidates_path, tools_path, "active-listening", dry_run=True)
    assert tools_path.read_text(encoding="utf-8") == tools_before
    assert candidates_path.read_text(encoding="utf-8") == pool_before

    promote_candidate(candidates_path, tools_path, "active-listening")
    repo = ToolsRepository.from_json_path(tools_path)
    assert repo.exists("active-listening")
    question = "沟通会上大家都在说但没人听"
    assert repo.search(question)[0].slug == "active-listening"
    assert repo.recommend_by_question(question)[0][0].slug == "active-listening"
    assert load_candidates(candidates_path)[0].status == CandidateStatus.PUBLISHED


def test_generation_prompt_contains_catalog_context(tmp_path: Path) -> None:
    tools_path, candidates_path = _setup_files(tmp_path)
    prompt = build_generation_prompt(
        family="沟通与冲突",
        count=5,
        repo=ToolsRepository.from_json_path(tools_path),
        candidates=load_candidates(candidates_path),
    )
    assert "生成 5 个“沟通与冲突”" in prompt
    assert "status-report｜项目状态报告" in prompt
    assert "active-listening｜积极倾听" in prompt
    assert "仅输出合法 JSON 数组" in prompt


def test_repo_rejects_duplicate_slugs(tmp_path: Path) -> None:
    path = tmp_path / "tools.json"
    tool = _valid_tool().model_dump(exclude_none=True)
    _write_json(path, [tool, tool])
    with pytest.raises(ValueError, match="重复 slug"):
        ToolsRepository.from_json_path(path)
