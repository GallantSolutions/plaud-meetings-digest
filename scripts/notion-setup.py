#!/usr/bin/env python3
"""
notion-setup.py — Creates the Plaud Meeting Action Items database in Notion.

Called by install.sh when the user picks the Notion output destination.
Idempotent: if a database with the same name already exists under the parent
page, this script reuses it rather than creating a duplicate.

Usage:
    python3 notion-setup.py --token <NOTION_TOKEN> \\
                            --parent-page <PARENT_PAGE_ID> \\
                            --output <PATH_TO_WRITE_DB_ID>

The Notion token must have access to the parent page (operator/recipient
explicitly shared the integration with the page before running install.sh).

Database schema:
    - Action        (title)
    - Context       (select)
    - Owner         (rich_text)
    - Due           (date)
    - Status        (select: Open, In progress, Done, Blocked, Dropped)
    - Priority      (select: High, Medium, Low)
    - Source        (rich_text)
    - Source date   (date)
    - Week          (rich_text)
    - Created       (created_time)
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
DB_NAME = "Plaud Meeting Action Items"


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def search_existing_database(token: str, parent_page_id: str) -> str | None:
    """Look for an existing database with the standard name under the parent page."""
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
        title_text = "".join(t.get("plain_text", "") for t in title_arr)
        if title_text.strip() == DB_NAME:
            parent = result.get("parent", {})
            if parent.get("type") == "page_id":
                if parent["page_id"].replace("-", "") == parent_page_id.replace("-", ""):
                    return result["id"]
    return None


def create_database(token: str, parent_page_id: str) -> str:
    """Create the database under the parent page."""
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": DB_NAME}}],
        "properties": {
            "Action": {"title": {}},
            "Context": {
                "select": {
                    "options": [
                        {"name": "RANK",         "color": "blue"},
                        {"name": "Client work",  "color": "green"},
                        {"name": "Portfolio",    "color": "purple"},
                        {"name": "Internal ops", "color": "yellow"},
                        {"name": "Personal",     "color": "gray"},
                    ]
                }
            },
            "Owner":       {"rich_text": {}},
            "Due":         {"date": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Open",        "color": "default"},
                        {"name": "In progress", "color": "blue"},
                        {"name": "Done",        "color": "green"},
                        {"name": "Blocked",     "color": "red"},
                        {"name": "Dropped",     "color": "gray"},
                    ]
                }
            },
            "Priority": {
                "select": {
                    "options": [
                        {"name": "High",   "color": "red"},
                        {"name": "Medium", "color": "yellow"},
                        {"name": "Low",    "color": "gray"},
                    ]
                }
            },
            "Source":      {"rich_text": {}},
            "Source date": {"date": {}},
            "Week":        {"rich_text": {}},
            "Created":     {"created_time": {}},
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

    # Normalize parent page ID (Notion accepts both with and without dashes; we strip)
    parent_id = args.parent_page.replace("-", "").strip()
    if len(parent_id) != 32:
        print(f"ERROR: parent page ID must be 32 hex chars, got {len(parent_id)}", file=sys.stderr)
        return 1

    # Search first (idempotent)
    existing = search_existing_database(args.token, parent_id)
    if existing:
        print(f"Found existing database with ID {existing[:8]}... (reusing)")
        with open(args.output, "w") as f:
            f.write(existing.replace("-", ""))
        return 0

    # Create
    print("Creating new Notion database...")
    db_id = create_database(args.token, parent_id)
    db_id_clean = db_id.replace("-", "")

    with open(args.output, "w") as f:
        f.write(db_id_clean)

    print(f"Created database {db_id_clean[:8]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
