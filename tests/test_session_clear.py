"""SessionState.clear()：/new 就地重置。"""

from __future__ import annotations

from pm_agent.agent.session import (
    CharterDraft,
    DecisionDraft,
    DecisionMatrixDraft,
    RiskRegisterDraft,
    SessionMode,
    SessionState,
)


def test_clear_resets_all_session_fields() -> None:
    state = SessionState(
        messages=[{"role": "user", "content": "hello"}],
        mode=SessionMode.DRAFTING_CHARTER,
        clarify_count=2,
        charter_draft=CharterDraft(project_name="X"),
        risk_draft=RiskRegisterDraft(),
        decision_draft=DecisionDraft(decision_title="Y"),
        matrix_draft=DecisionMatrixDraft(title="Z"),
        consulting_tool_slug="project-charter",
        consulting_notes=["note-a"],
    )

    state.clear()

    assert state.messages == []
    assert state.mode is SessionMode.IDLE
    assert state.clarify_count == 0
    assert state.charter_draft is None
    assert state.risk_draft is None
    assert state.decision_draft is None
    assert state.matrix_draft is None
    assert state.consulting_tool_slug is None
    assert state.consulting_notes == []


def test_clear_keeps_same_object_identity() -> None:
    state = SessionState(messages=[{"role": "user", "content": "a"}])
    before = id(state)
    state.clear()
    assert id(state) == before
