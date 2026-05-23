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
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_ALIGN_VERTICAL
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    sys.stderr.write("ERROR: python-docx not installed. Run: python3 -m pip install python-docx\n")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Brand colors (subtle, professional — used for section dividers + accents)
# ---------------------------------------------------------------------------

GALLANT_DEEP_NAVY = RGBColor(0x1A, 0x2A, 0x44)  # primary section headers
GALLANT_GRAPHITE  = RGBColor(0x3D, 0x4A, 0x59)  # secondary text
GALLANT_MUTED     = RGBColor(0x6C, 0x75, 0x83)  # metadata / footer
GALLANT_DIVIDER   = RGBColor(0xCC, 0xCC, 0xCC)  # horizontal rules
GALLANT_CRITICAL  = RGBColor(0xA8, 0x1F, 0x1F)  # 21+ day overdue (deep red, not bright)
GALLANT_ATTENTION = RGBColor(0xB8, 0x6E, 0x18)  # 14+ day attention (deep amber)


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
# Styling helpers (professional, emoji-free)
# ---------------------------------------------------------------------------

def _set_run(run, *, bold=False, italic=False, size=11, color=None, font="Calibri") -> None:
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = font
    if color:
        run.font.color.rgb = color


def _section_header(doc, text: str) -> None:
    """ALL CAPS section header in deep navy with a subtle underline rule."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text.upper())
    _set_run(r, bold=True, size=12, color=GALLANT_DEEP_NAVY)
    # Add a thin bottom border to the paragraph for a clean section rule
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "CCCCCC")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _meta_line(p, text: str) -> None:
    r = p.add_run(text)
    _set_run(r, italic=False, size=9, color=GALLANT_MUTED)


def _body_run(p, text: str, *, bold=False, color=None) -> None:
    r = p.add_run(text)
    _set_run(r, bold=bold, size=11, color=color or GALLANT_GRAPHITE)


def _detail_line(doc, parts: list[str], indent_in: float = 0.35) -> None:
    """A small-text detail line indented under a primary item (no bullet)."""
    if not parts:
        return
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(indent_in)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("    ".join(parts))
    _set_run(r, italic=True, size=9, color=GALLANT_MUTED)


def _aging_label(days_open: int, warn_days: int, loud_days: int) -> tuple[str, RGBColor]:
    """Return (text label, color) for a carry-over's aging tier."""
    if days_open >= loud_days:
        return ("CRITICAL", GALLANT_CRITICAL)
    if days_open >= warn_days:
        return ("ATTENTION", GALLANT_ATTENTION)
    return ("OPEN", GALLANT_GRAPHITE)


def _set_cell_text(cell, text: str, *, bold=False, color=None, size=10, italic=False) -> None:
    """Replace cell text with styled run."""
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    _set_run(r, bold=bold, italic=italic, size=size, color=color or GALLANT_GRAPHITE)


def _shade_cell(cell, hex_color: str) -> None:
    """Apply a subtle background shade to a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


# ---------------------------------------------------------------------------
# Write the rollup — professional, emoji-free, pharma-corporate styling
# ---------------------------------------------------------------------------

def _format_date_range(week_start_iso: str, week_end_iso: str) -> str:
    """Render '2026-05-25' + '2026-05-29' → 'May 25–29, 2026' (or cross-month variant)."""
    try:
        ws = datetime.fromisoformat(week_start_iso)
        we = datetime.fromisoformat(week_end_iso)
        if ws.month == we.month:
            return f"{ws.strftime('%B')} {ws.day}–{we.day}, {ws.year}"
        return f"{ws.strftime('%B')} {ws.day} – {we.strftime('%B')} {we.day}, {ws.year}"
    except Exception:
        return f"{week_start_iso} – {week_end_iso}"


def write_rollup(rollup: dict[str, Any], output_path: Path, warn_days: int, loud_days: int) -> None:
    doc = Document()

    # Set document-wide base font to Calibri 11pt
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    mtype = rollup.get("meeting_type", "Untitled")
    week_start = rollup.get("week_start", "")
    week_end = rollup.get("week_end", "")
    generated_at = rollup.get("generated_at", datetime.now().isoformat(timespec="minutes"))
    date_range = _format_date_range(week_start, week_end)

    # ===== TITLE BLOCK ======================================================
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_after = Pt(2)
    t_run = title_p.add_run(f"{mtype.upper()} — WEEKLY ROLLUP")
    _set_run(t_run, bold=True, size=20, color=GALLANT_DEEP_NAVY)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(2)
    s_run = sub_p.add_run(f"Week of {date_range}")
    _set_run(s_run, bold=False, size=13, color=GALLANT_GRAPHITE)

    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(6)
    _meta_line(meta_p, f"Generated {generated_at[:16].replace('T', ' ')}")

    # ===== OPEN ITEMS FROM PRIOR WEEKS (TOP — most load-bearing) ===========
    carry = rollup.get("carry_overs") or []
    _section_header(doc, "Open Items from Prior Weeks")

    if carry:
        carry_sorted = sorted(carry, key=lambda c: int(c.get("days_open", 0) or 0), reverse=True)

        table = doc.add_table(rows=1, cols=4)
        table.autofit = False
        table.allow_autofit = False
        widths = [Inches(3.6), Inches(0.9), Inches(1.0), Inches(1.5)]
        # Header row
        hdr = table.rows[0]
        hdr_cells = hdr.cells
        for i, label in enumerate(["Action Item", "Days Open", "Status", "Source Meeting"]):
            _set_cell_text(hdr_cells[i], label, bold=True, color=GALLANT_DEEP_NAVY, size=10)
            _shade_cell(hdr_cells[i], "F2F4F7")
            hdr_cells[i].width = widths[i]

        # Data rows
        for co in carry_sorted:
            days = int(co.get("days_open", 0) or 0)
            status_text, status_color = _aging_label(days, warn_days, loud_days)
            row = table.add_row()
            for i in range(4):
                row.cells[i].width = widths[i]
            _set_cell_text(row.cells[0], co.get("action", ""), size=10)
            _set_cell_text(row.cells[1], str(days), size=10, bold=True, color=status_color)
            _set_cell_text(row.cells[2], status_text, size=10, bold=True, color=status_color)
            _set_cell_text(row.cells[3], co.get("source_recording_title", ""), size=10, italic=True, color=GALLANT_MUTED)
    else:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        r = p.add_run("All prior-week items closed. No carry-overs this week.")
        _set_run(r, italic=True, size=11, color=GALLANT_GRAPHITE)

    # ===== NEXT WEEK'S FOCUS PICKS =========================================
    focus_picks = rollup.get("focus_picks") or []
    if focus_picks:
        _section_header(doc, "Next Week's Focus Picks")
        for idx, fp in enumerate(focus_picks, start=1):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            _body_run(p, f"{idx}.  ", bold=True, color=GALLANT_DEEP_NAVY)
            _body_run(p, fp.get("action", ""), bold=True, color=GALLANT_DEEP_NAVY)
            if fp.get("reason"):
                rp = doc.add_paragraph()
                rp.paragraph_format.left_indent = Inches(0.35)
                rp.paragraph_format.space_before = Pt(0)
                rp.paragraph_format.space_after = Pt(2)
                _body_run(rp, "Rationale: ", bold=True)
                _body_run(rp, fp["reason"])
            details = []
            if fp.get("owner"):
                details.append(f"Owner: {fp['owner']}")
            if fp.get("due"):
                details.append(f"Due: {fp['due']}")
            if fp.get("source_recording"):
                details.append(f"From: {fp['source_recording']}")
            _detail_line(doc, details)

    # ===== HIGH PRIORITY (THIS WEEK) =======================================
    high = rollup.get("high_priority") or []
    if high:
        _section_header(doc, "High Priority (This Week)")
        for item in high:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(2)
            _body_run(p, "•  ", bold=True, color=GALLANT_DEEP_NAVY)
            _body_run(p, item.get("action", ""), bold=True)
            details = []
            if item.get("owner"):
                details.append(f"Owner: {item['owner']}")
            if item.get("due"):
                details.append(f"Due: {item['due']}")
            if item.get("source_recording_title"):
                details.append(f"From: {item['source_recording_title']}")
            _detail_line(doc, details)

    # ===== BY CONTEXT ======================================================
    by_context = rollup.get("by_context") or {}
    if by_context:
        _section_header(doc, "Action Items by Context")
        for ctx_name, items in by_context.items():
            if not items:
                continue
            ctx_p = doc.add_paragraph()
            ctx_p.paragraph_format.space_before = Pt(8)
            ctx_p.paragraph_format.space_after = Pt(2)
            _body_run(ctx_p, ctx_name, bold=True, color=GALLANT_DEEP_NAVY)
            for it in items:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.left_indent = Inches(0.2)
                _body_run(p, "•  ", bold=True)
                _body_run(p, it.get("action", ""))
                details = []
                if it.get("owner"):
                    details.append(f"Owner: {it['owner']}")
                if it.get("due"):
                    details.append(f"Due: {it['due']}")
                if it.get("priority"):
                    details.append(f"Priority: {it['priority']}")
                if it.get("source_recording_title"):
                    details.append(f"From: {it['source_recording_title']}")
                _detail_line(doc, details, indent_in=0.55)

    # ===== DECISIONS RECORDED ==============================================
    decisions = rollup.get("decisions") or []
    if decisions:
        _section_header(doc, "Decisions Recorded")
        for d in decisions:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(2)
            _body_run(p, "•  ", bold=True, color=GALLANT_DEEP_NAVY)
            _body_run(p, d.get("what", ""), bold=True)
            if d.get("why"):
                rp = doc.add_paragraph()
                rp.paragraph_format.left_indent = Inches(0.35)
                rp.paragraph_format.space_before = Pt(0)
                rp.paragraph_format.space_after = Pt(2)
                _body_run(rp, "Rationale: ", bold=True)
                _body_run(rp, d["why"])
            if d.get("source_recording_title"):
                _detail_line(doc, [f"From: {d['source_recording_title']}"])

    # ===== OPEN QUESTIONS ==================================================
    questions = rollup.get("open_questions") or []
    if questions:
        _section_header(doc, "Open Questions")
        for q in questions:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(2)
            _body_run(p, "•  ", bold=True, color=GALLANT_DEEP_NAVY)
            _body_run(p, q.get("question", ""), bold=True)
            details = []
            if q.get("raised_by"):
                details.append(f"Raised by: {q['raised_by']}")
            if q.get("source_recording_title"):
                details.append(f"From: {q['source_recording_title']}")
            _detail_line(doc, details)

    # ===== OBSERVATIONS (formerly Themes) ==================================
    themes = rollup.get("themes") or []
    if themes:
        _section_header(doc, "Observations")
        for th in themes:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            _body_run(p, "•  ", bold=True, color=GALLANT_DEEP_NAVY)
            _body_run(p, th.get("title", ""), bold=True)
            if th.get("body"):
                body = doc.add_paragraph()
                body.paragraph_format.left_indent = Inches(0.35)
                body.paragraph_format.space_before = Pt(0)
                body.paragraph_format.space_after = Pt(4)
                _body_run(body, th["body"])

    # ===== SUMMARY FOOTER ==================================================
    stats = rollup.get("stats", {})
    if stats:
        _section_header(doc, "Summary")
        summary_p = doc.add_paragraph()
        summary_p.paragraph_format.space_before = Pt(4)
        bits = [
            f"{stats.get('meetings_processed', 0)} meetings processed",
            f"{stats.get('action_items_new', 0)} new action items",
            f"{stats.get('carry_overs_open', 0)} carry-overs still open",
        ]
        _body_run(summary_p, "    |    ".join(bits))

    # ===== GENERATED BY (small print, bottom of doc) =======================
    doc.add_paragraph()
    foot = doc.add_paragraph()
    fr = foot.add_run(f"Generated by Plaud Meetings Digest on {generated_at[:16].replace('T', ' ')}.")
    _set_run(fr, italic=True, size=8, color=GALLANT_MUTED)

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
