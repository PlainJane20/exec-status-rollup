"""
Week-over-week RAG trend tracking.

Simpler than slack-daily-agent's tracking.py: workstreams have a stable Jira
key (PGMAUTO-4), so matching a workstream to its prior-run record is an exact
key lookup, not fuzzy text matching. No difflib needed here — use the right
tool for what the data actually gives you.
"""

import json
from pathlib import Path

DEFAULT_HISTORY_PATH = Path(__file__).parent / "history" / "rag_history.json"


def load_history(path: Path = DEFAULT_HISTORY_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_history(history: dict, path: Path = DEFAULT_HISTORY_PATH):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(history, indent=2))


def diff_and_update(scored_workstreams: list, run_date: str, history_path: Path = DEFAULT_HISTORY_PATH) -> list:
    """
    Compares each workstream's current status against its last recorded
    status. Returns a list of {key, name, from_status, to_status} for
    anything that changed, and updates history on disk.
    """
    history = load_history(history_path)
    changes = []

    for ws in scored_workstreams:
        prior = history.get(ws["key"])
        if prior and prior["status"] != ws["status"]:
            changes.append({
                "key": ws["key"],
                "name": ws["name"],
                "from_status": prior["status"],
                "to_status": ws["status"],
            })
        history[ws["key"]] = {"status": ws["status"], "name": ws["name"], "last_seen": run_date}

    save_history(history, history_path)
    return changes
