"""
Jira client — fetches issues for a project and groups them into workstreams.

Uses /rest/api/3/search/jql, not the old /rest/api/3/search endpoint — Atlassian
retired that one (returns HTTP 410 as of this writing; discovered by testing
against the real project rather than assuming the old docs were current).

A "workstream" here is an Epic (or a top-level issue with no parent, e.g. a
lone Feature) plus whatever children roll up under it. The health scorer
operates on workstreams, not raw issues.
"""

import requests
from requests.auth import HTTPBasicAuth

FIELDS = "summary,status,issuetype,priority,duedate,updated,assignee,labels,parent"


def fetch_issues(cfg: dict) -> list:
    auth = HTTPBasicAuth(cfg["JIRA_EMAIL"], cfg["JIRA_API_TOKEN"])
    issues = []
    next_page_token = None

    while True:
        params = {
            "jql": f"project={cfg['JIRA_PROJECT_KEY']} ORDER BY updated DESC",
            "maxResults": 100,
            "fields": FIELDS,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        resp = requests.get(
            f"{cfg['JIRA_URL']}/rest/api/3/search/jql",
            auth=auth,
            headers={"Accept": "application/json"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        issues.extend(data.get("issues", []))

        if data.get("isLast", True) or not data.get("nextPageToken"):
            break
        next_page_token = data["nextPageToken"]

    return issues


def _normalize(issue: dict) -> dict:
    f = issue["fields"]
    return {
        "key": issue["key"],
        "summary": f.get("summary", ""),
        "type": f["issuetype"]["name"],
        "status": f["status"]["name"],
        "status_category": f["status"]["statusCategory"]["key"],  # "new" | "indeterminate" | "done"
        "priority": (f.get("priority") or {}).get("name", "Unset"),
        "due_date": f.get("duedate"),
        "updated": f.get("updated"),
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "labels": f.get("labels", []),
        "parent_key": (f.get("parent") or {}).get("key"),
    }


def build_workstreams(cfg: dict) -> list:
    """
    Group issues into workstreams: one entry per Epic (or per top-level
    issue with no parent), with its children nested underneath.
    """
    raw_issues = fetch_issues(cfg)
    issues = [_normalize(i) for i in raw_issues]

    by_key = {i["key"]: i for i in issues}
    children_by_parent = {}
    for i in issues:
        if i["parent_key"]:
            children_by_parent.setdefault(i["parent_key"], []).append(i)

    workstreams = []
    for i in issues:
        if i["parent_key"] is not None:
            continue  # this issue is a child, not a workstream root
        workstreams.append({
            "key": i["key"],
            "name": i["summary"],
            "type": i["type"],
            "status": i["status"],
            "status_category": i["status_category"],
            "due_date": i["due_date"],
            "updated": i["updated"],
            "children": children_by_parent.get(i["key"], []),
        })

    return workstreams
