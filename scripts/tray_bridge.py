"""
tray_bridge.py — Bridge between the Plaud tray widget's closure surface
and state_store.closures.jsonl.

The tray (scripts/tray/) writes its own state.json keyed by 16-char SHA256
of (docx_filename + "\\x00" + action_text). state_store closures use an
8-char SHA1 of (source_file_id + "|" + action_text.lower()). Different
ID schemes because the tray sees .docx artifacts on disk while
state_store sees the upstream Plaud cloud file IDs.

This bridge runs on Friday at rollup time:
  1. Load the tray state.json (only done items from THIS week).
  2. Load action-items.jsonl rows from the current week.
  3. For each tray-done item, find the matching JSONL row by:
        (a) action text equality (case-insensitive, whitespace-folded), AND
        (b) source_recording_title appearing inside the docx filename
            (the docx stem is "<prefix>.<title> (<attendees>)").
  4. Emit a closure record per match — same shape state_store.append_closures
     already consumes, with closed_via="tray".
  5. After successful rollup write, the calling skill invokes
     mark_rollup_fired() so the tray's Done tab clears on next refresh.

If the tray state file is missing, or has no done items, this is a no-op
and the rollup proceeds unaffected.

Usage:
    # Harvest closures and print as JSONL to stdout (weekly-rollup SKILL.md
    # pipes this to state_store.append_closures):
    python3 scripts/tray_bridge.py --harvest

    # Record that the rollup fired (clears Done tab on next refresh):
    python3 scripts/tray_bridge.py --mark-fired
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# Sibling module — added to sys.path by the install layout (tray/ is a
# subpackage of scripts/). When run standalone from the scripts/ dir,
# Python finds it directly.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from tray import state as tray_state  # noqa: E402

ITEMS_JSONL = Path.home() / ".claude" / "skills" / "meetings-digest" / "state" / "action-items.jsonl"


def _normalize(text: str) -> str:
    """Whitespace-fold + lowercase + strip leading bullet glyphs.
    Matches how state_store derives its lookup key and how the tray's
    parser strips bullet prefixes."""
    s = re.sub(r"^[•\-\*]\s+", "", text or "").strip().lower()
    return re.sub(r"\s+", " ", s)


def _docx_stem_contains_title(docx_stem: str, recording_title: str) -> bool:
    """The tray sees 'KPM.Marketing Sync (Ben, Garrett)' — the JSONL row's
    source_recording_title is the underlying Plaud recording title, e.g.
    'Marketing Sync'. Match if the title appears as a substring after
    stripping the prefix.  Tolerant of case + whitespace."""
    if not (docx_stem and recording_title):
        return False
    # Strip leading "<PREFIX>." segment
    base = re.sub(r"^[A-Z]{2,4}\.", "", docx_stem).strip()
    return recording_title.strip().lower() in base.lower()


def _iter_week_items() -> Iterator[dict]:
    """Yield JSONL rows whose source_recorded_at falls within the current
    ISO week. Skips malformed lines silently — rollup must never block on
    a damaged state row."""
    if not ITEMS_JSONL.exists():
        return
    week_iso = tray_state.current_week_iso()
    for line in ITEMS_JSONL.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        recorded = row.get("source_recorded_at") or row.get("created_at") or ""
        try:
            rec_dt = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
        except ValueError:
            continue
        iso_year, iso_week, _ = rec_dt.date().isocalendar()
        if f"{iso_year}-W{iso_week:02d}" == week_iso:
            yield row


def _load_existing_closure_ids() -> set[str]:
    """Read state_store.closures.jsonl directly so we can dedup before
    appending. Avoids importing state_store (which has its own sys.path
    expectations); the JSONL format is stable + read-only here."""
    closures_path = Path.home() / ".claude" / "skills" / "meetings-digest" / "state" / "closures.jsonl"
    if not closures_path.exists():
        return set()
    ids: set[str] = set()
    for line in closures_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        iid = obj.get("item_id")
        if iid:
            ids.add(iid.upper())
    return ids


def harvest_tray_closures() -> list[dict]:
    """Map every done item in tray state.json → a state_store closure
    record. Returns a list of dicts ready for state_store.append_closures().

    Dedups against closures.jsonl already on disk so re-running this on the
    same week (manual retry, rollup re-run) doesn't append duplicates.
    """
    state = tray_state.load_state()
    done_items = [
        (iid, entry) for iid, entry in state.get("items", {}).items()
        if entry.get("done") and entry.get("text")
    ]
    if not done_items:
        return []

    week_rows = list(_iter_week_items())
    if not week_rows:
        return []

    already_closed = _load_existing_closure_ids()

    # Index JSONL rows by normalized action text for O(1) lookup
    by_action: dict[str, list[dict]] = {}
    for row in week_rows:
        key = _normalize(row.get("action", ""))
        if key:
            by_action.setdefault(key, []).append(row)

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    closures: list[dict] = []
    seen_state_ids: set[str] = set()

    for tray_id, entry in done_items:
        key = _normalize(entry["text"])
        candidates = by_action.get(key) or []
        if not candidates:
            continue
        # Prefer the candidate whose source_recording_title matches the
        # tray's source_meeting (docx stem). Falls back to first match
        # when only one candidate exists.
        chosen = None
        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            for c in candidates:
                if _docx_stem_contains_title(
                    entry.get("source_meeting", ""), c.get("source_recording_title", "")
                ):
                    chosen = c
                    break
        if chosen is None:
            continue
        state_id = (chosen.get("item_id") or "").upper()
        if not state_id or state_id in seen_state_ids or state_id in already_closed:
            continue
        seen_state_ids.add(state_id)
        closures.append({
            "item_id": state_id,
            "closed_at": entry.get("done_at") or now_iso,
            "closed_via": "tray",
            "source_rollup": None,
            "action_text": chosen.get("action", ""),
            "tray_id": tray_id,
        })
    return closures


def mark_rollup_fired() -> None:
    """Record that the rollup ran. Idempotent."""
    tray_state.mark_rollup_fired()


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--harvest", action="store_true",
                      help="Print one closure JSON object per line to stdout")
    mode.add_argument("--mark-fired", action="store_true",
                      help="Record that the Friday rollup just fired (clears Done tab)")
    args = ap.parse_args()

    if args.harvest:
        closures = harvest_tray_closures()
        for rec in closures:
            print(json.dumps(rec, ensure_ascii=False))
        sys.stderr.write(f"harvested {len(closures)} tray closure(s)\n")
        return 0

    if args.mark_fired:
        mark_rollup_fired()
        sys.stderr.write("tray rollup_fired_at marker written\n")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
