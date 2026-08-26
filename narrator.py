"""
Turns the deterministically-scored workstreams into an executive-readable
markdown report. Claude's job here is narrow and explicit: write up facts
that are already computed, don't decide status, don't add facts that aren't
in the input. This mirrors the grounding discipline slack-daily-agent's eval
harness forced into that project's system prompt — applied here from the
start instead of discovered after a hallucination regression.
"""

import anthropic

SYSTEM_PROMPT = """You are writing an executive status rollup for a technical
program manager's leadership audience. You will be given a list of
workstreams, each with a RAG status (RED/AMBER/GREEN/CLOSED) and a list of
facts that were computed by deterministic rules, not by you.

Rules:
- The RAG status and facts given to you are ground truth. Do not change,
  soften, or second-guess a status — if a workstream is RED, present it as
  RED.
- Do not invent a fact, a cause, or a next step that isn't directly
  supported by the given facts. If you don't know why something is stale,
  say it's stale — don't guess a reason.
- Be concise and direct. No filler ("It's worth noting that...").
- Group by status: RED first, then AMBER, then GREEN. Omit CLOSED
  workstreams from the main body — list them in a one-line "Closed this
  period" footer only.
- For each workstream, one or two sentences max, referencing the actual
  facts. Don't repeat the raw dates verbatim if the fact already states it
  clearly — just don't contradict them.

Output format:

# Executive Status Rollup — {date}

## 🔴 Red — Needs Attention
(one line per RED workstream, or "None" if empty)

## 🟡 Amber — Watch
(one line per AMBER workstream, or "None" if empty)

## 🟢 Green — On Track
(one line per GREEN workstream, or "None" if empty)

## Summary
One short paragraph: overall portfolio health, and the single most
important thing leadership should know this period.

---
Closed this period: (comma-separated list of CLOSED workstream names, or "None")
"""


def narrate(scored_workstreams: list, date_str: str, api_key: str, model: str = "claude-sonnet-5") -> str:
    """
    scored_workstreams: list of {key, name, status, facts} dicts.
    api_key passed explicitly rather than read from os.environ — this
    project's config can resolve the key from a sibling repo's .env as a
    fallback (see config.py), and that resolved value only ever lives in
    the cfg dict, never gets exported back into the process environment.
    Reading os.environ here directly would silently miss it.
    """
    client = anthropic.Anthropic(api_key=api_key)

    lines = []
    for ws in scored_workstreams:
        lines.append(f"### {ws['name']} ({ws['key']})")
        lines.append(f"Status: {ws['status']}")
        for fact in ws["facts"]:
            lines.append(f"- {fact}")
        lines.append("")
    input_block = "\n".join(lines)

    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT.replace("{date}", date_str),
        messages=[{
            "role": "user",
            "content": f"Here are this period's scored workstreams:\n\n{input_block}",
        }],
    )
    text_blocks = [block.text for block in msg.content if block.type == "text"]
    return "\n".join(text_blocks)
