"""
Unit tests for the deterministic RAG scorer. Plain pytest, not an eval
harness — there's no model in the loop here, so there's nothing for an LLM
judge to grade. See health_scorer.py's module docstring for why this split
(deterministic logic -> unit tests, LLM narration -> eval harness) is
deliberate, not an oversight.
"""

from datetime import date

from health_scorer import score_workstream

TODAY = date(2026, 8, 26)


def ws(**overrides):
    base = {
        "key": "PGMAUTO-99",
        "name": "Test workstream",
        "status": "In Execution",
        "status_category": "indeterminate",
        "due_date": None,
        "updated": "2026-08-25T10:00:00.000-0700",
        "children": [],
    }
    base.update(overrides)
    return base


def test_on_track_is_green():
    result = score_workstream(ws(), today=TODAY)
    assert result.status == "GREEN"


def test_overdue_is_red():
    result = score_workstream(ws(due_date="2026-08-01"), today=TODAY)
    assert result.status == "RED"
    assert any("Past due" in f for f in result.facts)


def test_due_soon_is_amber():
    result = score_workstream(ws(due_date="2026-09-05"), today=TODAY)
    assert result.status == "AMBER"
    assert any("Due in" in f for f in result.facts)


def test_stale_in_progress_is_red():
    result = score_workstream(ws(updated="2026-08-01T10:00:00.000-0700"), today=TODAY)
    assert result.status == "RED"
    assert any("No update in" in f for f in result.facts)


def test_stale_not_started_is_amber_not_red():
    result = score_workstream(
        ws(status_category="new", updated="2026-08-01T10:00:00.000-0700"), today=TODAY
    )
    assert result.status == "AMBER"


def test_blocked_child_forces_red_even_if_otherwise_on_track():
    result = score_workstream(
        ws(children=[{"key": "PGMAUTO-100", "labels": ["blocked"], "status_category": "indeterminate"}]),
        today=TODAY,
    )
    assert result.status == "RED"
    assert any("blocked" in f for f in result.facts)


def test_rejected_status_is_closed_not_red():
    result = score_workstream(ws(status="Rejected"), today=TODAY)
    assert result.status == "CLOSED"


def test_done_workstream_ignores_due_date():
    result = score_workstream(
        ws(status="In Roadmap", status_category="done", due_date="2020-01-01"), today=TODAY
    )
    # status_category == "done" should suppress the overdue signal even
    # though the due date has long passed
    assert result.status != "RED"


def test_child_completion_ratio_is_reported():
    result = score_workstream(
        ws(children=[
            {"key": "A", "labels": [], "status_category": "done"},
            {"key": "B", "labels": [], "status_category": "indeterminate"},
        ]),
        today=TODAY,
    )
    assert any("1/2" in f for f in result.facts)
