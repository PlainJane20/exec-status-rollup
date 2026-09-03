<img src="docs/exec-status-rollup-banner.svg" alt="Executive Status Rollup — Executive Portfolio Intelligence" width="100%" />

# Executive Status Rollup

<div align="center">

[![Python 3.9+](https://img.shields.io/badge/Python_3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Powered by Claude](https://img.shields.io/badge/Powered_by-Claude-D97757?style=for-the-badge&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Jira API](https://img.shields.io/badge/Jira_API-0052CC?style=for-the-badge&logo=jira&logoColor=white)](https://developer.atlassian.com/)
[![Tests](https://img.shields.io/badge/Unit_tests-9_passing-1baf7a?style=for-the-badge)](test_health_scorer.py)

</div>

A weekly Red/Amber/Green executive rollup across a Jira portfolio — pulled
from real Jira data, scored by deterministic rules (not an LLM), narrated by
Claude, and tracked week-over-week so a status flip is visible instead of
silently overwritten.

**Why this exists:** the other two tools in this series
([slack-daily-brief](https://github.com/PlainJane20/slack-daily-brief),
[pm-automation-system](https://github.com/PlainJane20/pm-automation-system))
each solve one piece of a TPM's week — reading Slack, automating Jira
intake. This one is the integration: it's the artifact a TPM actually hands
to leadership, built by connecting the other two rather than starting a
fourth disconnected tool.

> **Why I built it:** this is a personal project, built to get real practice
> keeping a status *decision* separate from its *narration* — the RAG color
> here comes from testable rules over due dates, staleness, and blocked
> children that Claude never touches, not from asking a model to eyeball a
> ticket and guess. That separation is the actual skill: a Staff/Principal
> TPM has to make status calls that hold up under questioning, and "the LLM
> said so" isn't a defensible answer, while "here's the rule, and here's the
> unit test that pins it down" is. The week-over-week trend history was
> practice at the other half of the same problem — building a system that
> remembers its last answer instead of treating every report as a fresh
> snapshot, so a quiet regression shows up as a visible flip instead of
> getting silently overwritten.

> **Related work in this portfolio:** [critical-path-radar](https://github.com/PlainJane20/critical-path-radar)
> reads the same Jira project and complements this one directly — RAG
> status here says a workstream *looks* unhealthy; critical-path-radar's
> CPM math says whether that workstream's health *matters* to the
> delivery date. [agent-control-tower](https://github.com/PlainJane20/agent-control-tower)
> is retrofitted onto this agent (and slack-daily-brief) as the
> governance layer — cost caps, audit log, human-approval gate on the
> Slack post.

## At a glance

| | |
|---|---|
| **Problem** | Executive status reporting is usually a manual Friday-afternoon reconstruction across tickets, channels, and memory |
| **Approach** | Deterministic RAG scoring (auditable, testable) + Claude narration (grounded, not deciding status) + week-over-week trend diffing |
| **Data** | Real, live Jira data from the PGMAUTO project — not a mocked demo |
| **Stack** | Python · Jira REST API v3 · Claude (Anthropic API) · pytest · Slack API |

## Competencies demonstrated

| Competency | Observable evidence |
|---|---|
| Portfolio governance | Aggregates workstreams into a comparable executive health view |
| Decision-quality design | Deterministic status rules remain separate from narrative generation |
| Trend management | Week-over-week history makes deterioration and recovery visible |
| Systems integration | Connects Jira evidence, local history, Claude narration, and optional Slack delivery |
| Operational credibility | Documents real API migrations, timestamp defects, and credential propagation fixes |

## Architecture

```mermaid
flowchart LR
    Jira[("Jira: PGMAUTO project")] -->|"/rest/api/3/search/jql"| Client["jira_client.py"]
    Client --> Group["build_workstreams()<br/>group issues by Epic"]
    Group --> Scorer["health_scorer.py<br/>deterministic RAG rules"]
    Scorer -.->|validated by| Tests["test_health_scorer.py<br/>9 unit tests"]
    Scorer --> Trend["trend.py<br/>week-over-week diff"]
    History[("history/rag_history.json")] <--> Trend
    Scorer --> Narrator["Claude<br/>narrator.py"]
    Trend --> Narrator
    Narrator --> Report[("~/exec-status-rollup.md")]
    Narrator --> SlackPost["Slack #exec-status-rollup"]
    Narrator --> Console["Terminal display"]
```

## Key engineering decisions

| Decision | Why |
|---|---|
| RAG status is computed by rules, not by Claude | A status color is a fact about due dates and staleness, not a judgment call — asking an LLM to "decide" status invites the same invented-confidence failure mode an eval harness caught in a related project. Claude's role here is narrowly to write up already-computed facts. |
| Deterministic logic gets unit tests, not an eval harness | `health_scorer.py` has no model in the loop — there's nothing for an LLM judge to grade. `eval/`-style harnesses are for probabilistic output; plain `pytest` is the right tool here, and it's what actually caught a real bug (below). |
| Workstream matching by exact Jira key, not fuzzy text | A related project needed `difflib` fuzzy matching because Slack questions have no stable ID. Jira issues do — using an exact key match instead of fuzzy matching where the data supports it is simpler and has zero false-match risk. |
| Credentials resolved via a sibling-repo `.env` fallback chain | Reuses the same live Jira token already configured for `pm-automation-system` and the same Anthropic key already configured for `slack-daily-agent`, instead of asking for (and duplicating) the same secrets a third time. |

## Deciding vs. narrating: keeping the model out of the decision

> **The competency this is really practicing:** separating *deciding* from
> *narrating* in an LLM pipeline — deciding what to say only after a
> deterministic rule has already decided what's true.

`health_scorer.py` computes the RAG color from plain, testable rules over
due dates and staleness *before* Claude ever sees the ticket; Claude's
only job is to write up a status that a human (or `pytest`) already
computed and can verify independently of the model.

For context on why that distinction matters beyond this repo: Atlassian's
own **Rovo Strategic Intelligence** (open beta, June 2026) generates
AI-written project-health narration too, but by having the model *reason
over* the Teamwork Graph to infer status directly — the exact pattern this
design avoids.

Concretely, that means:

- **A wrong status is a bug you can catch and fix in a unit test.** Rovo's
  AI-inferred status has no equivalent — if the model's inference is wrong,
  there's no deterministic ground truth to diff it against. Here, one exists:
  `test_health_scorer.py`'s 9 tests pin down exactly what "red" means, and a
  regression in that logic fails a test before it ever reaches a VP's inbox.
- **The narration can be swapped or removed without changing a single status.**
  Claude writes the prose; it never touches the RAG color. Turn off the LLM
  entirely and the rollup still produces correct, auditable Red/Amber/Green
  calls — just without the write-up.
- **This is a narrower promise than Rovo's, on purpose.** Rovo is a full
  reasoning layer across Atlassian's whole graph; this tool does one thing —
  status classification you can unit-test — and treats the LLM as a renderer
  for facts it doesn't get a vote in deciding.

## Real bugs found building this

Same discipline as the other repos in this series — documented as found,
not smoothed over:

1. **The Jira Search API I built against doesn't exist anymore.** `/rest/api/3/search` returns HTTP 410 — Atlassian retired it. Found by testing against the real project instead of trusting older documentation; migrated to `/rest/api/3/search/jql` before writing another line against it.
2. **`datetime.fromisoformat` couldn't parse Jira's actual timestamps** on Python 3.9 — Jira returns offsets like `-0700` (no colon), which 3.9's parser rejects (3.11+ accepts it). Caught immediately by `test_health_scorer.py` — 8 of 9 tests failed on the first run — before this ever touched real data.
3. **A resolved credential silently didn't propagate.** `config.py`'s sibling-repo fallback resolves `ANTHROPIC_API_KEY` into a local dict, but `narrator.py` was reading `os.environ` directly — which the fallback never touches. Passing the key as an explicit function argument instead of an implicit environment read fixed the bug and removed the whole class of "which layer actually has this value" confusion.

## Setup

```bash
git clone <this repo>
cd exec-status-rollup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY at minimum. JIRA_* falls back to
# ../pm-automation-system/.env automatically if you have that repo too.
```

## Usage

```bash
# Run once, save to ~/exec-status-rollup.md
python run_rollup.py

# Also post to a Slack channel
python run_rollup.py --slack-channel exec-status-rollup

# Run the unit tests
python -m pytest test_health_scorer.py -v
```

## Output example

```
# Executive Status Rollup — Tuesday, August 25, 2026

## 🔴 Red — Needs Attention
- Automated Inventory Reconciliation System (AIRS): No update in 26 days; only 1 of 2 child issues done.
- Automated Employee IT Onboarding Pipeline: No update in 68 days — longest stale gap in the portfolio.

## 🟡 Amber — Watch
- Customer Self Service Portal: No update in 68 days.

## 🟢 Green — On Track
None

## Summary
No workstreams are currently green — the portfolio is split between RED and
AMBER items, all driven by extended periods without updates...

---
Closed this period: test via JIRA
```

## Contact

<div align="center">

### **Navi Sohi**
*Technical Program Manager & Automation Engineer*

<br>

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/navisohi/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/PlainJane20)
[![Email](https://img.shields.io/badge/Email-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](https://mail.google.com/mail/?view=cm&fs=1&to=nks.ai.dev@gmail.com)

<br>

</div>
