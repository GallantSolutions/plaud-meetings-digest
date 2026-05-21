#!/usr/bin/env python3
"""
notion-query.py — Query the Plaud Meeting Action Items Notion database for
items in a date range, by status, or by other filters. Used by the
weekly-rollup skill to gather the substrate it synthesizes.

Reads the Notion API key + database ID from the standard config file.
Output is a JSON array written to --output (or stdout if --output not given).

Usage:
    # Items where Source date is in the range
    python3 notion-query.py --since 2026-05-14 --until 2026-05-20 \\
                            --output /tmp/week-items.json

    # Items still Open and Created before a date (i.e., carry-overs)
    python3 notion-query.py --status Open --created-before 2026-05-14 \\
                            --output /tmp/carry-overs.json

    # Items moved to Done last week (using Created as a proxy if needed)
    python3 notion-query.py --status Done --created-since 2026-05-14 \\
                            --output /tmp/closed.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
RATE_LIMIT_RETRIES = 5


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        print(f"ERROR: config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def build_filter(args: argparse.Namespace) -> dict[str, Any] | None:
    """Build the Notion `filter` object from CLI args. Returns None for unfiltered."""
    conditions: list[dict[str, Any]] = []

    if args.since:
        conditions.append({
            "property": "Source date",
            "date": {"on_or_after": args.since},
        })
    if args.until:
        conditions.append({
            "property": "Source date",
            "date": {"on_or_before": args.until},
        })

    if args.created_since:
        conditions.append({
            "timestamp": "created_time",
            "created_time": {"on_or_after": f"{args.created_since}T00:00:00.000Z"},
        })
    if args.created_before:
        conditions.append({
            "timestamp": "created_time",
            "created_time": {"before": f"{args.created_before}T00:00:00.000Z"},
        })

    if args.status:
        conditions.append({
            "property": "Status",
            "select": {"equals": args.status},
        })
    if args.context:
        conditions.append({
            "property": "Context",
            "select": {"equals": args.context},
        })
    if args.priority:
        conditions.append({
            "property": "Priority",
            "select": {"equals": args.priority},
        })

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def query_pages(token: str, database_id: str, query_body: dict[str, Any]) -> list[dict[str, Any]]:
    """Page through Notion query results, handling pagination + rate limits."""
    all_pages: list[dict[str, Any]] = []
    start_cursor: str | None = None

    while True:
        body = dict(query_body)
        body["page_size"] = 100
        if start_cursor:
            body["start_cursor"] = start_cursor

        retries = 0
        while True:
            resp = requests.post(
                f"{NOTION_API}/databases/{database_id}/query",
                headers=headers(token),
                json=body,
                timeout=20,
            )
            if resp.status_code == 429:
                if retries >= RATE_LIMIT_RETRIES:
                    print("ERROR: Notion rate-limit exhausted", file=sys.stderr)
                    sys.exit(2)
                wait = float(resp.headers.get("Retry-After", "1"))
                time.sleep(wait)
                retries += 1
                continue
            break

        if resp.status_code != 200:
            print(f"ERROR: Notion query failed: {resp.status_code} {resp.text[:300]}", file=sys.stderr)
            sys.exit(2)

        data = resp.json()
        all_pages.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return all_pages


def plain_text(rich_text_arr: list[dict[str, Any]]) -> str:
    return "".join(t.get("plain_text", "") for t in (rich_text_arr or []))


def shape_row(page: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Notion page into a plain dict for downstream synthesis."""
    props = page.get("properties", {})

    def text_prop(name: str) -> str:
        p = props.get(name, {})
        if p.get("type") == "title":
            return plain_text(p.get("title", []))
        if p.get("type") == "rich_text":
            return plain_text(p.get("rich_text", []))
        return ""

    def select_prop(name: str) -> str | None:
        p = props.get(name, {})
        sel = p.get("select")
        return sel.get("name") if sel else None

    def date_prop(name: str) -> str | None:
        p = props.get(name, {})
        d = p.get("date")
        return d.get("start") if d else None

    return {
        "id": page.get("id", "").replace("-", ""),
        "url": page.get("url", ""),
        "action": text_prop("Action"),
        "context": select_prop("Context"),
        "owner": text_prop("Owner"),
        "due": date_prop("Due"),
        "status": select_prop("Status"),
        "priority": select_prop("Priority"),
        "source": text_prop("Source"),
        "source_date": date_prop("Source date"),
        "week": text_prop("Week"),
        "created_time": page.get("created_time"),
        "last_edited_time": page.get("last_edited_time"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help='Source date >= YYYY-MM-DD')
    parser.add_argument("--until", help='Source date <= YYYY-MM-DD')
    parser.add_argument("--created-since", help='Created on or after YYYY-MM-DD')
    parser.add_argument("--created-before", help='Created before YYYY-MM-DD')
    parser.add_argument("--status", help="Filter by Status select value (Open / In progress / Done / etc.)")
    parser.add_argument("--context", help="Filter by Context select value")
    parser.add_argument("--priority", help="Filter by Priority (High / Medium / Low)")
    parser.add_argument("--output", help="Path to write JSON output (default: stdout)")
    args = parser.parse_args()

    config = load_config()
    dest = config.get("destination", {})

    if dest.get("type") != "notion":
        print(f"ERROR: destination type is '{dest.get('type')}', not 'notion'. Cannot query.", file=sys.stderr)
        return 1

    token = dest.get("notion_api_key")
    db_id = dest.get("notion_database_id")
    if not token or not db_id:
        print("ERROR: notion_api_key or notion_database_id missing in config", file=sys.stderr)
        return 1

    filt = build_filter(args)
    query_body: dict[str, Any] = {}
    if filt:
        query_body["filter"] = filt
    query_body["sorts"] = [
        {"property": "Source date", "direction": "ascending"},
    ]

    pages = query_pages(token, db_id, query_body)
    rows = [shape_row(p) for p in pages]

    output_json = json.dumps(rows, indent=2)

    if args.output:
        Path(args.output).write_text(output_json)
        print(f"Wrote {len(rows)} item(s) to {args.output}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
