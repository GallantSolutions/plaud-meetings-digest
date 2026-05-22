#!/usr/bin/env python3
"""
notion-setup.py — Creates the "Plaud Meetings" database in Notion.

v2.0.0 schema change: each ROW is now ONE MEETING (not one action item).
The full recap (action items, decisions, open questions, quotes) lives in
the page body of each row.

Called by install.sh when the user picks the Notion output destination.
Idempotent: if a database with the same name already exists under the parent
page, this script reuses it rather than creating a duplicate.

Usage:
    python3 notion-setup.py --token <NOTION_TOKEN> \\
                            --parent-page <PARENT_PAGE_ID> \\
                            --output <PATH_TO_WRITE_DB_ID>

Database schema (one row per meeting recording):
    - Title          (title)        — meeting title (e.g., "Kingsway Pharma w/ John Smith")
    - Meeting Type   (select)       — Kingsway Pharma / Church / Personal / Uncategorized
    - Date           (date)         — when the meeting was recorded
    - Duration       (number)       — minutes
    - Speakers       (rich_text)    — comma-separated names
    - Action Items   (number)       — count of action items extracted
    - Decisions      (number)       — count of decisions
    - Open Questions (number)       — count
    - Status         (select)       — New / Reviewed / Archived
    - Source File ID (rich_text)    — Plaud's recording ID (for dedup audit)
    - Created        (created_time)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: python3 -m pip install requests", file=sys.stderr)
    sys.exit(1)

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"
DB_NAME = "Plaud Meetings"


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def search_existing_database(token: str, parent_page_id: str) -> str | None:
    """Look for an existing database with the canonical name under the parent page."""
    resp = requests.post(
        f"{NOTION_API}/search",
        headers=headers(token),
        json={
            "query": DB_NAME,
            "filter": {"value": "database", "property": "object"},
            "page_size": 50,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    for result in resp.json().get("results", []):
        title_arr = result.get("title", [])
        title_text = "".join(t.get("plain_text", "") for t in title_arr).strip()
        if title_text == DB_NAME:
            parent = result.get("parent", {})
            if parent.get("type") == "page_id":
                if parent["page_id"].replace("-", "") == parent_page_id.replace("-", ""):
                    return result["id"]
    return None


def create_database(token: str, parent_page_id: str) -> str:
    """Create the v2.0.0 'Plaud Meetings' database under the parent page."""
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": DB_NAME}}],
        "properties": {
            "Title":         {"title": {}},
            "Meeting Type": {
                "select": {
                    "options": [
                        {"name": "Kingsway Pharma", "color": "blue"},
                        {"name": "Church",          "color": "purple"},
                        {"name": "Personal",        "color": "gray"},
                        {"name": "Uncategorized",   "color": "default"},
                    ]
                }
            },
            "Date":           {"date": {}},
            "Duration":       {"number": {"format": "number"}},
            "Speakers":       {"rich_text": {}},
            "Action Items":   {"number": {"format": "number"}},
            "Decisions":      {"number": {"format": "number"}},
            "Open Questions": {"number": {"format": "number"}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "New",      "color": "yellow"},
                        {"name": "Reviewed", "color": "green"},
                        {"name": "Archived", "color": "gray"},
                    ]
                }
            },
            "Source File ID": {"rich_text": {}},
            "Created":        {"created_time": {}},
        },
    }

    resp = requests.post(
        f"{NOTION_API}/databases",
        headers=headers(token),
        json=payload,
        timeout=20,
    )

    if resp.status_code != 200:
        print(f"ERROR: Notion API returned {resp.status_code}", file=sys.stderr)
        try:
            err: dict[str, Any] = resp.json()
            print(f"  message: {err.get('message', 'unknown')}", file=sys.stderr)
            print(f"  code:    {err.get('code', 'unknown')}", file=sys.stderr)
        except Exception:
            print(f"  body: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)

    return resp.json()["id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Notion integration token")
    parser.add_argument("--parent-page", required=True, help="Parent page ID (32-char hex)")
    parser.add_argument("--output", required=True, help="Path to write the resulting DB ID")
    args = parser.parse_args()

    parent_id = args.parent_page.replace("-", "").strip()
    if len(parent_id) != 32:
        print(f"ERROR: parent page ID must be 32 hex chars, got {len(parent_id)}", file=sys.stderr)
        return 1

    existing = search_existing_database(args.token, parent_id)
    if existing:
        print(f"Found existing database with ID {existing[:8]}... (reusing)")
        with open(args.output, "w") as f:
            f.write(existing.replace("-", ""))
        return 0

    print("Creating new Notion database 'Plaud Meetings'...")
    db_id = create_database(args.token, parent_id)
    db_id_clean = db_id.replace("-", "")

    with open(args.output, "w") as f:
        f.write(db_id_clean)

    print(f"Created database {db_id_clean[:8]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
