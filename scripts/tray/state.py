"""
state.py — Per-week checklist state for the Plaud tray widget.

Stores which action items the operator has checked off in the current ISO
week. Auto-resets on Monday (new ISO week) so the widget always reflects
the current week's open list. The weekly rollup script reads this state
(via tray_bridge.py) to skip closed items in the Friday rollup.

State file: ~/.config/plaud-tray/state.json on POSIX
            %APPDATA%/plaud-tray/state.json on Windows

State shape (v2.4.0-alpha):
{
  "week_iso": "2026-W22",
  "rollup_fired_at": "2026-05-30T16:30:00-04:00",   // null until Friday rollup runs
  "items": {
    "<16-char item id>": {
      "done": true,
      "done_at": "2026-05-28T14:23:01-04:00",
      "text": "Send Anthony the Q3 forecast deck",      // v2.4.0-alpha — needed by rollup bridge
      "bucket": "KP",                                    // v2.4.0-alpha — KP/CM/CH/PE
      "source_meeting": "KPM.Marketing Sync (Ben...)"    // v2.4.0-alpha — needed by rollup bridge
    },
    ...
  }
}

Backward compat: legacy entries lacking text/bucket/source_meeting still
load and toggle correctly — only the rollup bridge needs the new fields,
and it falls back to live re-parse when an entry is bare.

Concurrency: writes are atomic via write-to-temp + os.replace, so the
rollup script and the tray app can read simultaneously without seeing a
half-written file.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path


def _state_dir() -> Path:
    """Platform-appropriate config directory."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "plaud-tray"
    return Path.home() / ".config" / "plaud-tray"


def state_path() -> Path:
    return _state_dir() / "state.json"


def current_week_iso(today: date | None = None) -> str:
    today = today or date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _empty_state() -> dict:
    return {"week_iso": current_week_iso(), "rollup_fired_at": None, "items": {}}


def load_state() -> dict:
    """Read state; auto-reset on new ISO week."""
    path = state_path()
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if data.get("week_iso") != current_week_iso():
        return _empty_state()
    if "items" not in data or not isinstance(data["items"], dict):
        data["items"] = {}
    data.setdefault("rollup_fired_at", None)
    return data


def save_state(state: dict) -> None:
    """Atomic write — temp file + replace."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(path))


def set_done(item_id: str, done: bool, *, text: str = "", bucket: str = "",
             source_meeting: str = "") -> dict:
    """Toggle an item; return the updated state.
    text/bucket/source_meeting are stored alongside so the rollup bridge
    can resolve back to a state_store item_id without re-parsing every
    .docx in OneDrive."""
    state = load_state()
    if done:
        existing = state["items"].get(item_id, {})
        state["items"][item_id] = {
            "done": True,
            "done_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "text": text or existing.get("text", ""),
            "bucket": bucket or existing.get("bucket", ""),
            "source_meeting": source_meeting or existing.get("source_meeting", ""),
        }
    else:
        state["items"].pop(item_id, None)
    save_state(state)
    return state


def mark_rollup_fired(when: datetime | None = None) -> dict:
    """Record that Friday's rollup ran. The widget uses this to clear the
    Done tab — closed items have been ratified by the rollup and the
    operator's working surface should be fresh for the next week."""
    state = load_state()
    state["rollup_fired_at"] = (when or datetime.now().astimezone()).isoformat(timespec="seconds")
    save_state(state)
    return state


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp tolerantly; return None on falsy/malformed.
    Accepts trailing 'Z' as +00:00 (Python <3.11 didn't until fromisoformat
    was extended; do it explicitly for forward-compat)."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def clear_done_after_rollup() -> dict:
    """Drop every done entry whose done_at predates rollup_fired_at.
    Idempotent — safe to call on every refresh.

    Uses parsed-datetime compare (not ISO-string lex compare) so the math
    stays correct across DST shifts and operator timezone changes.
    """
    state = load_state()
    fired_raw = state.get("rollup_fired_at")
    fired_dt = _parse_iso(fired_raw)
    if fired_dt is None:
        return state
    kept = {}
    for iid, entry in state["items"].items():
        if entry.get("done"):
            done_dt = _parse_iso(entry.get("done_at"))
            # Drop if we have a parseable done_at that's at-or-before the
            # rollup fire time. Unparseable done_at (legacy / corrupted) is
            # treated as old and cleared, since it was definitely done before
            # the rollup_fired_at marker was written.
            if done_dt is None or done_dt <= fired_dt:
                continue
        kept[iid] = entry
    state["items"] = kept
    save_state(state)
    return state


def is_done(item_id: str, state: dict | None = None) -> bool:
    state = state or load_state()
    return bool(state.get("items", {}).get(item_id, {}).get("done"))


def annotate(items: list[dict]) -> list[dict]:
    """Add `done` + `done_at` fields to each item dict based on persisted state."""
    state = load_state()
    annotated = []
    for item in items:
        entry = state["items"].get(item["id"], {})
        annotated.append({
            **item,
            "done": bool(entry.get("done")),
            "done_at": entry.get("done_at"),
        })
    return annotated


def stats(items: list[dict]) -> dict:
    """Counts for the widget footer + tab badges."""
    done = sum(1 for i in items if i.get("done"))
    total = len(items)
    state = load_state()
    return {
        "done": done,
        "open": total - done,
        "total": total,
        "week_iso": current_week_iso(),
        "rollup_fired_at": state.get("rollup_fired_at"),
    }
