"""
Config loading.

Deliberately falls back to pm-automation-system's .env for Jira credentials
when this repo's own .env doesn't have them set — the two tools point at the
same Jira instance, and duplicating a live API token across two local repos
is one more place for it to leak. If you're running this somewhere
pm-automation-system doesn't exist, just fill in your own .env and the
fallback is never touched.
"""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

HERE = Path(__file__).parent
JIRA_FALLBACK_ENV = HERE.parent / "pm-automation-system" / ".env"
ANTHROPIC_FALLBACK_ENV = HERE.parent / "slack-daily-agent" / ".env"
SLACK_FALLBACK_ENV = HERE.parent / "slack-daily-agent" / ".env"

JIRA_KEYS = ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]


def _fill_from(cfg: dict, keys: list, fallback_path: Path):
    missing = [k for k in keys if not cfg.get(k)]
    if missing and fallback_path.exists():
        fallback = dotenv_values(fallback_path)
        for k in missing:
            if fallback.get(k):
                cfg[k] = fallback[k]


def load_config() -> dict:
    load_dotenv(HERE / ".env")
    cfg = {k: os.environ.get(k, "") for k in JIRA_KEYS}
    cfg["JIRA_PROJECT_KEY"] = os.environ.get("JIRA_PROJECT_KEY", "PGMAUTO")
    cfg["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg["SLACK_USER_TOKEN"] = os.environ.get("SLACK_USER_TOKEN", "")

    _fill_from(cfg, JIRA_KEYS, JIRA_FALLBACK_ENV)
    _fill_from(cfg, ["ANTHROPIC_API_KEY"], ANTHROPIC_FALLBACK_ENV)
    _fill_from(cfg, ["SLACK_USER_TOKEN"], SLACK_FALLBACK_ENV)

    return cfg
