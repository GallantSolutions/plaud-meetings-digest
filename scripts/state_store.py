"""
state_store.py — Manages the local state for Plaud Meetings Digest:

1. dedup state: which Plaud file IDs have already been processed
   stored at <skill_dir>/state/processed-file-ids.json
2. action items: append-only JSONL of every action item extracted,
   tagged with meeting_type + source recording metadata
   stored at <skill_dir>/state/action-items.jsonl

The action-items.jsonl is what the weekly-rollup skill reads to synthesize
the rollup. Each line is a self-contained JSON object so the file is
append-friendly + survives partial writes.

Cross-platform: uses Path operations only. Works on Mac and Windows.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (cross-platform)
# ---------------------------------------------------------------------------

SKILL_DIR = Path.home() / ".claude" / "skills" / "meetings-digest"
STATE_DIR = SKILL_DIR / "state"
DEDUP_PATH = STATE_DIR / "processed-file-ids.json"
ITEMS_PATH = STATE_DIR / "action-items.jsonl"


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Dedup state — JSON dict of file_id -> ISO timestamp processed
# ---------------------------------------------------------------------------

def load_dedup() -> dict[str, str]:
    if not DEDUP_PATH.exists():
        return {}
    try:
        data = json.loads(DEDUP_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            # tolerate older list-of-objects shape
            return {x["file_id"]: x.get("processed_at", "") for x in data if isinstance(x, dict) and x.get("file_id")}
        return {}
    except json.JSONDecodeError:
        # Corrupted — back up and start fresh
        backup = DEDUP_PATH.with_suffix(".json.bak")
        DEDUP_PATH.rename(backup)
        sys.stderr.write(f"WARNING: dedup state corrupted; backed up to {backup}\n")
        return {}


def mark_processed(file_ids: list[str]) -> None:
    """Atomic write of new dedup state."""
    if not file_ids:
        return
    ensure_state_dir()
    state = load_dedup()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for fid in file_ids:
        state[fid] = now

    _atomic_json_write(DEDUP_PATH, state)


def prune_dedup(retention_days: int) -> int:
    """Drop entries older than retention_days. Returns count pruned."""
    state = load_dedup()
    if not state:
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
    keep: dict[str, str] = {}
    pruned = 0
    for fid, ts in state.items():
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            dt = 0
        if dt >= cutoff:
            keep[fid] = ts
        else:
            pruned += 1
    if pruned:
        _atomic_json_write(DEDUP_PATH, keep)
    return pruned


def already_processed(file_ids: list[str]) -> tuple[list[str], list[str]]:
    """Split into (new, already_processed) lists, preserving order in inputs."""
    state = load_dedup()
    new: list[str] = []
    old: list[str] = []
    for fid in file_ids:
        (old if fid in state else new).append(fid)
    return new, old


# ---------------------------------------------------------------------------
# Action items — append-only JSONL
# ---------------------------------------------------------------------------

@dataclass
class ActionItem:
    action: str
    owner: str
    context: str | None
    due: str | None              # ISO date or null
    priority: str                # High / Medium / Low
    meeting_type: str            # e.g. "Kingsway Pharma" / "Church" / "Personal" / "Uncategorized"
    source_file_id: str
    source_recording_title: str
    source_recorded_at: str | None  # ISO 8601 datetime
    source_timestamp: str | None    # HH:MM:SS into recording
    extracted_at: str               # ISO 8601 UTC, set on append

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def append_items(items: list[ActionItem]) -> None:
    if not items:
        return
    ensure_state_dir()
    with ITEMS_PATH.open("a", encoding="utf-8") as f:
        for it in items:
            f.write(it.to_jsonl() + "\n")


def read_items(
    since: str | None = None,
    until: str | None = None,
    meeting_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Load items from the JSONL, optionally filtered by:
      - since: source_recorded_at >= ISO date (e.g., '2026-05-19')
      - until: source_recorded_at <= ISO date
      - meeting_types: only include rows whose meeting_type is in this list

    Returns list of dicts (raw JSONL records, not ActionItem instances — keeps
    schema-evolution friendly).
    """
    if not ITEMS_PATH.exists():
        return []

    rows: list[dict[str, Any]] = []
    with ITEMS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # skip malformed line; don't abort the whole read
                continue
            if not isinstance(obj, dict):
                continue

            rec_date = obj.get("source_recorded_at") or obj.get("extracted_at") or ""
            # Normalize to ISO date prefix for range comparisons
            rec_date_prefix = rec_date[:10]

            if since and rec_date_prefix and rec_date_prefix < since:
                continue
            if until and rec_date_prefix and rec_date_prefix > until:
                continue
            if meeting_types and obj.get("meeting_type") not in meeting_types:
                continue

            rows.append(obj)

    return rows


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------

def _atomic_json_write(path: Path, data: Any) -> None:
    ensure_state_dir()
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Diagnostic CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dedup-stats")

    p_filter = sub.add_parser("items")
    p_filter.add_argument("--since")
    p_filter.add_argument("--until")
    p_filter.add_argument("--meeting-types", nargs="+")
    p_filter.add_argument("--limit", type=int, default=20)

    args = p.parse_args()

    if args.cmd == "dedup-stats":
        state = load_dedup()
        print(f"Dedup state: {len(state)} processed file IDs")
        for fid, ts in list(state.items())[:5]:
            print(f"  {fid}  →  {ts}")
        if len(state) > 5:
            print(f"  ... and {len(state) - 5} more")
    elif args.cmd == "items":
        rows = read_items(since=args.since, until=args.until, meeting_types=args.meeting_types)
        print(f"Matched {len(rows)} items (showing up to {args.limit}):")
        for r in rows[:args.limit]:
            print(json.dumps(r, ensure_ascii=False))
