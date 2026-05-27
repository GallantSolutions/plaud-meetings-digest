#!/usr/bin/env python3
"""
Print-renderer for CLIENT-USER-GUIDE.md.

Produces dist/CLIENT-USER-GUIDE.docx — board-grade, ready to print on letter paper
and slip into a Gallant LABS-branded folder for client handoff.

Reuses the pharma-corporate styling helpers established in docx_writer.py:
deep navy ALL CAPS headers, Calibri 11pt body, graphite secondary, locked palette,
zero emoji. The markdown stays the source of truth; this script is the render adapter.

Usage:
    python3 scripts/build_client_guide.py
    python3 scripts/build_client_guide.py --out /custom/path/Guide.docx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.enum.table import WD_ALIGN_VERTICAL
    from docx.oxml.ns import qn, nsmap
    from docx.oxml import OxmlElement
except ImportError:
    sys.stderr.write("ERROR: python-docx not installed. Run: python3 -m pip install python-docx\n")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "dist" / "CLIENT-USER-GUIDE.docx"

# Brand palette — kept in sync with docx_writer.py
GALLANT_DEEP_NAVY = RGBColor(0x1A, 0x2A, 0x44)
GALLANT_GRAPHITE  = RGBColor(0x3D, 0x4A, 0x59)
GALLANT_MUTED     = RGBColor(0x6C, 0x75, 0x83)
GALLANT_WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
GALLANT_DIVIDER_HEX = "CCCCCC"
GALLANT_NAVY_HEX    = "1A2A44"
GALLANT_BAND_HEX    = "F4F5F7"


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------

def _set_run(run, *, bold=False, italic=False, size=11, color=None, font="Calibri") -> None:
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = font
    if color:
        run.font.color.rgb = color


def _shade_paragraph(p, hex_color: str) -> None:
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    pPr.append(shd)


def _shade_cell(cell, hex_color: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _set_cell_border(cell, *, color="CCCCCC", size="4") -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), size)
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), color)
        tcBorders.append(b)
    tcPr.append(tcBorders)


def _paragraph_bottom_border(p, *, color="CCCCCC", size="6") -> None:
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _page_break(doc) -> None:
    p = doc.add_paragraph()
    r = p.add_run()
    r.add_break(WD_BREAK.PAGE)


def _section_header(doc, text: str) -> None:
    """ALL CAPS section header in deep navy with subtle bottom rule."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(20)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text.upper())
    _set_run(r, bold=True, size=13, color=GALLANT_DEEP_NAVY)
    _paragraph_bottom_border(p, color=GALLANT_DIVIDER_HEX, size="6")


def _subsection(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    _set_run(r, bold=True, size=11, color=GALLANT_DEEP_NAVY)


def _body(doc, text: str, *, italic=False) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    _set_run(r, italic=italic, size=11, color=GALLANT_GRAPHITE)


def _body_runs(doc, parts: list[tuple[str, bool]]) -> None:
    """parts = [(text, bold), ...]."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    for text, bold in parts:
        r = p.add_run(text)
        _set_run(r, bold=bold, size=11, color=GALLANT_GRAPHITE)


def _bullet(doc, text_parts: list[tuple[str, bool]]) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(3)
    r0 = p.add_run("•   ")
    _set_run(r0, bold=True, size=11, color=GALLANT_DEEP_NAVY)
    for text, bold in text_parts:
        r = p.add_run(text)
        _set_run(r, bold=bold, size=11, color=GALLANT_GRAPHITE)


def _numbered(doc, n: int, text_parts: list[tuple[str, bool]]) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(3)
    r0 = p.add_run(f"{n}.  ")
    _set_run(r0, bold=True, size=11, color=GALLANT_DEEP_NAVY)
    for text, bold in text_parts:
        r = p.add_run(text)
        _set_run(r, bold=bold, size=11, color=GALLANT_GRAPHITE)


def _quote(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.35)
    p.paragraph_format.right_indent = Inches(0.35)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"“{text}”")
    _set_run(r, italic=True, size=11, color=GALLANT_GRAPHITE)


def _code_block(doc, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(8)
    _shade_paragraph(p, GALLANT_BAND_HEX)
    r = p.add_run(text)
    _set_run(r, size=9, color=GALLANT_GRAPHITE, font="Consolas")


def _table(doc, headers: list[str], rows: list[list[str]], *, col_widths_in: list[float] | None = None) -> None:
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if col_widths_in:
        for i, w in enumerate(col_widths_in):
            for cell in tbl.columns[i].cells:
                cell.width = Inches(w)
    hdr = tbl.rows[0].cells
    for i, h in enumerate(headers):
        cell = hdr[i]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _shade_cell(cell, GALLANT_NAVY_HEX)
        _set_cell_border(cell, color=GALLANT_NAVY_HEX, size="4")
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(h.upper())
        _set_run(r, bold=True, size=10, color=GALLANT_WHITE)
    for ri, row in enumerate(rows):
        rcells = tbl.rows[1 + ri].cells
        for ci, val in enumerate(row):
            cell = rcells[ci]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _set_cell_border(cell, color=GALLANT_DIVIDER_HEX, size="4")
            if ri % 2 == 1:
                _shade_cell(cell, GALLANT_BAND_HEX)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            r = p.add_run(val)
            _set_run(r, size=10, color=GALLANT_GRAPHITE)


def _glossary_term(doc, term: str, definition: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r1 = p.add_run(f"{term}  ")
    _set_run(r1, bold=True, size=11, color=GALLANT_DEEP_NAVY)
    r2 = p.add_run(definition)
    _set_run(r2, size=11, color=GALLANT_GRAPHITE)


def _horizontal_rule(doc, *, color="CCCCCC", size="6") -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    _paragraph_bottom_border(p, color=color, size=size)


# ---------------------------------------------------------------------------
# page-level constructs
# ---------------------------------------------------------------------------

def _configure_page(doc) -> None:
    for section in doc.sections:
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.header_distance = Inches(0.5)
        section.footer_distance = Inches(0.5)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)


def _add_running_header(doc, text: str) -> None:
    section = doc.sections[0]
    section.different_first_page_header_footer = True
    header = section.header
    header.is_linked_to_previous = False
    p = header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(text)
    _set_run(r, italic=True, size=9, color=GALLANT_MUTED)


def _add_page_number_footer(doc, text_left: str) -> None:
    section = doc.sections[0]
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_ALIGN_PARAGRAPH.RIGHT)
    rl = p.add_run(text_left)
    _set_run(rl, italic=True, size=9, color=GALLANT_MUTED)
    rs = p.add_run("\t")
    _set_run(rs, size=9, color=GALLANT_MUTED)
    # Page X of Y via field codes
    for code in ("PAGE", "NUMPAGES"):
        if code == "NUMPAGES":
            sep = p.add_run(" of ")
            _set_run(sep, italic=True, size=9, color=GALLANT_MUTED)
        fldChar_begin = OxmlElement("w:fldChar")
        fldChar_begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = code
        fldChar_end = OxmlElement("w:fldChar")
        fldChar_end.set(qn("w:fldCharType"), "end")
        run = p.add_run()
        _set_run(run, italic=True, size=9, color=GALLANT_MUTED)
        run._r.append(fldChar_begin)
        run._r.append(instr)
        run._r.append(fldChar_end)


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

def _add_cover_page(doc) -> None:
    # Top: brand mark
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(60)
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("GALLANT  ·  LABS.")
    _set_run(r, bold=True, size=11, color=GALLANT_MUTED)

    # Spacer
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(120)

    # Title
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run("Plaud Meetings")
    _set_run(r, bold=True, size=36, color=GALLANT_DEEP_NAVY)

    # Subtitle
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("User Guide")
    _set_run(r, size=22, color=GALLANT_GRAPHITE)

    # Divider
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(24)
    _paragraph_bottom_border(p, color=GALLANT_NAVY_HEX, size="12")

    # Recipient block
    meta = [
        ("Prepared for", "Kingsway Pharma"),
        ("Recipient", "John Smith"),
        ("Prepared by", "Gallant Solutions  ·  LABS."),
        ("Engagement reference", "PMD-KINGSWAY-2026"),
        ("Classification", "Confidential  —  Client Use"),
        ("Edition", "1.1  ·  2026-05-25"),
    ]
    for label, val in meta:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{label.upper()}    ")
        _set_run(r1, bold=True, size=9, color=GALLANT_MUTED)
        r2 = p.add_run(val)
        _set_run(r2, size=11, color=GALLANT_GRAPHITE)

    # Bottom footer
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(180)
    r = p.add_run("hello@gallant.solutions")
    _set_run(r, italic=True, size=10, color=GALLANT_MUTED)

    _page_break(doc)


def _add_foreword(doc) -> None:
    _section_header(doc, "Foreword")

    _body(doc, "John,")
    _body(doc, "This document accompanies the meeting-capture system Gallant has built and deployed for your work at Kingsway Pharma. The system runs quietly in the background on your computer. Twice each weekday it gathers your recordings, transforms them into clean, well-structured Word documents, and files them into OneDrive. Each Friday it produces a one-page weekly rollup that brings the week into focus before the weekend.")
    _body(doc, "Two things matter for it to work well. They take seconds. They are described in detail on the pages that follow, and summarized on the pull-out reference card near the back.")
    _body(doc, "We have engineered the system to take care of itself — it updates automatically each night, alerts our team within an hour if something fails, and reverts itself when a fresh update misbehaves. You should not need to think about it. If something ever looks off, we ask only that you tell us; you do not need to attempt to fix it.")
    _body(doc, "This is a relationship, not a software install. Treat us as the line of escalation any time the system surprises you. Same-day response is the standard you should hold us to.")
    _body(doc, "Welcome aboard.")

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("— The Gallant team")
    _set_run(r, bold=True, size=11, color=GALLANT_DEEP_NAVY)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("hello@gallant.solutions")
    _set_run(r, italic=True, size=10, color=GALLANT_MUTED)

    _page_break(doc)


def _add_contents(doc) -> None:
    _section_header(doc, "Contents")
    items = [
        "Read this first",
        "Your first week",
        "How recordings become documents",
        "Where your meetings appear in OneDrive",
        "What is inside each meeting document",
        "What is inside the Friday weekly rollup",
        "Daily and weekly habits",
        "When something looks off",
        "What not to do",
        "How the system maintains itself",
        "Service and support",
        "Quick reference card  (pull-out)",
        "Glossary",
        "Document control",
    ]
    for n, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{n:>2}.   ")
        _set_run(r1, bold=True, size=11, color=GALLANT_DEEP_NAVY)
        r2 = p.add_run(item)
        _set_run(r2, size=11, color=GALLANT_GRAPHITE)
    _page_break(doc)


def _add_read_first(doc) -> None:
    _section_header(doc, "1.  Read this first")
    _body(doc, "If you read only one page of this guide, read this one.", italic=True)

    _subsection(doc, "Three habits.  That is the complete user-side checklist.")
    _numbered(doc, 1, [
        ("At the start of every recording, say one of four keywords within the first ten seconds: ", False),
        ("Kingsway Pharma", True), (", ", False),
        ("Church", True), (", or ", False), ("Personal", True),
        (".  Then name the people you are meeting with.  Then talk normally.", False),
    ])
    _numbered(doc, 2, [
        ("At end of day, lock your screen with ", False),
        ("Windows key + L", True),
        (".  Do not sign out.  Do not shut down except when you choose to.", False),
    ])
    _numbered(doc, 3, [
        ("Saturday morning, open the Friday rollup and close out finished items.  ", True),
        ("Read the “Open Items from Prior Weeks” table at the top.  For anything that's actually done — even if no meeting captured it (a hallway handoff, an email you sent, a deliverable that arrived on your desk) — change the ", False),
        ("[ ]", True), (" in the ", False), ("Done?", True),
        (" column to ", False), ("[x]", True), (" and save.  Takes 60 seconds.  Next Friday's rollup will exclude those items automatically.", False),
    ])

    _body(doc, "That is it.  Recordings flow into Plaud the way they always have.  Twice each weekday, the system pulls anything new, generates a clean Word document for each meeting, and files it into OneDrive under Plaud Meetings / [matching folder].  Each Friday afternoon you receive a one-page rollup of the week's Kingsway Pharma meetings.")

    _body(doc, "You never open a tool, click a button, or run a command.  The only software you interact with is OneDrive — where the finished documents appear — and Word — where you read and annotate them.")

    _body(doc, "If something looks off, email hello@gallant.solutions.  Do not attempt repairs.  Our team is usually already aware before you are.")

    _page_break(doc)


def _add_first_week(doc) -> None:
    _section_header(doc, "2.  Your first week")
    _body(doc, "A short orientation.  Each step takes under a minute.", italic=True)

    _subsection(doc, "Day 1 — Record a single Kingsway Pharma meeting")
    _body(doc, "Press record on your Plaud as you normally would.  Say aloud:")
    _quote(doc, "Kingsway Pharma meeting with [name], about [topic].")
    _body(doc, "Speak naturally for the rest of the meeting.  Within a few hours, open OneDrive and navigate to Plaud Meetings / Kingsway Pharma.  You will see a week folder named for the current work week (e.g., KPM.May 25-29, 2026 (Week 22)/).  Inside it: a Word document named after the topic and attendees you spoke.  Open it.  Read it.  This confirms the routing works for you.")

    _subsection(doc, "Day 2 — Record a Church or Personal note")
    _body(doc, "Press record.  Say “Personal note, [topic]” or “Church reflection on [topic].”  Verify the file appears in Plaud Meetings / Personal or Plaud Meetings / Church.  You now have direct evidence that the four keywords route to four different folders.")

    _subsection(doc, "Day 3 to Friday — Use the system normally")
    _body(doc, "Record meetings as they happen.  Keep the keyword-first habit.  Lock your screen at end of day rather than signing out.")

    _subsection(doc, "Friday afternoon — Read your first rollup")
    _body(doc, "Open Plaud Meetings / Kingsway Pharma / [this week's folder].  The rollup file begins with KPR. and is named for the work week (e.g., KPR.May 25-29, 2026 (Week 22).docx).  The rollup opens with Open Items from Prior Weeks — items still outstanding from earlier meetings, sorted oldest first.")
    _body(doc, "In the first week there will be no carry-overs (no prior weeks exist yet).  The section will read: “All prior-week items closed.  No carry-overs this week.”  From week two onward, this is the most important section of the rollup; it surfaces commitments that are quietly aging.")
    _body_runs(doc, [
        ("Beginning week two, this is also where you close things out.  ", True),
        ("The carry-over table includes a ", False), ("Done?", True),
        (" column with a [ ] checkbox per row.  Read the table Saturday morning, change [ ] to [x] on anything that's actually finished — whether it was completed in a recorded meeting, by an email you sent, by a colleague who dropped off the deliverable, or anything else — and save the document.  Next Friday's rollup will exclude what you closed.  This is the only piece of bookkeeping the system asks of you, and it takes under a minute.", False),
    ])

    _subsection(doc, "End of week 1 — One brief check-in call")
    _body(doc, "A member of the Gallant team will reach out for a 15-minute call.  Bring any friction, confusion, or “I wish it did this” observations.  Adjustments made in the first week are essentially free; adjustments made in month two require a coordinated update.")

    _page_break(doc)


def _add_pipeline(doc) -> None:
    _section_header(doc, "3.  How recordings become documents")
    _body(doc, "The system operates on a fixed daily schedule.  You do not need to remember the schedule — it is described here so that the rhythm of new documents appearing is predictable rather than mysterious.")

    _table(doc,
        ["When", "What happens"],
        [
            ["11:00 AM each weekday", "Pulls all morning recordings, generates documents, files into OneDrive"],
            ["4:00 PM each weekday", "Pulls all afternoon recordings, generates documents, files into OneDrive"],
            ["4:30 PM each Friday", "Synthesizes the weekly rollup across all meeting types"],
            ["3:00 AM each night", "Checks for system updates; installs silently if available"],
        ],
        col_widths_in=[2.0, 4.5],
    )

    _body(doc, "A recording made at 9:00 AM appears after 11:00 AM.  A recording made at 3:00 PM appears after 4:00 PM.  A recording made over the weekend lands the following Monday at 11:00 AM.")

    _subsection(doc, "The pipeline, in plain terms:")
    _numbered(doc, 1, [("You press record on Plaud and speak.  The first ten seconds determine routing.", False)])
    _numbered(doc, 2, [("Plaud transcribes the recording on your behalf.", False)])
    _numbered(doc, 3, [("At the next scheduled run, our system retrieves the transcript.", False)])
    _numbered(doc, 4, [("It re-reads the transcript carefully and extracts the meaning: a recap, action items, decisions, open questions, and notable quotes.", False)])
    _numbered(doc, 5, [("It writes a Word document with that content and files it into the correct OneDrive folder.", False)])

    _body(doc, "The entire process is supervised by software designed to fail safely.  If any step misbehaves, our team is notified within an hour, the previous working version is restored automatically, and the missed recordings catch up on the following scheduled run.")

    _page_break(doc)


def _add_onedrive(doc) -> None:
    _section_header(doc, "4.  Where your meetings appear in OneDrive")
    _body(doc, "Open OneDrive.  Look for a folder named Plaud Meetings.  Inside:")

    _code_block(doc,
"""OneDrive/
  Plaud Meetings/
    Kingsway Pharma/                          [bucketed by work week]
      KPM.May 25-29, 2026 (Week 22)/
        KPM.Q3 Plans (John Smith).docx
        KPM.Pricing Pushback (Sarah Jones, Mark Lee).docx
        KPM.Compounding Demo (John Smith).docx
        KPR.May 25-29, 2026 (Week 22).docx   [weekly rollup]
      KPM.Jun 1-5, 2026 (Week 23)/
        KPM.Q3 Plans Follow-Up (John Smith).docx
        KPR.Jun 1-5, 2026 (Week 23).docx
    Church/                                   [flat layout]
      CHM.Sermon on Patience.docx
    Personal/                                 [flat layout]
      PM.Dentist Reminder.docx
    Uncategorized/                            [keyword missing]
      UN.Untitled.docx""")

    _subsection(doc, "Filename convention")
    _body(doc, "<prefix>.<topic> (<attendees>).docx")
    _body(doc, "The trailing letter on each prefix identifies the file type, so they remain unambiguous if you happen to keep other files in OneDrive that begin with the same two letters.")

    _table(doc,
        ["Prefix", "Meaning"],
        [
            ["KPM.", "Kingsway Pharma Meeting (single meeting note)"],
            ["KPR.", "Kingsway Pharma Rollup (Friday weekly summary)"],
            ["CHM.", "Church Meeting"],
            ["PM.",  "Personal Meeting"],
            ["UN.",  "Uncategorized (keyword missing — manual triage)"],
        ],
        col_widths_in=[1.0, 5.5],
    )

    _subsection(doc, "How files are organized")
    _bullet(doc, [
        ("Kingsway Pharma meetings", True),
        (" are bucketed by work week (Monday through Friday).  A meeting recorded any time May 25–29, 2026 — including weekend recordings within that ISO week — lands in KPM.May 25-29, 2026 (Week 22)/.  The Friday weekly rollup for that week lives in the same folder.  One folder represents one week's worth of Kingsway Pharma work.", False),
    ])
    _bullet(doc, [
        ("Church and Personal", True),
        (" are flat — files sit directly in the folder with no week subfolders.  Sparse-volume content does not need bucketing.", False),
    ])
    _bullet(doc, [
        ("The topic in the filename", True),
        (" is a three- to six-word summary the system writes from the meeting content.  You do not enter it.", False),
    ])
    _bullet(doc, [
        ("Attendee names", True),
        (" come from the opening line.  Solo recordings produce filenames without parentheses.", False),
    ])

    _page_break(doc)


def _add_meeting_doc(doc) -> None:
    _section_header(doc, "5.  What is inside each meeting document")
    _body(doc, "Each per-meeting document is one to two pages with the following structure:")
    _bullet(doc, [("Title block", True), (" — meeting type, topic, attendees, date, and recording duration", False)])
    _bullet(doc, [("Recap", True), (" — a two- to three-sentence executive summary capturing the essence of the conversation", False)])
    _bullet(doc, [("Action items", True), (" — each with a [ ] checkbox, owner, due date, and priority", False)])
    _bullet(doc, [("Decisions recorded", True), (" — what was decided and why", False)])
    _bullet(doc, [("Open questions", True), (" — anything raised but unresolved", False)])
    _bullet(doc, [("Notable quotes", True), (" — verbatim statements worth preserving", False)])

    _body(doc, "To mark an action item complete, open the document in Word, change [ ] to [x], and save.  The system does not auto-detect completion; your edits are for your own tracking and visible to anyone you share the document with.")


def _add_rollup_doc(doc) -> None:
    _section_header(doc, "6.  What is inside the Friday weekly rollup")
    _body(doc, "The rollup is engineered to be read in roughly seven minutes over a Saturday morning coffee, leaving Monday already prioritized.")
    _body(doc, "The document opens with Open Items from Prior Weeks as a five-column table sorted oldest-first:")

    _table(doc,
        ["Action Item", "Days Open", "Status", "Source Meeting", "Done?"],
        [["(example row)", "21", "CRITICAL", "KPM.Q3 Plans", "[ ]"]],
        col_widths_in=[2.0, 0.8, 1.0, 1.7, 0.7],
    )

    _body(doc, "The Status column uses three text labels:")
    _bullet(doc, [("CRITICAL", True), (" — open 21 or more days", False)])
    _bullet(doc, [("ATTENTION", True), (" — open 14 or more days", False)])
    _bullet(doc, [("OPEN", True), (" — open fewer than 14 days", False)])

    _body_runs(doc, [
        ("The ", False), ("Done?", True),
        (" column carries a [ ] checkbox per row.  This is your closure surface — the one place you tell the system that something is finished.  Spend 60 seconds Saturday morning reviewing the table and flipping [ ] to [x] on anything that's actually complete.  Save the document.  Next Friday's rollup will exclude those items automatically.", False),
    ])
    _body_runs(doc, [
        ("Closure works for anything, recorded or not.  ", True),
        ("If a colleague dropped off a deliverable on Wednesday and no meeting captured the handoff, the system has no way to know — only you do.  Mark [x].  If you sent an email completing an action item, mark [x].  The system doesn't try to guess.  It just listens to your gesture.", False),
    ])

    _body(doc, "This section is intentionally placed at the top.  Stuck commitments across weeks are the highest-leverage information in the document; the layout is designed to make them impossible to skip.")
    _body(doc, "If you have closed everything out, the section reads simply: “All prior-week items closed.  No carry-overs this week.”")

    _subsection(doc, "Subsequent sections, in order:")
    for n, (label, desc) in enumerate([
        ("Next Week's Focus Picks", "three to five high-leverage items with rationale"),
        ("High Priority (This Week)", "items demanding attention in the coming week"),
        ("Action Items by Context", "grouped by category"),
        ("Decisions Recorded", "the week's commitments"),
        ("Open Questions", "what remains unresolved"),
        ("Observations", "recurring patterns the system identified"),
        ("Summary", "one-line totals across the document"),
    ], start=1):
        _numbered(doc, n, [(label, True), (f" — {desc}", False)])

    _page_break(doc)


def _add_habits(doc) -> None:
    _section_header(doc, "7.  Daily and weekly habits")

    _subsection(doc, "The recording habit")
    _body(doc, "The opening ten seconds of every recording determine where the file lands.  Three forms work consistently:")
    _quote(doc, "Kingsway Pharma meeting with John Smith, going over Q3 plans.")
    _quote(doc, "Church reflection — this week's sermon was about patience.")
    _quote(doc, "Personal note, reminder to book the dentist.")

    _body(doc, "These do not work:")
    _quote(doc, "So I wanted to talk about the Q3 numbers...   (no keyword)")
    _quote(doc, "Meeting with John about Kingsway Pharma...    (keyword too late)")

    _body_runs(doc, [
        ("The rule:  ", True),
        ("within the first ten seconds, one of ", False),
        ("Kingsway Pharma", True), (", ", False),
        ("Church", True), (", or ", False), ("Personal", True),
        (" must be spoken.  After that, talk about whatever you want — who you are with, what it is about, what was decided.", False),
    ])

    _body_runs(doc, [
        ("Name your attendees in the opening line.  ", True),
        ("Spoken names appear in the filename, which makes scanning OneDrive much easier later.", False),
    ])
    _quote(doc, "Kingsway Pharma meeting with John Smith and Sarah Jones about Q3 plans  →  file lands as KPM.Q3 Plans (John Smith, Sarah Jones).docx")
    _body(doc, "If you forget to name attendees, the file still gets the topic — KPM.Q3 Plans.docx — and remains usable, just less scannable.")

    _subsection(doc, "The end-of-day habit")
    _body(doc, "The system runs in the background on your computer.  It only works while you are signed in.  If you sign out, the scheduled runs do not fire.")
    _bullet(doc, [("At end of day:", True), (" press Windows key + L to lock the screen.", False)])
    _bullet(doc, [("Closing the laptop lid is fine.", True), ("  The computer sleeps and wakes for scheduled runs.", False)])
    _bullet(doc, [("Do not click “Sign out”", True), (" unless asked.  You can shut down the computer when you want; missed runs catch up the next time you start it.", False)])
    _body(doc, "That is the complete user-side checklist.  Two habits, both passive.")

    _page_break(doc)


def _add_troubleshooting(doc) -> None:
    _section_header(doc, "8.  When something looks off")

    _subsection(doc, "A meeting landed in the “Uncategorized” folder")
    _body(doc, "The keyword was not stated at the start.  Two options:")
    _numbered(doc, 1, [("Re-record if possible.", False)])
    _numbered(doc, 2, [("Manually move the document from Uncategorized/ into the correct folder.", False)])
    _body(doc, "Occasional misses are normal.  If it begins happening regularly, contact support and we will review the keyword set with you.")

    _subsection(doc, "A meeting did not appear at all")
    _body(doc, "Wait until after the next scheduled run (11:00 AM or 4:00 PM that day).  The system catches up on whatever Plaud has.  A recording made at 9:00 AM will appear after 11:00 AM; a recording made at 3:00 PM will appear after 4:00 PM.")
    _body(doc, "If it still has not appeared by the next morning, email hello@gallant.solutions.  Do not attempt to fix it yourself.")

    _subsection(doc, "The Friday rollup is empty")
    _body(doc, "There were no Kingsway Pharma meetings that week.  The rollup is for Kingsway Pharma only; Church and Personal recordings remain in their folders but do not roll up.")

    _subsection(doc, "Something looks wrong or unexpected")
    _body(doc, "Email hello@gallant.solutions with:")
    _bullet(doc, [("What you were doing", False)])
    _bullet(doc, [("What you expected", False)])
    _bullet(doc, [("What you actually saw (a screenshot is helpful but not required)", False)])
    _bullet(doc, [("Approximate time of day", False)])
    _body(doc, "Support is notified automatically when something breaks technically — the team is usually already investigating before you notice.  Even so, please tell us if you see something off.  The combination of automated alerts and your eyes-on report is what keeps the system invisible to you.")

    _page_break(doc)


def _add_donot(doc) -> None:
    _section_header(doc, "9.  What not to do")
    _body(doc, "These will not break the system permanently, but they create avoidable work for both of us:")
    _bullet(doc, [("Do not edit files in your .claude folder.", True), ("  It is hidden by default.  If you find it, leave it.", False)])
    _bullet(doc, [("Do not delete Plaud recordings before they appear in OneDrive.", True), ("  Plaud is the source of truth; OneDrive is the output.  If you delete from Plaud before the system has retrieved the recording, the meeting is lost.", False)])
    _bullet(doc, [("Do not install Plaud or Claude updates yourself.", True), ("  The system handles its own updates automatically.", False)])
    _bullet(doc, [("Do not disconnect your OneDrive account.", True), ("  Meetings stop appearing if OneDrive is signed out.", False)])
    _bullet(doc, [("Do not move the “Plaud Meetings” folder out of OneDrive.", True), ("  Move files within it freely; the parent folder stays where it is.", False)])
    _bullet(doc, [("Do not change the meeting keywords", True), (" without telling us.  If you start saying “KP meeting” instead of “Kingsway Pharma,” nothing routes correctly.  To add a new meeting type — a new project, a new client — contact support and we will configure it.", False)])

    _page_break(doc)


def _add_maintenance(doc) -> None:
    _section_header(doc, "10.  How the system maintains itself")
    _body(doc, "Each night at 3:00 AM the system checks for a new version and installs it silently if one is available.  You will not notice.  A fix published at 6:00 PM today will be in place by tomorrow morning.")
    _body_runs(doc, [
        ("Self-healing.  ", True),
        ("If an update causes the system to fail, the previous working version is automatically restored at the next scheduled run.  Our team is alerted within roughly an hour.  You will see no interruption.", False),
    ])
    _body_runs(doc, [
        ("Required conditions.  ", True),
        ("For automatic updates to work, the computer must be on, signed in (lock screen is fine), and connected to the internet at 3:00 AM.  A typical office computer with the lid closed and on Wi-Fi satisfies all three.", False),
    ])
    _body(doc, "You will never be asked to apply an update manually.  If we ever do need physical access to your machine, we will reach out first and schedule it.")


def _add_service(doc) -> None:
    _section_header(doc, "11.  Service and support")

    _subsection(doc, "Standard channels")
    _table(doc,
        ["Channel", "Use it for", "Response time"],
        [
            ["hello@gallant.solutions", "Anything off, anything unclear, anything you want changed", "Same business day"],
            ["Scheduled check-in call", "End-of-week-1, then quarterly", "30 minutes, pre-booked"],
        ],
        col_widths_in=[2.0, 3.0, 1.5],
    )

    _subsection(doc, "What our team monitors automatically")
    _body(doc, "Behind the scenes, the system reports to a monitoring service every time a scheduled run completes successfully.  If a run fails, or fails to run at all, our team is alerted within an hour.  In the great majority of cases the system has already restored itself by the time we look.  You typically receive no notification because there is nothing to notice; we keep the rolling log so that we have evidence in the rare case that something needs escalation.")

    _subsection(doc, "Escalation path")
    _numbered(doc, 1, [("First response — email.  ", True), ("hello@gallant.solutions.  Same business day.  Most issues resolve here.", False)])
    _numbered(doc, 2, [("Second response — phone, by request.  ", True), ("When email exchange is slower than the situation warrants, ask for a call.", False)])
    _numbered(doc, 3, [("On-site, if ever needed.  ", True), ("We have engineered the system so this is extremely unlikely.  If your situation truly requires it, we will travel.", False)])

    _subsection(doc, "Hours")
    _body(doc, "Standard support is Monday through Friday, 9 AM to 6 PM Eastern.  Outside those hours, our system continues to monitor itself; human response resumes at the start of the next business day.  If a recording is missed because the system was offline overnight, the next morning's 11:00 AM run will catch it up automatically.")

    _page_break(doc)


def _add_reference_card(doc) -> None:
    _section_header(doc, "12.  Quick reference card")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    r = p.add_run("Tear out and keep near your computer.")
    _set_run(r, italic=True, size=10, color=GALLANT_MUTED)

    # Card outline as a single-cell shaded table to create a framed "card" feel
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    _set_cell_border(cell, color=GALLANT_NAVY_HEX, size="12")

    def _card_line(label: str, value: str) -> None:
        p = cell.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r1 = p.add_run(f"{label}    ")
        _set_run(r1, bold=True, size=10, color=GALLANT_DEEP_NAVY)
        r2 = p.add_run(value)
        _set_run(r2, size=11, color=GALLANT_GRAPHITE)

    # Remove the default empty paragraph in the cell
    first_p = cell.paragraphs[0]
    first_p._element.getparent().remove(first_p._element)

    _card_line("RECORD", "Within the first ten seconds, say Kingsway Pharma, Committee, Church, or Personal.  Then name the people present.  Then talk normally.")
    _card_line("END OF DAY", "Lock the screen with Windows key + L.  Do not sign out.")
    _card_line("FIND YOUR MEETINGS", "OneDrive  →  Plaud Meetings  →  folder matching your keyword.  Kingsway Pharma meetings are bucketed by work week, e.g., KPM.May 25-29, 2026 (Week 22)/.")
    _card_line("READ THE FRIDAY ROLLUP", "Same week folder.  The file begins with KPR. rather than KPM.  Best read Saturday morning.")
    _card_line("CLOSE OUT FINISHED ITEMS", "In the rollup's Open Items table, change [ ] to [x] in the Done? column for anything finished — recorded, hallway-handoff, your own work, anything.  Save.  Next Friday's rollup will exclude it.")
    _card_line("MARK A PER-MEETING ACTION COMPLETE", "Open the meeting document.  Change [ ] to [x] next to the action.  Save.  (Personal tracking only — for system closure use the rollup Done? column.)")
    _card_line("FILENAME CHEAT SHEET", "KPM. Kingsway Pharma Meeting  ·  KPR. Kingsway Pharma Rollup  ·  CHM. Church  ·  PM. Personal  ·  UN. Uncategorized.")

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("THREE VALID OPENING LINES")
    _set_run(r, bold=True, size=10, color=GALLANT_DEEP_NAVY)

    for line in [
        "Kingsway Pharma meeting with [name], regarding [topic]...",
        "Church reflection on [topic]...",
        "Personal note, [topic]...",
    ]:
        p = cell.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"•   “{line}”")
        _set_run(r, italic=True, size=10, color=GALLANT_GRAPHITE)

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("THREE THINGS NOT TO DO")
    _set_run(r, bold=True, size=10, color=GALLANT_DEEP_NAVY)
    for line in [
        "Do not delete Plaud recordings until they have appeared in OneDrive.",
        "Do not sign out at end of day — lock the screen instead.",
        "Do not edit files in folders you do not recognize.",
    ]:
        p = cell.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"•   {line}")
        _set_run(r, size=10, color=GALLANT_GRAPHITE)

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    r1 = p.add_run("SOMETHING OFF?    ")
    _set_run(r1, bold=True, size=10, color=GALLANT_DEEP_NAVY)
    r2 = p.add_run("Email hello@gallant.solutions.  Same business day.  Do not attempt to fix.")
    _set_run(r2, size=10, color=GALLANT_GRAPHITE)

    _page_break(doc)


def _add_glossary(doc) -> None:
    _section_header(doc, "13.  Glossary")
    terms = [
        ("Action item.", "A commitment captured during a meeting that requires follow-up.  Each action item carries an owner, due date, and priority.  Marked complete by changing [ ] to [x] in the document."),
        ("Carry-over.", "An open action item from a prior week that has not yet been marked complete.  Carry-overs appear at the top of each Friday rollup, sorted oldest-first, with a status label of CRITICAL, ATTENTION, or OPEN."),
        ("Done? column.", "The fifth column in the carry-over table.  A [ ] checkbox per row.  You change [ ] to [x] to tell the system that the item is finished.  Closures are read by next Friday's rollup and applied automatically.  This is the system's single closure surface — used for items that completed in any context, recorded or not."),
        ("Critical / Attention / Open.", "Aging labels applied to carry-overs in the weekly rollup.  CRITICAL means an item has been open 21 or more days; ATTENTION means 14 or more days; OPEN means fewer than 14 days."),
        ("ISO week.", "A standardized calendar week, Monday through Sunday, used throughout the system.  Week numbers reset each year.  Week 22 of 2026 runs Monday May 25 through Sunday May 31."),
        ("Keyword.", "The routing word spoken in the first ten seconds of a recording.  The four configured keywords are Kingsway Pharma, Committee, Church, and Personal."),
        ("KPM / KPR / CHM / PM / UN.", "Filename prefixes that identify the file type at a glance.  KPM = Kingsway Pharma Meeting.  KPR = Kingsway Pharma Rollup.  CHM = Church Meeting.  PM = Personal Meeting.  UN = Uncategorized."),
        ("Lock screen.", "The screen that appears when you press Windows key + L.  The computer remains signed in and continues running scheduled tasks; the screen is simply protected from view."),
        ("OneDrive.", "The Microsoft cloud storage service where all generated documents are filed.  The system writes to a folder called Plaud Meetings at the root of your OneDrive."),
        ("Plaud.", "The recording device.  The source of truth for raw audio.  Recordings are transcribed by Plaud's service and retrieved by our system at the next scheduled run."),
        ("Rollup.", "The Friday weekly summary document.  One per Kingsway Pharma work week, filed into the same week folder as the meetings it summarizes."),
        ("Scheduled run.", "A point in time when the system retrieves new recordings, generates documents, and files them into OneDrive.  The four scheduled runs each weekday are 11:00 AM, 4:00 PM, 4:30 PM (Friday rollup only), and 3:00 AM (system update check)."),
        ("Self-healing.", "The system's ability to automatically restore the previous working version when a fresh update causes a failure.  Performed without human intervention; an alert is sent to the Gallant team within roughly an hour."),
        ("Work week.", "Monday through Friday.  Used for bucketing Kingsway Pharma meetings into week folders.  Recordings made on Saturday or Sunday land in the following Monday's batch and are filed into the work week they belong to."),
    ]
    for term, defn in terms:
        _glossary_term(doc, term, defn)

    _page_break(doc)


def _add_document_control(doc) -> None:
    _section_header(doc, "14.  Document control")
    for label, val in [
        ("Document title",        "Plaud Meetings — User Guide"),
        ("Document ID",           "PMD-KINGSWAY-2026-CG-01-r1"),
        ("Edition",               "1.1"),
        ("Issued",                "2026-05-25"),
        ("Classification",        "Confidential — Client Use"),
        ("Prepared for",          "Kingsway Pharma  ·  John Smith"),
        ("Prepared by",           "Gallant Solutions  ·  LABS."),
        ("Engagement reference",  "PMD-KINGSWAY-2026"),
        ("System version at issue", "plaud-meetings-digest v2.2.5"),
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(f"{label}.    ")
        _set_run(r1, bold=True, size=10, color=GALLANT_DEEP_NAVY)
        r2 = p.add_run(val)
        _set_run(r2, size=11, color=GALLANT_GRAPHITE)

    _subsection(doc, "Revision history")
    _table(doc,
        ["Edition", "Date", "Author", "Notes"],
        [
            ["1.0", "2026-05-24", "Gallant Solutions", "Initial client edition.  Print-ready board-grade layout."],
            ["1.1", "2026-05-25", "Gallant Solutions", "Added v2.2.5 closure mechanism: Done? column on the carry-over table, Saturday closure ritual, third habit."],
        ],
        col_widths_in=[0.7, 1.0, 1.6, 3.2],
    )

    _subsection(doc, "Contact for corrections")
    _body(doc, "Notify hello@gallant.solutions of any error in this document.  Corrections appear in the next revision and are re-issued at no cost.")

    _horizontal_rule(doc)
    _body(doc, "This document is the property of the recipient.  Reproduction for internal use is permitted.  External distribution requires written consent from Gallant Solutions.", italic=True)
    _body(doc, "Gallant Solutions  ·  hello@gallant.solutions", italic=True)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build(out_path: Path) -> Path:
    doc = Document()
    _configure_page(doc)
    _add_running_header(doc, "Plaud Meetings — User Guide  ·  Confidential — Client Use")
    _add_page_number_footer(doc, "PMD-KINGSWAY-2026-CG-01-r1  ·  Edition 1.1  ·  2026-05-25")

    _add_cover_page(doc)
    _add_foreword(doc)
    _add_contents(doc)
    _add_read_first(doc)
    _add_first_week(doc)
    _add_pipeline(doc)
    _add_onedrive(doc)
    _add_meeting_doc(doc)
    _add_rollup_doc(doc)
    _add_habits(doc)
    _add_troubleshooting(doc)
    _add_donot(doc)
    _add_maintenance(doc)
    _add_service(doc)
    _add_reference_card(doc)
    _add_glossary(doc)
    _add_document_control(doc)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Render CLIENT-USER-GUIDE.md to print-ready .docx")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output .docx path (default: dist/CLIENT-USER-GUIDE.docx)")
    args = ap.parse_args()
    out = build(args.out)
    print(f"OK  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
