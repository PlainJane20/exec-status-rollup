"""
Deterministic RAG (Red/Amber/Green) scoring for a workstream.

Deliberately NOT an LLM call. The status color is a fact derived from real
data (due dates, staleness, blocked children) — asking a model to "decide"
RAG status invites exactly the kind of invented-confidence-with-no-basis
failure mode the eval harness in slack-daily-agent caught. Rule-based logic
here is auditable, debuggable, and testable with plain unit tests instead of
an eval harness — the right tool for a deterministic problem. The LLM's job
(see narrator.py) is limited to writing up these already-computed facts in
plain English, not deciding what the facts are.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

STALE_AFTER_DAYS = 14
DUE_SOON_DAYS = 14
CLOSED_STATUSES = {"Rejected", "Done", "Cancelled", "Closed"}


@dataclass
class RagResult:
    status: str  # "RED" | "AMBER" | "GREEN" | "CLOSED"
    facts: list = field(default_factory=list)  # grounded, human-readable reasons


def _parse_date(s):
    """
    Jira returns timestamps like '2026-07-30T14:23:11.123-0700' — a
    timezone offset with no colon. Python's datetime.fromisoformat on 3.9
    can't parse that (3.11+ can); the trailing regex normalizes it to
    '-07:00' first. Plain due-date strings ('2026-08-01') pass through
    untouched since the regex only matches a 4-digit offset at the end.
    """
    if not s:
        return None
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    return datetime.fromisoformat(s.replace("Z", "+00:00")).date()


def score_workstream(ws: dict, today: date = None) -> RagResult:
    today = today or date.today()

    if ws["status"] in CLOSED_STATUSES:
        return RagResult("CLOSED", [f"Status is '{ws['status']}' — excluded from active RAG rollup."])

    facts = []
    is_red = False
    is_amber = False

    due = _parse_date(ws.get("due_date"))
    updated = _parse_date(ws.get("updated"))

    if due and due < today and ws["status_category"] != "done":
        days_over = (today - due).days
        facts.append(f"Past due by {days_over} day(s) (due {due.isoformat()}).")
        is_red = True
    elif due and (due - today).days <= DUE_SOON_DAYS and ws["status_category"] != "done":
        facts.append(f"Due in {(due - today).days} day(s) ({due.isoformat()}).")
        is_amber = True

    if updated:
        days_stale = (today - updated).days
        if days_stale > STALE_AFTER_DAYS:
            facts.append(f"No update in {days_stale} days (last updated {updated.isoformat()}).")
            if ws["status_category"] == "indeterminate":
                is_red = True  # actively "in progress" but stalled — a real red flag
            else:
                is_amber = True

    children = ws.get("children", [])
    blocked_children = [c for c in children if "blocked" in [l.lower() for l in c.get("labels", [])]]
    if blocked_children:
        facts.append(f"{len(blocked_children)} child issue(s) labeled blocked: "
                      + ", ".join(c["key"] for c in blocked_children) + ".")
        is_red = True

    if children:
        done = [c for c in children if c["status_category"] == "done"]
        facts.append(f"{len(done)}/{len(children)} child issue(s) done.")

    if not facts:
        facts.append("No due-date, staleness, or blocker signals — on track.")

    status = "RED" if is_red else "AMBER" if is_amber else "GREEN"
    return RagResult(status, facts)
