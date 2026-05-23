"""
rollup_docx_writer.py — Write the weekly rollup Word document.

Used by the weekly-rollup skill. Takes a synthesis JSON (produced by the skill
after it queries state_store.py for the week's items) and writes a single
.docx into the meeting type's `_weekly/` subfolder in OneDrive.

For this client, only Kingsway Pharma triggers a rollup. The skill is
responsible for filtering items by meeting_type before passing them here.

Input JSON shape:
{
  "meeting_type": "Kingsway Pharma",
  "week_start": "2026-05-18",       # ISO date (Monday)
  "week_end":   "2026-05-22",       # ISO date (Friday)
  "generated_at": "2026-05-22T17:30:00-04:00",
  "stats": {
    "meetings_processed": 7,
    "action_items_new": 23,
    "carry_overs_open": 5,
    "themes_detected": 3
  },
  "focus_picks":   [ {action, owner, reason, due, source_recording}, ... ],
  "high_priority": [ {...same shape as action_items in state_store... }, ... ],
  "by_context":    { "<context>": [ items... ], ... },
  "carry_overs":   [ {action, days_open, owner, source_recording}, ... ],
  "decisions":     [ {what, why, source_recording}, ... ],
  "open_questions":[ {question, raised_by, source_recording}, ... ],
  "themes":        [ {title, body}, ... ]
}

Usage:
    python3 rollup_docx_writer.py --input /tmp/rollup.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json"

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    sys.stderr.write("ERROR: python-docx not installed. Run: python3 -m pip install python-docx\n")
    sys.exit(1)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        sys.stderr.write(f"ERROR: config not found at {CONFIG_PATH}\n")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sanitize_filename(s: str, max_len: int = 80) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len].rstrip() or "untitled"


# ---------------------------------------------------------------------------
# Helpers for repeated styling
# ---------------------------------------------------------------------------

def _muted(p, text: str) -> None:
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)


def _bullet_item(doc, primary: str, secondary_bits: list[str] | None = None) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(primary).bold = True
    if secondary_bits:
        sub = doc.add_paragraph()
        sub.paragraph_format.left_indent = Inches(0.5)
        sub.paragraph_format.space_before = Pt(0)
        _muted(sub, "   " + " · ".join(secondary_bits))


def _aging_emoji(days_open: int, warn_days: int, loud_days: int) -> str:
    if days_open >= loud_days:
        return "🚨 "
    if days_open >= warn_days:
        return "⚠️ "
    return ""


# ---------------------------------------------------------------------------
# Write the rollup
# ---------------------------------------------------------------------------

def write_rollup(rollup: dict[str, Any], output_path: Path, warn_days: int, loud_days: int) -> None:
    doc = Document()

    mtype = rollup.get("meeting_type", "Untitled")
    week_start = rollup.get("week_start", "")
    week_end = rollup.get("week_end", "")
    generated_at = rollup.get("generated_at", datetime.now().isoformat(timespec="minutes"))

    # ---- Title ----
    title = doc.add_heading(f"{mtype} — Weekly Rollup", level=1)
    sub = doc.add_paragraph()
    sr = sub.add_run(f"Week of {week_start} → {week_end}")
    sr.bold = True
    sr.font.size = Pt(12)

    meta = doc.add_paragraph()
    _muted(meta, f"Generated {generated_at[:16].replace('T', ' ')} by Plaud Meetings Digest")
    doc.add_paragraph()

    # ---- Stats ----
    stats = rollup.get("stats", {})
    if stats:
        st = doc.add_paragraph()
        bits = [
            f"{stats.get('meetings_processed', 0)} meetings processed",
            f"{stats.get('action_items_new', 0)} new action items",
            f"{stats.get('carry_overs_open', 0)} carry-overs still open",
        ]
        st_run = st.add_run(" · ".join(bits))
        st_run.font.size = Pt(10)
        st_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # ---- Focus picks ----
    focus_picks = rollup.get("focus_picks") or []
    if focus_picks:
        doc.add_heading("🎯 Next week's focus", level=2)
        for fp in focus_picks:
            p = doc.add_paragraph(style="List Number")
            p.add_run(fp.get("action", "")).bold = True
            if fp.get("reason"):
                sub = doc.add_paragraph()
                sub.paragraph_format.left_indent = Inches(0.5)
                sub.paragraph_format.space_before = Pt(0)
                _muted(sub, f"   Why: {fp['reason']}")
            details = []
            if fp.get("owner"):
                details.append(f"Owner: {fp['owner']}")
            if fp.get("due"):
                details.append(f"Due: {fp['due']}")
            if fp.get("source_recording"):
                details.append(f"From: {fp['source_recording']}")
            if details:
                sub = doc.add_paragraph()
                sub.paragraph_format.left_indent = Inches(0.5)
                sub.paragraph_format.space_before = Pt(0)
                _muted(sub, "   " + " · ".join(details))

    # ---- High priority ----
    high = rollup.get("high_priority") or []
    if high:
        doc.add_heading("🔴 High priority (open)", level=2)
        for item in high:
            bits = []
            if item.get("owner"):
                bits.append(f"Owner: {item['owner']}")
            if item.get("due"):
                bits.append(f"Due: {item['due']}")
            if item.get("source_recording_title"):
                bits.append(f"From: {item['source_recording_title']}")
            _bullet_item(doc, item.get("action", ""), bits)

    # ---- By context ----
    by_context = rollup.get("by_context") or {}
    if by_context:
        doc.add_heading("By context", level=2)
        for ctx_name, items in by_context.items():
            if not items:
                continue
            doc.add_heading(ctx_name, level=3)
            for it in items:
                bits = []
                if it.get("owner"):
                    bits.append(f"Owner: {it['owner']}")
                if it.get("due"):
                    bits.append(f"Due: {it['due']}")
                if it.get("priority"):
                    bits.append(f"Priority: {it['priority']}")
                if it.get("source_recording_title"):
                    bits.append(f"From: {it['source_recording_title']}")
                _bullet_item(doc, it.get("action", ""), bits)

    # ---- Carry-overs ----
    carry = rollup.get("carry_overs") or []
    if carry:
        doc.add_heading("🔁 Carry-overs from prior weeks", level=2)
        for co in carry:
            days = int(co.get("days_open", 0) or 0)
            prefix = _aging_emoji(days, warn_days, loud_days)
            label = f"{prefix}[Open {days} days] {co.get('action', '')}"
            bits = []
            if co.get("owner"):
                bits.append(f"Owner: {co['owner']}")
            if co.get("source_recording_title"):
                bits.append(f"From: {co['source_recording_title']}")
            _bullet_item(doc, label, bits)

    # ---- Decisions ----
    decisions = rollup.get("decisions") or []
    if decisions:
        doc.add_heading("🧠 Decisions made", level=2)
        for d in decisions:
            label = d.get("what", "")
            if d.get("why"):
                label = f"{label} — {d['why']}"
            bits = []
            if d.get("source_recording_title"):
                bits.append(f"From: {d['source_recording_title']}")
            _bullet_item(doc, label, bits)

    # ---- Open questions ----
    questions = rollup.get("open_questions") or []
    if questions:
        doc.add_heading("❓ Open questions still unresolved", level=2)
        for q in questions:
            label = q.get("question", "")
            bits = []
            if q.get("raised_by"):
                bits.append(f"Raised by: {q['raised_by']}")
            if q.get("source_recording_title"):
                bits.append(f"From: {q['source_recording_title']}")
            _bullet_item(doc, label, bits)

    # ---- Themes ----
    themes = rollup.get("themes") or []
    if themes:
        doc.add_heading("📊 Themes", level=2)
        for th in themes:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(th.get("title", "")).bold = True
            if th.get("body"):
                body = doc.add_paragraph()
                body.paragraph_format.left_indent = Inches(0.5)
                body.add_run(th["body"])

    # ---- Footer ----
    doc.add_paragraph()
    f = doc.add_paragraph()
    fr = f.add_run(f"Generated by Plaud Meetings Digest on {generated_at[:16].replace('T', ' ')}.")
    fr.italic = True
    fr.font.size = Pt(8)
    fr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


def resolve_routing_entry(meeting_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """Local copy of docx_writer.resolve_routing_entry — keep in sync. We
    avoid cross-script imports because launchd's restricted PYTHONPATH
    makes inter-script imports brittle."""
    routing = config.get("meeting_routing", {})
    for entry in routing.get("types", []):
        if entry.get("folder") == meeting_type:
            return entry
    fallback_folder = routing.get("fallback_folder") or "Uncategorized"
    if meeting_type == fallback_folder:
        return {
            "folder": fallback_folder,
            "filename_prefix": routing.get("fallback_filename_prefix", "") or "",
            "rollup_filename_prefix": None,
            "weekly_subfolders": False,
            "include_in_weekly_rollup": False,
        }
    return {}


def week_folder_name(recorded: datetime, prefix: str) -> str:
    """Local copy of docx_writer.week_folder_name — keep in sync."""
    iso_year, iso_week, iso_weekday = recorded.isocalendar()
    monday = recorded - timedelta(days=iso_weekday - 1)
    friday = monday + timedelta(days=4)
    if monday.month == friday.month:
        date_range = f"{monday.strftime('%b')} {monday.day}-{friday.day}, {monday.year}"
    else:
        date_range = f"{monday.strftime('%b')} {monday.day}-{friday.strftime('%b')} {friday.day}, {monday.year}"
    if prefix:
        return f"{prefix}.{date_range} (Week {iso_week})"
    return f"{date_range} (Week {iso_week})"


def resolve_output_path(rollup: dict[str, Any], base_dir: Path, config: dict[str, Any]) -> Path:
    """
    Rollup goes inside the same per-week subfolder as the week's meeting
    files (when the meeting type has weekly_subfolders=true). Filename uses
    the type's rollup_filename_prefix (e.g. 'KPR').

    Folder:   base / 'Plaud Meetings' / {meeting_type} / {KPM.<date range>, <year> (Week <N>)}/
    Filename: '{rollup_prefix}.{date range}, {year} (Week {N}).docx'
              e.g. 'KPR.May 25-29, 2026 (Week 22).docx'

    Backwards compat: if the type has weekly_subfolders=false OR no
    rollup_filename_prefix is set, falls back to the v2.2.1 location at
    {meeting_type}/_weekly/{meeting_filename_prefix}.Weekly Rollup
    ({year}-W{ww}).docx. (Realistically rollups only run for types with
    include_in_weekly_rollup=true, which currently means Kingsway Pharma
    which uses the new path; the fallback is for future-flexibility.)
    """
    mtype = rollup.get("meeting_type") or "Untitled"
    week_start_iso = rollup.get("week_start", datetime.now().strftime("%Y-%m-%d"))
    try:
        week_start_dt = datetime.fromisoformat(week_start_iso)
    except ValueError:
        week_start_dt = datetime.now()
    iso_year, iso_week, _ = week_start_dt.isocalendar()

    entry = resolve_routing_entry(mtype, config)
    meeting_prefix = entry.get("filename_prefix", "") or ""
    rollup_prefix = entry.get("rollup_filename_prefix") or ""
    weekly_subfolders = bool(entry.get("weekly_subfolders"))

    mtype_folder = base_dir / "Plaud Meetings" / sanitize_filename(mtype, 40)

    if weekly_subfolders and rollup_prefix:
        # New layout (v2.2.2+): rollup lives inside the week folder
        week_folder = mtype_folder / sanitize_filename(week_folder_name(week_start_dt, meeting_prefix), 90)
        # Filename uses the rollup prefix + same date-range label
        # Build the date-range part WITHOUT the meeting prefix (since the
        # filename uses the rollup prefix instead)
        date_range_part = week_folder_name(week_start_dt, "").lstrip(".").strip()
        filename = f"{rollup_prefix}.{date_range_part}.docx"
        return week_folder / filename

    # Backwards-compat fallback (pre-v2.2.2 or types without rollup prefix)
    folder = mtype_folder / "_weekly"
    if meeting_prefix:
        filename = f"{meeting_prefix}.Weekly Rollup ({iso_year}-W{iso_week:02d}).docx"
    else:
        filename = f"{iso_year}-W{iso_week:02d} {sanitize_filename(mtype, 40)} Weekly Rollup.docx"
    return folder / filename


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to JSON synthesis file")
    parser.add_argument("--output", help="Explicit output path (overrides routing)")
    args = parser.parse_args()

    config = load_config()
    base_dir_str = config.get("destination", {}).get("onedrive_folder")
    if not base_dir_str:
        sys.stderr.write("ERROR: destination.onedrive_folder not configured.\n")
        return 1
    base_dir = Path(base_dir_str).expanduser()

    in_path = Path(args.input)
    if not in_path.exists():
        sys.stderr.write(f"ERROR: input JSON missing: {in_path}\n")
        return 1
    rollup = json.loads(in_path.read_text(encoding="utf-8"))

    rollup_cfg = config.get("weekly_rollup", {})
    warn_days = int(rollup_cfg.get("carry_over_warn_days", 14))
    loud_days = int(rollup_cfg.get("carry_over_loud_days", 21))

    out_path = Path(args.output) if args.output else resolve_output_path(rollup, base_dir, config)
    write_rollup(rollup, out_path, warn_days, loud_days)

    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
