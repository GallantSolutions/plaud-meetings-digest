"""
parser.py — Extract open action items from this week's per-meeting .docx files
written by docx_writer.py into the OneDrive bucket folders.

OneDrive layout produced by the digest:
  {onedrive_base}/Plaud Meetings/{bucket}/{PREFIX}.{date-range} (Week N)/
    {PREFIX_M}.{title} ({attendees}).docx        ← per-meeting (parsed)
    {PREFIX_R}.{date-range} (Week N).docx        ← weekly rollup (skipped)

Buckets per Ben's current config: Kingsway Pharma / Committee / Church / Personal
with filename_prefix KPM / CMM / CHM / PM (per-meeting) and
rollup_filename_prefix KPR / CMR / CHR / PR.

Action-item extraction handles both .docx formats currently in production:
  - v2.3.0+: Plaud-native markdown rendered as bullet paragraphs under a
    case-insensitive "Action Items" heading (the typical case as of 2026-05-28)
  - v2.2.x: legacy structured section with "ACTION ITEMS" caps header and
    "•  " bullet prefix on each item — still present in older docs

The parser is heading-driven, not format-driven: it walks paragraphs, finds
one whose stripped text matches "action items" case-insensitively, then
collects every following non-empty paragraph until the next heading-like
paragraph (bold or ALL CAPS, both used as section headers by docx_writer).
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

try:
    from docx import Document
except ImportError:
    raise SystemExit("python-docx not installed. Run: python3 -m pip install python-docx")


# Bucket display tags used in the widget UI — match the CC's color-coded tags.
# These come from the config's filename_prefix mapped down to 2-letter codes.
BUCKET_TAGS = {
    "KPM": "KP",
    "CMM": "CM",
    "CHM": "CH",
    "PM":  "PE",
}

ACTION_HEADING_RE = re.compile(r"^\s*action items?\s*$", re.IGNORECASE)
BULLET_PREFIX_RE = re.compile(r"^[•\-\*]\s+")  # strip bullet glyphs from start


def current_iso_week_label(today: date | None = None) -> str:
    """Returns the docx_writer's weekly subfolder pattern: 'Month dd-dd, YYYY (Week N)'."""
    today = today or date.today()
    # Find the Monday of the current ISO week
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    iso_year, iso_week, _ = today.isocalendar()
    if monday.month == friday.month:
        date_range = f"{monday.strftime('%B')} {monday.day}-{friday.day}, {monday.year}"
    else:
        date_range = f"{monday.strftime('%B %d')}-{friday.strftime('%B %d')}, {monday.year}"
    return f"{date_range} (Week {iso_week})"


def find_week_folder(bucket_folder: Path, prefix: str, week_label: str) -> Path | None:
    """Find the bucket's current-week subfolder. The folder may not exist yet
    (no meetings landed this week) — return None in that case."""
    if not bucket_folder.exists():
        return None
    target_name = f"{prefix}.{week_label}"
    candidate = bucket_folder / target_name
    if candidate.is_dir():
        return candidate
    # Tolerate slight format variations by glob-matching
    for child in bucket_folder.iterdir():
        if child.is_dir() and child.name.startswith(f"{prefix}.") and f"(Week {week_label.rsplit('(Week ', 1)[-1]}".rstrip(")") in child.name:
            return child
    return None


def _is_heading_paragraph(p) -> bool:
    """A paragraph is a section header iff its text is short + entirely uppercase.
    docx_writer._section_header() always uppercases the heading text via
    `text.upper()`, so this is the unique signal that separates the heading
    from a body paragraph or a bullet (bullets have a bolded '•' glyph but
    the body text is mixed case, so `text.isupper()` correctly distinguishes).

    Limited to text <60 chars to avoid false positives on short shouty
    sentences that might appear in transcripts."""
    text = p.text.strip()
    if not text or len(text) >= 60:
        return False
    # Must contain at least one letter (skip pure-symbol paragraphs)
    if not any(c.isalpha() for c in text):
        return False
    return text.upper() == text


def _iter_action_blocks(doc) -> Iterator[str]:
    """Yield each action-item paragraph text from a parsed Document.
    Walks paragraphs, locates 'Action Items' heading, yields subsequent
    non-empty paragraphs until the next heading."""
    in_section = False
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if ACTION_HEADING_RE.match(text):
            in_section = True
            continue
        if not in_section:
            continue
        # We're inside the Action Items section
        if _is_heading_paragraph(p):
            # Next section started — stop collecting
            return
        # Strip leading bullet glyph if present
        cleaned = BULLET_PREFIX_RE.sub("", text).strip()
        if cleaned:
            yield cleaned


def _item_id(meeting_path: Path, text: str) -> str:
    """Stable hash for state dedup. Same meeting + same text = same id."""
    h = hashlib.sha256()
    h.update(meeting_path.name.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:16]


def parse_meeting_doc(docx_path: Path, bucket_tag: str) -> list[dict]:
    """Parse one .docx file. Returns a list of action-item dicts."""
    try:
        doc = Document(str(docx_path))
    except Exception:
        return []
    items: list[dict] = []
    stat = docx_path.stat()
    for text in _iter_action_blocks(doc):
        items.append({
            "id": _item_id(docx_path, text),
            "text": text,
            "bucket": bucket_tag,
            "source_meeting": docx_path.stem,
            "source_path": str(docx_path),
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return items


def collect_open_items(config: dict, onedrive_base: Path) -> list[dict]:
    """Scan all configured buckets' current-week folders, return aggregated items.
    Skips rollup files (they're synthesis, not source-of-truth for actions)."""
    plaud_root = onedrive_base / "Plaud Meetings"
    if not plaud_root.exists():
        return []

    week_label = current_iso_week_label()
    all_items: list[dict] = []

    for bucket in (config.get("meeting_routing", {}).get("types") or []):
        folder_name = bucket.get("folder")
        prefix = bucket.get("filename_prefix")
        rollup_prefix = bucket.get("rollup_filename_prefix")
        if not folder_name or not prefix:
            continue
        bucket_folder = plaud_root / folder_name
        bucket_tag = BUCKET_TAGS.get(prefix, prefix[:2].upper())

        if bucket.get("weekly_subfolders"):
            week_folder = find_week_folder(bucket_folder, prefix, week_label)
            scan_folders = [week_folder] if week_folder else []
        else:
            # Flat-folder buckets (Personal in older configs): scan the bucket directly.
            scan_folders = [bucket_folder] if bucket_folder.exists() else []

        for folder in scan_folders:
            for docx in folder.glob("*.docx"):
                # Skip rollup files
                if rollup_prefix and docx.stem.startswith(f"{rollup_prefix}."):
                    continue
                # Skip our own per-meeting files only if they don't match the prefix
                if not docx.stem.startswith(f"{prefix}."):
                    continue
                # Skip Office's temp lock files
                if docx.name.startswith("~$"):
                    continue
                all_items.extend(parse_meeting_doc(docx, bucket_tag))

    # Sort by mtime descending (newest meetings first)
    all_items.sort(key=lambda x: x["mtime"], reverse=True)
    return all_items
