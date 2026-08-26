#!/usr/bin/env python3
"""
Executive Status Rollup — pulls Jira, scores workstreams deterministically,
narrates with Claude, tracks week-over-week RAG flips.

Usage:
  python run_rollup.py                    # print + save to ~/exec-status-rollup.md
  python run_rollup.py --out FILE
  python run_rollup.py --slack-channel exec-status-rollup
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

load_dotenv(Path(__file__).parent / ".env")

from config import load_config
from jira_client import build_workstreams
from health_scorer import score_workstream
from narrator import narrate
from trend import diff_and_update

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Executive Status Rollup")
    parser.add_argument("--out", default="~/exec-status-rollup.md")
    parser.add_argument("--slack-channel", default=None, help="Post the rollup to this Slack channel")
    parser.add_argument("--model", default="claude-sonnet-5")
    args = parser.parse_args()

    cfg = load_config()
    missing = [k for k in ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"] if not cfg[k]]
    if missing:
        console.print(f"[red]Missing Jira config:[/] {', '.join(missing)}")
        sys.exit(1)
    if not cfg["ANTHROPIC_API_KEY"]:
        console.print("[red]Missing ANTHROPIC_API_KEY[/]")
        sys.exit(1)

    today = date.today()
    date_str = today.strftime("%A, %B %-d, %Y")

    console.print(f"[bold cyan]Fetching workstreams from {cfg['JIRA_PROJECT_KEY']}...[/]")
    workstreams = build_workstreams(cfg)

    scored = []
    for ws in workstreams:
        result = score_workstream(ws, today=today)
        scored.append({"key": ws["key"], "name": ws["name"], "status": result.status, "facts": result.facts})

    # ── RAG summary table ──
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold dim")
    table.add_column("Status", justify="center")
    table.add_column("Key")
    table.add_column("Workstream")
    status_style = {"RED": "bold red", "AMBER": "bold yellow", "GREEN": "bold green", "CLOSED": "dim"}
    for ws in scored:
        table.add_row(f"[{status_style[ws['status']]}]{ws['status']}[/]", ws["key"], ws["name"][:55])
    console.print(table)

    # ── Week-over-week trend ──
    changes = diff_and_update(scored, run_date=today.isoformat())
    if changes:
        console.print("\n[bold]Status changes since last run:[/]")
        for c in changes:
            arrow = "[red]regressed[/]" if c["to_status"] == "RED" else "[green]improved[/]" if c["to_status"] == "GREEN" else "[yellow]changed[/]"
            console.print(f"  {arrow} {c['name']}: {c['from_status']} -> {c['to_status']}")

    # ── Narrate ──
    active = [ws for ws in scored if ws["status"] != "CLOSED"]
    closed = [ws for ws in scored if ws["status"] == "CLOSED"]
    console.print(f"\n[bold cyan]Narrating {len(active)} active workstreams with Claude...[/]")
    report = narrate(scored, date_str, api_key=cfg["ANTHROPIC_API_KEY"], model=args.model)

    if changes:
        change_lines = "\n".join(
            f"- {c['name']}: {c['from_status']} → {c['to_status']}" for c in changes
        )
        report += f"\n\n## Changed Since Last Run\n{change_lines}\n"

    console.print()
    console.print(Markdown(report))

    out_path = Path(args.out).expanduser()
    out_path.write_text(report)
    console.print(f"\n[green]✓[/] Saved to {out_path}")

    if args.slack_channel:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        import os
        import re

        if not cfg["SLACK_USER_TOKEN"]:
            console.print("[yellow]--slack-channel given but SLACK_USER_TOKEN is not set — skipping.[/]")
        else:
            client = WebClient(token=cfg["SLACK_USER_TOKEN"])
            slack_text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", re.sub(r"^#+\s*(.+)$", r"*\1*", report, flags=re.MULTILINE))
            try:
                resp = client.conversations_list(types="public_channel,private_channel", limit=200)
                match = next((c for c in resp["channels"] if c["name"] == args.slack_channel), None)
                if not match:
                    console.print(f"[yellow]#{args.slack_channel} not found or you're not a member.[/]")
                else:
                    client.chat_postMessage(channel=match["id"], text=slack_text)
                    console.print(f"[green]✓[/] Posted to #{args.slack_channel}")
            except SlackApiError as e:
                console.print(f"[red]Slack post failed:[/] {e.response['error']}")


if __name__ == "__main__":
    main()
