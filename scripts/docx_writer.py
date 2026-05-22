"""
docx_writer.py — Write a per-meeting Word document into the routed OneDrive
folder. Called by the meetings-digest skill at runtime.

Input: a JSON file describing the meeting + extracted items.
Output: one .docx file in {onedrive_base}/Plaud Meetings/{meeting_type}/
        named '<YYYY-MM-DD HHMM> — <title-preview>.docx'

Input JSON shape:
{
  "meeting_type": "Kingsway Pharma",         # routed folder
  "recording_title": "Kingsway Pharma w/ John Smith",
  "recorded_at": "2026-05-22T14:30:00-04:00",
  "duration_minutes": 47.3,
  "speakers": ["Garrett", "John Smith"],
  "source_file_id": "rec_abc123",
  "transcript_excerpt": "...first 500 chars...",   # used for the routing audit
  "action_items": [ {action, owner, due, priority, context, source_timestamp}, ... ],
  "decisions":   [ {what, why, source_timestamp}, ... ],
  "open_questions": [ {question, raised_by, source_timestamp}, ... ],
  "notable_quotes": [ {quote, speaker, source_timestamp}, ... ]
}

Usage:
    python3 docx_writer.py --input /tmp/meeting.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
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
    """Make a string safe for Windows + Mac filesystems."""
    s = re.sub(r'[\\/:*?"<>|]', "", s)        # forbidden chars
    s = re.sub(r"\s+", " ", s).strip()        # collapse whitespace
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s or "untitled"


def resolve_recording_datetime(recorded_at_iso: str | None) -> datetime:
    if not recorded_at_iso:
        return datetime.now()
    try:
        # tolerate trailing Z
        return datetime.fromisoformat(recorded_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now()


def write_docx(meeting: dict[str, Any], output_path: Path) -> None:
    doc = Document()

    # ---- Heading ----
    h = doc.add_heading(meeting.get("recording_title") or "Untitled Meeting", level=1)

    # ---- Meta line ----
    recorded = resolve_recording_datetime(meeting.get("recorded_at"))
    duration = meeting.get("duration_minutes")
    speakers = meeting.get("speakers") or []
    mtype = meeting.get("meeting_type") or "Uncategorized"

    meta = doc.add_paragraph()
    meta_runs = [
        ("Date: ", True),
        (recorded.strftime("%A, %B %d, %Y at %I:%M %p"), False),
    ]
    if duration:
        meta_runs += [("\nDuration: ", True), (f"{int(duration)} min", False)]
    if speakers:
        meta_runs += [("\nSpeakers: ", True), (", ".join(speakers), False)]
    meta_runs += [("\nMeeting type: ", True), (mtype, False)]
    for text, bold in meta_runs:
        r = meta.add_run(text)
        r.bold = bold
        r.font.size = Pt(10)

    doc.add_paragraph()  # spacing

    # ---- Action items (☐ prefix so it visually reads as a checklist) ----
    doc.add_heading("Action items", level=2)
    items = meeting.get("action_items") or []
    if items:
        for item in items:
            p = doc.add_paragraph(style="List Bullet")
            box = p.add_run("☐ ")
            box.font.size = Pt(11)
            r = p.add_run(item.get("action", "(no text)"))
            r.bold = True
            # Owner / due / priority on second line
            details = []
            if item.get("owner"):
                details.append(f"Owner: {item['owner']}")
            if item.get("due"):
                details.append(f"Due: {item['due']}")
            if item.get("priority"):
                details.append(f"Priority: {item['priority']}")
            if item.get("context"):
                details.append(f"Context: {item['context']}")
            if item.get("source_timestamp"):
                details.append(f"@ {item['source_timestamp']}")
            if details:
                sub = doc.add_paragraph()
                sub.paragraph_format.left_indent = Inches(0.5)
                sub.paragraph_format.space_before = Pt(0)
                sr = sub.add_run("   " + " · ".join(details))
                sr.italic = True
                sr.font.size = Pt(9)
                sr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    else:
        doc.add_paragraph("(no action items extracted)")

    # ---- Decisions ----
    doc.add_heading("Decisions made", level=2)
    decisions = meeting.get("decisions") or []
    if decisions:
        for d in decisions:
            p = doc.add_paragraph(style="List Bullet")
            r = p.add_run(d.get("what", "(no text)"))
            r.bold = True
            if d.get("why"):
                p.add_run(f" — {d['why']}")
            if d.get("source_timestamp"):
                ts = doc.add_paragraph()
                ts.paragraph_format.left_indent = Inches(0.5)
                ts.paragraph_format.space_before = Pt(0)
                ts_run = ts.add_run(f"   @ {d['source_timestamp']}")
                ts_run.italic = True
                ts_run.font.size = Pt(9)
                ts_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    else:
        doc.add_paragraph("(none)")

    # ---- Open questions ----
    doc.add_heading("Open questions", level=2)
    questions = meeting.get("open_questions") or []
    if questions:
        for q in questions:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(q.get("question", "(no text)"))
            if q.get("raised_by"):
                p.add_run(f"  — raised by {q['raised_by']}")
            if q.get("source_timestamp"):
                p.add_run(f"  @ {q['source_timestamp']}")
    else:
        doc.add_paragraph("(none)")

    # ---- Notable quotes ----
    quotes = meeting.get("notable_quotes") or []
    if quotes:
        doc.add_heading("Notable quotes", level=2)
        for q in quotes:
            p = doc.add_paragraph(style="Intense Quote")
            r = p.add_run(q.get("quote", "(no text)"))
            attribution_bits = []
            if q.get("speaker"):
                attribution_bits.append(q["speaker"])
            if q.get("source_timestamp"):
                attribution_bits.append(q["source_timestamp"])
            if attribution_bits:
                attrib = doc.add_paragraph()
                attrib.paragraph_format.left_indent = Inches(0.5)
                ar = attrib.add_run(" — " + " @ ".join(attribution_bits))
                ar.italic = True
                ar.font.size = Pt(9)

    # ---- Footer ----
    doc.add_paragraph()
    f = doc.add_paragraph()
    fr = f.add_run(
        f"Generated by Plaud Meetings Digest on {datetime.now().strftime('%Y-%m-%d %H:%M')}.  "
        f"Recording ID: {meeting.get('source_file_id', '?')}"
    )
    fr.italic = True
    fr.font.size = Pt(8)
    fr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # ---- Save ----
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


def resolve_output_path(meeting: dict[str, Any], base_dir: Path) -> Path:
    """
    Compute the .docx output path under base_dir / 'Plaud Meetings' /
    <meeting_type> / '<YYYY-MM-DD HHMM> <title-preview>.docx'
    """
    recorded = resolve_recording_datetime(meeting.get("recorded_at"))
    mtype = meeting.get("meeting_type") or "Uncategorized"
    title = meeting.get("recording_title") or "Untitled"

    folder = base_dir / "Plaud Meetings" / sanitize_filename(mtype, 40)
    filename = f"{recorded.strftime('%Y-%m-%d %H%M')} {sanitize_filename(title)}.docx"

    return folder / filename


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to JSON file with meeting data")
    parser.add_argument("--output", help="Explicit output path (overrides config-based routing)")
    args = parser.parse_args()

    config = load_config()
    base_dir_str = config.get("destination", {}).get("onedrive_folder")
    if not base_dir_str:
        sys.stderr.write("ERROR: destination.onedrive_folder not configured. Re-run install.\n")
        return 1

    base_dir = Path(base_dir_str).expanduser()
    if not base_dir.exists():
        sys.stderr.write(f"WARNING: OneDrive folder doesn't exist at {base_dir}; creating.\n")
        base_dir.mkdir(parents=True, exist_ok=True)

    in_path = Path(args.input)
    if not in_path.exists():
        sys.stderr.write(f"ERROR: input JSON missing: {in_path}\n")
        return 1
    meeting = json.loads(in_path.read_text(encoding="utf-8"))

    out_path = Path(args.output) if args.output else resolve_output_path(meeting, base_dir)
    write_docx(meeting, out_path)

    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
