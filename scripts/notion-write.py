#!/usr/bin/env python3
"""
notion-write.py — Writes action items to the Plaud Meeting Action Items
Notion database. Called by the meetings-digest skill at runtime.

Reads action items from a JSON file (one array, schema documented in
SKILL.md). Authenticates with the Notion token from config.json. Creates one
database row per action item.

Usage:
    python3 notion-write.py --action-items <path-to-items.json>

Exit codes:
    0 — all items written successfully
    1 — config or input file error (bad path / bad JSON)
    2 — Notion API error (auth, schema mismatch, rate limit)

Action item shape (each):
    {
      "action": "Send Bristol the audit PDF",
      "owner": "Garrett",
      "context": "RANK",
      "due": "2026-05-23",                        // ISO date, optional
      "source_recording": "Bristol discovery call",
      "source_recorded_at": "2026-05-19T14:30Z",  // ISO datetime
      "source_timestamp": "00:23:15",             // HH:MM:SS into recording
      "priority": "High|Medium|Low",              // default Medium
      "week": "2026-W21"                          // ISO week, optional
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: python3 -m pip install requests", file=sys.stderr)
    sys.exit(1)

CONFIG_PATH = Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json"
NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        print(f"ERROR: config not found at {CONFIG_PATH}", file=sys.stderr)
        print("Run install.sh to set up.", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def rich_text(s: str) -> list[dict[str, Any]]:
    if not s:
        return []
    return [{"type": "text", "text": {"content": s[:2000]}}]


def build_properties(item: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {
        "Action": {"title": rich_text(item.get("action", "(no action text)"))},
    }

    if item.get("context"):
        props["Context"] = {"select": {"name": item["context"]}}

    if item.get("owner"):
        props["Owner"] = {"rich_text": rich_text(item["owner"])}

    if item.get("due"):
        props["Due"] = {"date": {"start": item["due"]}}

    priority = item.get("priority", "Medium")
    if priority not in ("High", "Medium", "Low"):
        priority = "Medium"
    props["Priority"] = {"select": {"name": priority}}

    props["Status"] = {"select": {"name": "Open"}}

    source_parts = []
    if item.get("source_recording"):
        source_parts.append(item["source_recording"])
    if item.get("source_timestamp"):
        source_parts.append(f"@ {item['source_timestamp']}")
    if source_parts:
        props["Source"] = {"rich_text": rich_text(" ".join(source_parts))}

    if item.get("source_recorded_at"):
        # Notion's `date` property wants ISO 8601; trim time if needed
        recorded = item["source_recorded_at"]
        if "T" in recorded:
            props["Source date"] = {"date": {"start": recorded}}
        else:
            props["Source date"] = {"date": {"start": recorded}}

    if item.get("week"):
        props["Week"] = {"rich_text": rich_text(item["week"])}

    return props


def write_one(token: str, database_id: str, item: dict[str, Any]) -> tuple[bool, str]:
    payload = {
        "parent": {"database_id": database_id},
        "properties": build_properties(item),
    }
    try:
        resp = requests.post(
            f"{NOTION_API}/pages",
            headers=headers(token),
            json=payload,
            timeout=15,
        )
    except requests.RequestException as e:
        return False, f"network error: {e}"

    if resp.status_code == 200:
        return True, resp.json().get("id", "")

    try:
        body = resp.json()
        msg = body.get("message", resp.text[:300])
        code = body.get("code", "")
        return False, f"{resp.status_code} {code}: {msg}"
    except Exception:
        return False, f"{resp.status_code}: {resp.text[:300]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-items", required=True, help="Path to JSON file with action items array")
    args = parser.parse_args()

    config = load_config()
    dest = config.get("destination", {})

    if dest.get("type") != "notion":
        print(f"ERROR: destination type is '{dest.get('type')}', not 'notion'", file=sys.stderr)
        return 1

    token = dest.get("notion_api_key")
    db_id = dest.get("notion_database_id")
    if not token or not db_id:
        print("ERROR: notion_api_key or notion_database_id missing in config", file=sys.stderr)
        print("Re-run install.sh to fix.", file=sys.stderr)
        return 1

    items_path = Path(args.action_items)
    if not items_path.exists():
        print(f"ERROR: action-items file not found: {items_path}", file=sys.stderr)
        return 1

    try:
        items = json.loads(items_path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: action-items JSON invalid: {e}", file=sys.stderr)
        return 1

    if not isinstance(items, list):
        print("ERROR: action-items must be a JSON array", file=sys.stderr)
        return 1

    if not items:
        print("No action items to write.")
        return 0

    print(f"Writing {len(items)} action item(s) to Notion...")

    written = 0
    failed: list[tuple[int, str]] = []
    for i, item in enumerate(items, start=1):
        ok, info = write_one(token, db_id, item)
        if ok:
            written += 1
        else:
            failed.append((i, info))
            print(f"  ✗ item {i}: {info}", file=sys.stderr)

    print(f"Written: {written}/{len(items)}")
    if failed:
        print(f"Failed:  {len(failed)} (see stderr above)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
