#!/usr/bin/env python3
"""
notion-write.py — Writes ONE Notion database row per meeting recording.

v2.0.0 schema: each row = one meeting. The full recap (action items,
decisions, open questions, notable quotes) goes in the page body of the row.
Properties capture the meeting metadata (title, type, date, counts, etc.)
for filtering/sorting in the Notion UI.

Called by the meetings-digest skill at runtime. Input is the same JSON shape
docx_writer.py accepts — one meeting per invocation.

Usage:
    python3 notion-write.py --input /tmp/meeting.json

Exit codes:
    0 — success (row created)
    1 — config or input error
    2 — Notion API error (auth, schema mismatch, rate limit)
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
        print(f"ERROR: config not found at {CONFIG_PATH}. Run install.", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def rich_text(s: str, bold: bool = False, italic: bool = False, code: bool = False) -> list[dict[str, Any]]:
    if not s:
        return []
    s = s[:2000]  # Notion's per-rich-text cap
    span: dict[str, Any] = {"type": "text", "text": {"content": s}}
    annotations = {}
    if bold:   annotations["bold"] = True
    if italic: annotations["italic"] = True
    if code:   annotations["code"] = True
    if annotations:
        span["annotations"] = annotations
    return [span]


def block_h2(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": rich_text(text)},
    }


def block_para(text: str, italic: bool = False) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text(text, italic=italic)},
    }


def block_bullet(text: str, bold_lead: str | None = None) -> dict[str, Any]:
    spans: list[dict[str, Any]] = []
    if bold_lead:
        spans.extend(rich_text(bold_lead, bold=True))
    spans.extend(rich_text(text))
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": spans},
    }


def block_todo(text: str, bold_lead: str | None = None, checked: bool = False) -> dict[str, Any]:
    """A Notion to-do block — renders as a checkbox the client can click to mark done."""
    spans: list[dict[str, Any]] = []
    if bold_lead:
        spans.extend(rich_text(bold_lead, bold=True))
    spans.extend(rich_text(text))
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": spans, "checked": checked},
    }


def block_quote(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "quote",
        "quote": {"rich_text": rich_text(text)},
    }


def build_blocks(meeting: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Notion blocks rendering the meeting recap into the page body."""
    blocks: list[dict[str, Any]] = []

    # ---- Metadata header ----
    meta_parts = []
    if meeting.get("recorded_at"):
        meta_parts.append(meeting["recorded_at"][:16].replace("T", " "))
    if meeting.get("duration_minutes"):
        meta_parts.append(f"{int(meeting['duration_minutes'])} min")
    if meeting.get("speakers"):
        meta_parts.append("Speakers: " + ", ".join(meeting["speakers"]))
    if meeting.get("meeting_type"):
        meta_parts.append(f"Type: {meeting['meeting_type']}")
    if meta_parts:
        blocks.append(block_para(" · ".join(meta_parts), italic=True))

    # ---- Action items (rendered as checkboxes so the client can tick them off) ----
    blocks.append(block_h2("Action items"))
    items = meeting.get("action_items") or []
    if items:
        for it in items:
            primary = it.get("action", "(no text)")
            details = []
            if it.get("owner"):            details.append(f"Owner: {it['owner']}")
            if it.get("due"):              details.append(f"Due: {it['due']}")
            if it.get("priority"):         details.append(f"Priority: {it['priority']}")
            if it.get("context"):          details.append(f"Context: {it['context']}")
            if it.get("source_timestamp"): details.append(f"@ {it['source_timestamp']}")
            suffix = f"  — {' · '.join(details)}" if details else ""
            blocks.append(block_todo(suffix, bold_lead=primary, checked=False))
    else:
        blocks.append(block_para("(no action items extracted)", italic=True))

    # ---- Decisions ----
    blocks.append(block_h2("Decisions made"))
    decisions = meeting.get("decisions") or []
    if decisions:
        for d in decisions:
            primary = d.get("what", "(no text)")
            suffix_parts = []
            if d.get("why"):              suffix_parts.append(d["why"])
            if d.get("source_timestamp"): suffix_parts.append(f"@ {d['source_timestamp']}")
            suffix = f"  — {' · '.join(suffix_parts)}" if suffix_parts else ""
            blocks.append(block_bullet(suffix, bold_lead=primary))
    else:
        blocks.append(block_para("(none)", italic=True))

    # ---- Open questions ----
    blocks.append(block_h2("Open questions"))
    questions = meeting.get("open_questions") or []
    if questions:
        for q in questions:
            primary = q.get("question", "(no text)")
            suffix_parts = []
            if q.get("raised_by"):        suffix_parts.append(f"raised by {q['raised_by']}")
            if q.get("source_timestamp"): suffix_parts.append(f"@ {q['source_timestamp']}")
            suffix = f"  — {' · '.join(suffix_parts)}" if suffix_parts else ""
            blocks.append(block_bullet(suffix, bold_lead=primary))
    else:
        blocks.append(block_para("(none)", italic=True))

    # ---- Notable quotes ----
    quotes = meeting.get("notable_quotes") or []
    if quotes:
        blocks.append(block_h2("Notable quotes"))
        for q in quotes:
            blocks.append(block_quote(q.get("quote", "")))
            attribution_parts = []
            if q.get("speaker"):          attribution_parts.append(q["speaker"])
            if q.get("source_timestamp"): attribution_parts.append(q["source_timestamp"])
            if attribution_parts:
                blocks.append(block_para(" — " + " @ ".join(attribution_parts), italic=True))

    # ---- Footer ----
    footer = (
        f"Generated by Plaud Meetings Digest on "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}.  "
        f"Recording ID: {meeting.get('source_file_id', '?')}"
    )
    blocks.append(block_para(footer, italic=True))

    return blocks


def build_properties(meeting: dict[str, Any]) -> dict[str, Any]:
    """Build the Notion DB row properties from the meeting dict."""
    props: dict[str, Any] = {
        "Title": {"title": rich_text(meeting.get("recording_title") or "Untitled Meeting")},
        "Status": {"select": {"name": "New"}},
    }

    if meeting.get("meeting_type"):
        props["Meeting Type"] = {"select": {"name": meeting["meeting_type"]}}

    if meeting.get("recorded_at"):
        props["Date"] = {"date": {"start": meeting["recorded_at"]}}

    if meeting.get("duration_minutes") is not None:
        try:
            props["Duration"] = {"number": round(float(meeting["duration_minutes"]), 1)}
        except (TypeError, ValueError):
            pass

    if meeting.get("speakers"):
        speakers_str = ", ".join(meeting["speakers"]) if isinstance(meeting["speakers"], list) else str(meeting["speakers"])
        props["Speakers"] = {"rich_text": rich_text(speakers_str)}

    if meeting.get("action_items") is not None:
        props["Action Items"] = {"number": len(meeting.get("action_items") or [])}
    if meeting.get("decisions") is not None:
        props["Decisions"] = {"number": len(meeting.get("decisions") or [])}
    if meeting.get("open_questions") is not None:
        props["Open Questions"] = {"number": len(meeting.get("open_questions") or [])}

    if meeting.get("source_file_id"):
        props["Source File ID"] = {"rich_text": rich_text(meeting["source_file_id"])}

    return props


def write_meeting_row(token: str, database_id: str, meeting: dict[str, Any]) -> tuple[bool, str]:
    blocks = build_blocks(meeting)
    # Notion limits children per create call to 100
    first_batch = blocks[:100]
    rest = blocks[100:]

    payload = {
        "parent": {"database_id": database_id},
        "properties": build_properties(meeting),
        "children": first_batch,
    }

    try:
        resp = requests.post(
            f"{NOTION_API}/pages",
            headers=headers(token),
            json=payload,
            timeout=20,
        )
    except requests.RequestException as e:
        return False, f"network error: {e}"

    if resp.status_code != 200:
        try:
            body = resp.json()
            return False, f"{resp.status_code} {body.get('code', '')}: {body.get('message', resp.text[:300])}"
        except Exception:
            return False, f"{resp.status_code}: {resp.text[:300]}"

    page_id = resp.json().get("id", "")
    page_url = resp.json().get("url", "")

    # Append remaining blocks in 100-block chunks if needed
    for i in range(0, len(rest), 100):
        chunk = rest[i:i + 100]
        try:
            r2 = requests.patch(
                f"{NOTION_API}/blocks/{page_id}/children",
                headers=headers(token),
                json={"children": chunk},
                timeout=20,
            )
            if r2.status_code != 200:
                return False, f"Appending blocks chunk {i//100 + 2} failed: {r2.status_code} {r2.text[:300]}"
        except requests.RequestException as e:
            return False, f"network error appending blocks: {e}"

    return True, page_url or page_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to JSON file describing the meeting")
    args = parser.parse_args()

    config = load_config()
    dest = config.get("destination", {})

    if dest.get("type") != "notion":
        print(f"ERROR: destination type is '{dest.get('type')}', not 'notion'", file=sys.stderr)
        return 1

    token = dest.get("notion_api_key")
    db_id = dest.get("notion_database_id")
    if not token or not db_id:
        print("ERROR: notion_api_key or notion_database_id missing in config. Re-run install.", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input JSON missing: {input_path}", file=sys.stderr)
        return 1

    try:
        meeting = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: input JSON invalid: {e}", file=sys.stderr)
        return 1

    ok, info = write_meeting_row(token, db_id, meeting)
    if not ok:
        print(f"ERROR: {info}", file=sys.stderr)
        return 2

    print(f"✓ Notion row created: {info}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
