#!/usr/bin/env python3
"""
HTML renderer for CLIENT-USER-GUIDE.md — built for high-fidelity upload to
Google Drive where it converts to a NATIVE Google Doc on import (much cleaner
than the .docx → Google Docs path, which mangles formatting).

Produces dist/CLIENT-USER-GUIDE.html — self-contained, no external CSS/fonts,
inline styles only so Google Docs preserves them on conversion.

Sections + structure mirror scripts/build_client_guide.py exactly. The markdown
at CLIENT-USER-GUIDE.md is the source of truth; both renderers (.docx + HTML)
target the same content surface.

Usage:
    python3 scripts/build_client_guide_html.py
    python3 scripts/build_client_guide_html.py --out /custom/path/Guide.html
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "dist" / "CLIENT-USER-GUIDE.html"

# Brand palette — synced with docx_writer.py and rollup_docx_writer.py
NAVY   = "#1A2A44"
GRAPH  = "#3D4A59"
MUTED  = "#6C7583"
DIVID  = "#CCCCCC"
BAND   = "#F4F5F7"
WHITE  = "#FFFFFF"


# ---------------------------------------------------------------------------
# Style block (inline only — Google Docs preserves inline styles best)
# ---------------------------------------------------------------------------

STYLE_BLOCK = f"""
<style>
  body {{
    font-family: Calibri, 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    color: {GRAPH};
    line-height: 1.45;
    max-width: 7.5in;
    margin: 0 auto;
    padding: 0.5in;
  }}
  h1 {{
    font-size: 24pt;
    color: {NAVY};
    font-weight: bold;
    margin: 0;
  }}
  h2 {{
    font-size: 14pt;
    color: {NAVY};
    font-weight: bold;
    text-transform: uppercase;
    border-bottom: 1px solid {DIVID};
    padding-bottom: 4pt;
    margin-top: 24pt;
    margin-bottom: 10pt;
    page-break-after: avoid;
  }}
  h3 {{
    font-size: 12pt;
    color: {NAVY};
    font-weight: bold;
    margin-top: 14pt;
    margin-bottom: 4pt;
    page-break-after: avoid;
  }}
  p {{
    margin: 0 0 8pt 0;
  }}
  ul, ol {{
    margin: 0 0 10pt 0;
    padding-left: 24pt;
  }}
  li {{
    margin-bottom: 4pt;
  }}
  strong {{
    color: {NAVY};
  }}
  em {{
    color: {MUTED};
  }}
  blockquote {{
    margin: 6pt 0 6pt 18pt;
    color: {GRAPH};
    font-style: italic;
    border-left: 2px solid {DIVID};
    padding-left: 12pt;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 6pt 0 14pt 0;
    font-size: 10pt;
  }}
  th {{
    background-color: {NAVY};
    color: {WHITE};
    text-align: left;
    padding: 6pt 8pt;
    font-weight: bold;
    text-transform: uppercase;
    font-size: 9pt;
  }}
  td {{
    padding: 5pt 8pt;
    border: 1px solid {DIVID};
    vertical-align: top;
    color: {GRAPH};
  }}
  tr:nth-child(even) td {{
    background-color: {BAND};
  }}
  pre, code {{
    font-family: Consolas, 'Courier New', monospace;
    font-size: 9pt;
    color: {GRAPH};
  }}
  pre {{
    background-color: {BAND};
    padding: 10pt;
    border-radius: 2pt;
    overflow-x: auto;
    margin: 4pt 0 12pt 0;
  }}
  .cover {{
    page-break-after: always;
    padding: 1.5in 0;
  }}
  .cover .mark {{
    font-size: 11pt;
    font-weight: bold;
    color: {MUTED};
    letter-spacing: 0.05em;
    margin-bottom: 2in;
  }}
  .cover .title {{
    font-size: 36pt;
    font-weight: bold;
    color: {NAVY};
    line-height: 1.1;
    margin-bottom: 4pt;
  }}
  .cover .subtitle {{
    font-size: 22pt;
    color: {GRAPH};
    margin-bottom: 24pt;
  }}
  .cover .divider {{
    border: none;
    border-top: 3px solid {NAVY};
    margin: 0 0 24pt 0;
  }}
  .cover .meta {{
    font-size: 11pt;
    color: {GRAPH};
    margin-bottom: 4pt;
  }}
  .cover .meta .label {{
    color: {MUTED};
    text-transform: uppercase;
    font-size: 9pt;
    font-weight: bold;
    display: inline-block;
    min-width: 180pt;
  }}
  .cover .contact {{
    margin-top: 1.5in;
    font-size: 10pt;
    color: {MUTED};
    font-style: italic;
  }}
  .pagebreak {{
    page-break-after: always;
    height: 0;
    overflow: hidden;
  }}
  .card {{
    border: 3px solid {NAVY};
    padding: 18pt 22pt;
    margin: 12pt 0 14pt 0;
    page-break-inside: avoid;
  }}
  .card .row {{
    margin-bottom: 8pt;
  }}
  .card .label {{
    font-weight: bold;
    color: {NAVY};
    font-size: 10pt;
    text-transform: uppercase;
    display: inline-block;
    min-width: 220pt;
    vertical-align: top;
  }}
  .card .value {{
    color: {GRAPH};
    font-size: 11pt;
    display: inline;
  }}
  .card .heading {{
    font-weight: bold;
    color: {NAVY};
    font-size: 10pt;
    text-transform: uppercase;
    margin-top: 12pt;
    margin-bottom: 4pt;
  }}
  .card ul {{
    margin: 0 0 6pt 0;
  }}
  .doc-control p {{
    margin: 0 0 3pt 0;
  }}
  .doc-control .label {{
    font-weight: bold;
    color: {NAVY};
    font-size: 10pt;
    display: inline-block;
    min-width: 180pt;
  }}
  .closing {{
    font-style: italic;
    color: {MUTED};
    font-size: 10pt;
    margin-top: 24pt;
  }}
  .glossary-term {{
    margin: 0 0 8pt 0;
  }}
  .glossary-term .term {{
    font-weight: bold;
    color: {NAVY};
  }}
  .center {{
    text-align: center;
  }}
  .tear-out {{
    text-align: center;
    font-style: italic;
    color: {MUTED};
    font-size: 10pt;
    margin-bottom: 8pt;
  }}
</style>
"""


# ---------------------------------------------------------------------------
# Section authors (mirror build_client_guide.py)
# ---------------------------------------------------------------------------

def cover() -> str:
    return f"""
<div class="cover">
  <div class="mark">GALLANT  ·  LABS.</div>
  <div class="title">Plaud Meetings</div>
  <div class="subtitle">User Guide</div>
  <hr class="divider"/>
  <p class="meta"><span class="label">Prepared for</span>Kingsway Pharma</p>
  <p class="meta"><span class="label">Recipient</span>John Smith</p>
  <p class="meta"><span class="label">Prepared by</span>Gallant Solutions  ·  LABS.</p>
  <p class="meta"><span class="label">Engagement reference</span>PMD-KINGSWAY-2026</p>
  <p class="meta"><span class="label">Classification</span>Confidential  —  Client Use</p>
  <p class="meta"><span class="label">Edition</span>1.1  ·  2026-05-25</p>
  <p class="contact">hello@gallant.solutions</p>
</div>
"""


def foreword() -> str:
    return """
<h2>Foreword</h2>
<p>John,</p>
<p>This document accompanies the meeting-capture system Gallant has built and deployed for your work at Kingsway Pharma. The system runs quietly in the background on your computer. Twice each weekday it gathers your recordings, transforms them into clean, well-structured Word documents, and files them into OneDrive. Each Friday it produces a one-page weekly rollup that brings the week into focus before the weekend.</p>
<p>Three things matter for it to work well. They take seconds. They are described in detail on the pages that follow, and summarized on the pull-out reference card near the back.</p>
<p>We have engineered the system to take care of itself — it updates automatically each night, alerts our team within an hour if something fails, and reverts itself when a fresh update misbehaves. You should not need to think about it. If something ever looks off, we ask only that you tell us; you do not need to attempt to fix it.</p>
<p>This is a relationship, not a software install. Treat us as the line of escalation any time the system surprises you. Same-day response is the standard you should hold us to.</p>
<p>Welcome aboard.</p>
<p><strong>— The Gallant team</strong><br/><em>hello@gallant.solutions</em></p>
<div class="pagebreak"></div>
"""


def contents() -> str:
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
        "Quick reference card (pull-out)",
        "Glossary",
        "Document control",
    ]
    lis = "\n".join(f"  <li>{html.escape(it)}</li>" for it in items)
    return f"""
<h2>Contents</h2>
<ol>
{lis}
</ol>
<div class="pagebreak"></div>
"""


def read_first() -> str:
    return """
<h2>1. Read this first</h2>
<p><em>If you read only one page of this guide, read this one.</em></p>
<h3>Three habits. That is the complete user-side checklist.</h3>
<ol>
  <li><strong>At the start of every recording, say one of four keywords within the first ten seconds:</strong> <strong>Kingsway Pharma</strong>, <strong>Committee</strong>, <strong>Church</strong>, or <strong>Personal</strong>. Then name the people you are meeting with. Then talk normally.</li>
  <li><strong>At end of day, lock your screen</strong> with <strong>Windows key + L</strong>. Do not sign out. Do not shut down except when you choose to.</li>
  <li><strong>Saturday morning, open the Friday rollup and close out finished items.</strong> Read the &ldquo;Open Items from Prior Weeks&rdquo; table at the top. For anything that&rsquo;s actually done &mdash; even if no meeting captured it (a hallway handoff, an email you sent, a deliverable that arrived on your desk) &mdash; change the <strong>[ ]</strong> in the <strong>Done?</strong> column to <strong>[x]</strong> and save. Takes 60 seconds. Next Friday&rsquo;s rollup will exclude those items automatically.</li>
</ol>
<p>That is it. Recordings flow into Plaud the way they always have. Twice each weekday, the system pulls anything new, generates a clean Word document for each meeting, and files it into OneDrive under Plaud Meetings / [matching folder]. Each Friday afternoon you receive a one-page rollup of the week&rsquo;s Kingsway Pharma meetings.</p>
<p>You never open a tool, click a button, or run a command. The only software you interact with is OneDrive &mdash; where the finished documents appear &mdash; and Word &mdash; where you read and annotate them.</p>
<p>If something looks off, email <strong>hello@gallant.solutions</strong>. Do not attempt repairs. Our team is usually already aware before you are.</p>
<div class="pagebreak"></div>
"""


def first_week() -> str:
    return """
<h2>2. Your first week</h2>
<p><em>A short orientation. Each step takes under a minute.</em></p>
<h3>Day 1 &mdash; Record a single Kingsway Pharma meeting</h3>
<p>Press record on your Plaud as you normally would. Say aloud:</p>
<blockquote>Kingsway Pharma meeting with [name], about [topic].</blockquote>
<p>Speak naturally for the rest of the meeting. Within a few hours, open OneDrive and navigate to <strong>Plaud Meetings / Kingsway Pharma</strong>. You will see a week folder named for the current work week (e.g., <code>KPM.May 25-29, 2026 (Week 22)/</code>). Inside it: a Word document named after the topic and attendees you spoke. Open it. Read it. This confirms the routing works for you.</p>
<h3>Day 2 &mdash; Record a Church or Personal note</h3>
<p>Press record. Say &ldquo;Personal note, [topic]&rdquo; or &ldquo;Church reflection on [topic].&rdquo; Verify the file appears in <strong>Plaud Meetings / Personal</strong> or <strong>Plaud Meetings / Church</strong>. You now have direct evidence that the four keywords route to four different folders.</p>
<h3>Day 3 to Friday &mdash; Use the system normally</h3>
<p>Record meetings as they happen. Keep the keyword-first habit. Lock your screen at end of day rather than signing out.</p>
<h3>Friday afternoon &mdash; Read your first rollup</h3>
<p>Open <strong>Plaud Meetings / Kingsway Pharma / [this week&rsquo;s folder]</strong>. The rollup file begins with <code>KPR.</code> and is named for the work week (e.g., <code>KPR.May 25-29, 2026 (Week 22).docx</code>). The rollup opens with <strong>Open Items from Prior Weeks</strong> &mdash; items still outstanding from earlier meetings, sorted oldest first.</p>
<p>In the first week there will be no carry-overs (no prior weeks exist yet). The section will read: <em>&ldquo;All prior-week items closed. No carry-overs this week.&rdquo;</em> From week two onward, this is the most important section of the rollup; it surfaces commitments that are quietly aging.</p>
<p><strong>Beginning week two, this is also where you close things out.</strong> The carry-over table includes a <strong>Done?</strong> column with a <strong>[ ]</strong> checkbox per row. Read the table Saturday morning, change <strong>[ ]</strong> to <strong>[x]</strong> on anything that&rsquo;s actually finished &mdash; whether it was completed in a recorded meeting, by an email you sent, by a colleague who dropped off the deliverable, or anything else &mdash; and save the document. Next Friday&rsquo;s rollup will exclude what you closed. This is the only piece of bookkeeping the system asks of you, and it takes under a minute.</p>
<h3>End of week 1 &mdash; One brief check-in call</h3>
<p>A member of the Gallant team will reach out for a 15-minute call. Bring any friction, confusion, or &ldquo;I wish it did this&rdquo; observations. Adjustments made in the first week are essentially free; adjustments made in month two require a coordinated update.</p>
<div class="pagebreak"></div>
"""


def pipeline() -> str:
    return """
<h2>3. How recordings become documents</h2>
<p>The system operates on a fixed daily schedule. You do not need to remember the schedule &mdash; it is described here so that the rhythm of new documents appearing is predictable rather than mysterious.</p>
<table>
  <thead>
    <tr><th>When</th><th>What happens</th></tr>
  </thead>
  <tbody>
    <tr><td>11:00 AM each weekday</td><td>Pulls all morning recordings, generates documents, files into OneDrive</td></tr>
    <tr><td>4:00 PM each weekday</td><td>Pulls all afternoon recordings, generates documents, files into OneDrive</td></tr>
    <tr><td>4:30 PM each Friday</td><td>Synthesizes the weekly rollup across all meeting types</td></tr>
    <tr><td>3:00 AM each night</td><td>Checks for system updates; installs silently if available</td></tr>
  </tbody>
</table>
<p>A recording made at 9:00 AM appears after 11:00 AM. A recording made at 3:00 PM appears after 4:00 PM. A recording made over the weekend lands the following Monday at 11:00 AM.</p>
<h3>The pipeline, in plain terms:</h3>
<ol>
  <li>You press record on Plaud and speak. The first ten seconds determine routing.</li>
  <li>Plaud transcribes the recording on your behalf.</li>
  <li>At the next scheduled run, our system retrieves the transcript.</li>
  <li>It re-reads the transcript carefully and extracts the meaning: a recap, action items, decisions, open questions, and notable quotes.</li>
  <li>It writes a Word document with that content and files it into the correct OneDrive folder.</li>
</ol>
<p>The entire process is supervised by software designed to fail safely. If any step misbehaves, our team is notified within an hour, the previous working version is restored automatically, and the missed recordings catch up on the following scheduled run.</p>
<div class="pagebreak"></div>
"""


def onedrive() -> str:
    return """
<h2>4. Where your meetings appear in OneDrive</h2>
<p>Open OneDrive. Look for a folder named <strong>Plaud Meetings</strong>. Inside:</p>
<pre>OneDrive/
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
      UN.Untitled.docx</pre>
<h3>Filename convention</h3>
<p><code>&lt;prefix&gt;.&lt;topic&gt; (&lt;attendees&gt;).docx</code></p>
<p>The trailing letter on each prefix identifies the file type, so they remain unambiguous if you happen to keep other files in OneDrive that begin with the same two letters.</p>
<table>
  <thead>
    <tr><th>Prefix</th><th>Meaning</th></tr>
  </thead>
  <tbody>
    <tr><td><code>KPM.</code></td><td>Kingsway Pharma <strong>Meeting</strong> (single meeting note)</td></tr>
    <tr><td><code>KPR.</code></td><td>Kingsway Pharma <strong>Rollup</strong> (Friday weekly summary)</td></tr>
    <tr><td><code>CHM.</code></td><td>Church Meeting</td></tr>
    <tr><td><code>PM.</code></td><td>Personal Meeting</td></tr>
    <tr><td><code>UN.</code></td><td>Uncategorized (keyword missing — manual triage)</td></tr>
  </tbody>
</table>
<h3>How files are organized</h3>
<ul>
  <li><strong>Kingsway Pharma meetings</strong> are bucketed by work week (Monday through Friday). A meeting recorded any time May 25&ndash;29, 2026 &mdash; including weekend recordings within that ISO week &mdash; lands in <code>KPM.May 25-29, 2026 (Week 22)/</code>. The Friday weekly rollup for that week lives in the same folder. One folder represents one week&rsquo;s worth of Kingsway Pharma work.</li>
  <li><strong>Church and Personal</strong> are flat &mdash; files sit directly in the folder with no week subfolders. Sparse-volume content does not need bucketing.</li>
  <li><strong>The topic in the filename</strong> is a three- to six-word summary the system writes from the meeting content. You do not enter it.</li>
  <li><strong>Attendee names</strong> come from the opening line. Solo recordings produce filenames without parentheses.</li>
</ul>
<div class="pagebreak"></div>
"""


def meeting_doc() -> str:
    return """
<h2>5. What is inside each meeting document</h2>
<p>Each per-meeting document is one to two pages with the following structure:</p>
<ul>
  <li><strong>Title block</strong> &mdash; meeting type, topic, attendees, date, and recording duration</li>
  <li><strong>Recap</strong> &mdash; a two- to three-sentence executive summary capturing the essence of the conversation</li>
  <li><strong>Action items</strong> &mdash; each with a <code>[ ]</code> checkbox, owner, due date, and priority</li>
  <li><strong>Decisions recorded</strong> &mdash; what was decided and why</li>
  <li><strong>Open questions</strong> &mdash; anything raised but unresolved</li>
  <li><strong>Notable quotes</strong> &mdash; verbatim statements worth preserving</li>
</ul>
<p>To mark an action item complete, open the document in Word, change <code>[ ]</code> to <code>[x]</code>, and save. The system does not auto-detect completion; your edits are for your own tracking and visible to anyone you share the document with.</p>
"""


def rollup_doc() -> str:
    return """
<h2>6. What is inside the Friday weekly rollup</h2>
<p>The rollup is engineered to be read in roughly seven minutes over a Saturday morning coffee, leaving Monday already prioritized.</p>
<p>The document opens with <strong>Open Items from Prior Weeks</strong> as a five-column table sorted oldest-first:</p>
<table>
  <thead>
    <tr><th>Action Item</th><th>Days Open</th><th>Status</th><th>Source Meeting</th><th>Done?</th></tr>
  </thead>
  <tbody>
    <tr><td>(example row)</td><td>21</td><td>CRITICAL</td><td>KPM.Q3 Plans</td><td>[ ]</td></tr>
  </tbody>
</table>
<p>The Status column uses three text labels:</p>
<ul>
  <li><strong>CRITICAL</strong> &mdash; open 21 or more days</li>
  <li><strong>ATTENTION</strong> &mdash; open 14 or more days</li>
  <li><strong>OPEN</strong> &mdash; open fewer than 14 days</li>
</ul>
<p>The <strong>Done?</strong> column carries a <code>[ ]</code> checkbox per row. This is your closure surface &mdash; the one place you tell the system that something is finished. Spend 60 seconds Saturday morning reviewing the table and flipping <code>[ ]</code> to <code>[x]</code> on anything that&rsquo;s actually complete. Save the document. Next Friday&rsquo;s rollup will exclude those items automatically.</p>
<p><strong>Closure works for anything, recorded or not.</strong> If a colleague dropped off a deliverable on Wednesday and no meeting captured the handoff, the system has no way to know &mdash; only you do. Mark <code>[x]</code>. If you sent an email completing an action item, mark <code>[x]</code>. The system doesn&rsquo;t try to guess. It just listens to your gesture.</p>
<p>This section is intentionally placed at the top. Stuck commitments across weeks are the highest-leverage information in the document; the layout is designed to make them impossible to skip.</p>
<p>If you have closed everything out, the section reads simply: <em>&ldquo;All prior-week items closed. No carry-overs this week.&rdquo;</em></p>
<h3>Subsequent sections, in order:</h3>
<ol>
  <li><strong>Next Week&rsquo;s Focus Picks</strong> &mdash; three to five high-leverage items with rationale</li>
  <li><strong>High Priority (This Week)</strong> &mdash; items demanding attention in the coming week</li>
  <li><strong>Action Items by Context</strong> &mdash; grouped by category</li>
  <li><strong>Decisions Recorded</strong> &mdash; the week&rsquo;s commitments</li>
  <li><strong>Open Questions</strong> &mdash; what remains unresolved</li>
  <li><strong>Observations</strong> &mdash; recurring patterns the system identified</li>
  <li><strong>Summary</strong> &mdash; one-line totals across the document</li>
</ol>
<div class="pagebreak"></div>
"""


def habits() -> str:
    return """
<h2>7. Daily and weekly habits</h2>
<h3>The recording habit</h3>
<p>The opening ten seconds of every recording determine where the file lands. Three forms work consistently:</p>
<blockquote>Kingsway Pharma meeting with John Smith, going over Q3 plans.</blockquote>
<blockquote>Church reflection &mdash; this week&rsquo;s sermon was about patience.</blockquote>
<blockquote>Personal note, reminder to book the dentist.</blockquote>
<p>These do <strong>not</strong> work:</p>
<blockquote>So I wanted to talk about the Q3 numbers...  <em>(no keyword)</em></blockquote>
<blockquote>Meeting with John about Kingsway Pharma...   <em>(keyword too late)</em></blockquote>
<p><strong>The rule:</strong> within the first ten seconds, one of <strong>Kingsway Pharma</strong>, <strong>Committee</strong>, <strong>Church</strong>, or <strong>Personal</strong> must be spoken. After that, talk about whatever you want &mdash; who you are with, what it is about, what was decided.</p>
<p><strong>Name your attendees in the opening line.</strong> Spoken names appear in the filename, which makes scanning OneDrive much easier later.</p>
<blockquote>Kingsway Pharma meeting with John Smith and Sarah Jones about Q3 plans  &rarr;  file lands as <code>KPM.Q3 Plans (John Smith, Sarah Jones).docx</code></blockquote>
<p>If you forget to name attendees, the file still gets the topic &mdash; <code>KPM.Q3 Plans.docx</code> &mdash; and remains usable, just less scannable.</p>
<h3>The end-of-day habit</h3>
<p>The system runs in the background on your computer. It only works while you are signed in. If you sign out, the scheduled runs do not fire.</p>
<ul>
  <li><strong>At end of day:</strong> press <strong>Windows key + L</strong> to lock the screen.</li>
  <li><strong>Closing the laptop lid is fine.</strong> The computer sleeps and wakes for scheduled runs.</li>
  <li><strong>Do not click &ldquo;Sign out&rdquo;</strong> unless asked. You can shut down the computer when you want; missed runs catch up the next time you start it.</li>
</ul>
<p>That is the complete user-side checklist. Two habits, both passive.</p>
<div class="pagebreak"></div>
"""


def troubleshooting() -> str:
    return """
<h2>8. When something looks off</h2>
<h3>A meeting landed in the &ldquo;Uncategorized&rdquo; folder</h3>
<p>The keyword was not stated at the start. Two options:</p>
<ol>
  <li>Re-record if possible.</li>
  <li>Manually move the document from <code>Uncategorized/</code> into the correct folder.</li>
</ol>
<p>Occasional misses are normal. If it begins happening regularly, contact support and we will review the keyword set with you.</p>
<h3>A meeting did not appear at all</h3>
<p>Wait until after the next scheduled run (11:00 AM or 4:00 PM that day). The system catches up on whatever Plaud has. A recording made at 9:00 AM will appear after 11:00 AM; a recording made at 3:00 PM will appear after 4:00 PM.</p>
<p>If it still has not appeared by the next morning, email <strong>hello@gallant.solutions</strong>. Do not attempt to fix it yourself.</p>
<h3>The Friday rollup is empty</h3>
<p>There were no Kingsway Pharma meetings that week. The rollup is for Kingsway Pharma only; Church and Personal recordings remain in their folders but do not roll up.</p>
<h3>Something looks wrong or unexpected</h3>
<p>Email <strong>hello@gallant.solutions</strong> with:</p>
<ul>
  <li>What you were doing</li>
  <li>What you expected</li>
  <li>What you actually saw (a screenshot is helpful but not required)</li>
  <li>Approximate time of day</li>
</ul>
<p>Support is notified automatically when something breaks technically &mdash; the team is usually already investigating before you notice. Even so, please tell us if you see something off. The combination of automated alerts and your eyes-on report is what keeps the system invisible to you.</p>
<div class="pagebreak"></div>
"""


def donot() -> str:
    return """
<h2>9. What not to do</h2>
<p>These will not break the system permanently, but they create avoidable work for both of us:</p>
<ul>
  <li><strong>Do not edit files in your <code>.claude</code> folder.</strong> It is hidden by default. If you find it, leave it.</li>
  <li><strong>Do not delete Plaud recordings before they appear in OneDrive.</strong> Plaud is the source of truth; OneDrive is the output. If you delete from Plaud before the system has retrieved the recording, the meeting is lost.</li>
  <li><strong>Do not install Plaud or Claude updates yourself.</strong> The system handles its own updates automatically.</li>
  <li><strong>Do not disconnect your OneDrive account.</strong> Meetings stop appearing if OneDrive is signed out.</li>
  <li><strong>Do not move the &ldquo;Plaud Meetings&rdquo; folder out of OneDrive.</strong> Move files within it freely; the parent folder stays where it is.</li>
  <li><strong>Do not change the meeting keywords</strong> without telling us. If you start saying &ldquo;KP meeting&rdquo; instead of &ldquo;Kingsway Pharma,&rdquo; nothing routes correctly. To add a new meeting type &mdash; a new project, a new client &mdash; contact support and we will configure it.</li>
</ul>
<div class="pagebreak"></div>
"""


def maintenance() -> str:
    return """
<h2>10. How the system maintains itself</h2>
<p>Each night at 3:00 AM the system checks for a new version and installs it silently if one is available. You will not notice. A fix published at 6:00 PM today will be in place by tomorrow morning.</p>
<p><strong>Self-healing.</strong> If an update causes the system to fail, the previous working version is automatically restored at the next scheduled run. Our team is alerted within roughly an hour. You will see no interruption.</p>
<p><strong>Required conditions.</strong> For automatic updates to work, the computer must be on, signed in (lock screen is fine), and connected to the internet at 3:00 AM. A typical office computer with the lid closed and on Wi-Fi satisfies all three.</p>
<p>You will never be asked to apply an update manually. If we ever do need physical access to your machine, we will reach out first and schedule it.</p>
"""


def service() -> str:
    return """
<h2>11. Service and support</h2>
<h3>Standard channels</h3>
<table>
  <thead>
    <tr><th>Channel</th><th>Use it for</th><th>Response time</th></tr>
  </thead>
  <tbody>
    <tr><td>hello@gallant.solutions</td><td>Anything off, anything unclear, anything you want changed</td><td>Same business day</td></tr>
    <tr><td>Scheduled check-in call</td><td>End-of-week-1, then quarterly</td><td>30 minutes, pre-booked</td></tr>
  </tbody>
</table>
<h3>What our team monitors automatically</h3>
<p>Behind the scenes, the system reports to a monitoring service every time a scheduled run completes successfully. If a run fails, or fails to run at all, our team is alerted within an hour. In the great majority of cases the system has already restored itself by the time we look. You typically receive no notification because there is nothing to notice; we keep the rolling log so that we have evidence in the rare case that something needs escalation.</p>
<h3>Escalation path</h3>
<ol>
  <li><strong>First response &mdash; email.</strong> hello@gallant.solutions. Same business day. Most issues resolve here.</li>
  <li><strong>Second response &mdash; phone, by request.</strong> When email exchange is slower than the situation warrants, ask for a call.</li>
  <li><strong>On-site, if ever needed.</strong> We have engineered the system so this is extremely unlikely. If your situation truly requires it, we will travel.</li>
</ol>
<h3>Hours</h3>
<p>Standard support is Monday through Friday, 9 AM to 6 PM Eastern. Outside those hours, our system continues to monitor itself; human response resumes at the start of the next business day. If a recording is missed because the system was offline overnight, the next morning&rsquo;s 11:00 AM run will catch it up automatically.</p>
<div class="pagebreak"></div>
"""


def reference_card() -> str:
    return """
<h2>12. Quick reference card</h2>
<p class="tear-out">Tear out and keep near your computer.</p>
<div class="card">
  <p class="row"><span class="label">Record</span><span class="value">Within the first ten seconds, say <strong>Kingsway Pharma</strong>, <strong>Committee</strong>, <strong>Church</strong>, or <strong>Personal</strong>. Then name the people present. Then talk normally.</span></p>
  <p class="row"><span class="label">End of day</span><span class="value">Lock the screen with <strong>Windows key + L</strong>. Do not sign out.</span></p>
  <p class="row"><span class="label">Find your meetings</span><span class="value">OneDrive &rarr; <strong>Plaud Meetings</strong> &rarr; folder matching your keyword. Kingsway Pharma meetings are bucketed by work week, e.g., <code>KPM.May 25-29, 2026 (Week 22)/</code>.</span></p>
  <p class="row"><span class="label">Read the Friday rollup</span><span class="value">Same week folder. The file begins with <code>KPR.</code> rather than <code>KPM.</code> Best read Saturday morning.</span></p>
  <p class="row"><span class="label">Close out finished items</span><span class="value">In the rollup&rsquo;s Open Items table, change <strong>[ ]</strong> to <strong>[x]</strong> in the <strong>Done?</strong> column for anything finished &mdash; recorded, hallway-handoff, your own work, anything. Save. Next Friday&rsquo;s rollup will exclude it.</span></p>
  <p class="row"><span class="label">Mark a per-meeting action complete</span><span class="value">Open the meeting document. Change <strong>[ ]</strong> to <strong>[x]</strong> next to the action. Save. (Personal tracking only &mdash; for system closure use the rollup Done? column.)</span></p>
  <p class="row"><span class="label">Filename cheat sheet</span><span class="value"><code>KPM.</code> Kingsway Pharma Meeting  &middot;  <code>KPR.</code> Kingsway Pharma Rollup  &middot;  <code>CHM.</code> Church  &middot;  <code>PM.</code> Personal  &middot;  <code>UN.</code> Uncategorized.</span></p>
  <p class="heading">Three valid opening lines</p>
  <ul>
    <li><em>&ldquo;Kingsway Pharma meeting with [name], regarding [topic]...&rdquo;</em></li>
    <li><em>&ldquo;Church reflection on [topic]...&rdquo;</em></li>
    <li><em>&ldquo;Personal note, [topic]...&rdquo;</em></li>
  </ul>
  <p class="heading">Three things not to do</p>
  <ul>
    <li>Do not delete Plaud recordings until they have appeared in OneDrive.</li>
    <li>Do not sign out at end of day &mdash; lock the screen instead.</li>
    <li>Do not edit files in folders you do not recognize.</li>
  </ul>
  <p class="row" style="margin-top:10pt"><span class="label">Something off?</span><span class="value">Email <strong>hello@gallant.solutions</strong>. Same business day. Do not attempt to fix.</span></p>
</div>
<div class="pagebreak"></div>
"""


def glossary() -> str:
    terms = [
        ("Action item.", "A commitment captured during a meeting that requires follow-up. Each action item carries an owner, due date, and priority. Marked complete by changing [ ] to [x] in the document."),
        ("Carry-over.", "An open action item from a prior week that has not yet been marked complete. Carry-overs appear at the top of each Friday rollup, sorted oldest-first, with a status label of CRITICAL, ATTENTION, or OPEN."),
        ("Critical / Attention / Open.", "Aging labels applied to carry-overs in the weekly rollup. CRITICAL means an item has been open 21 or more days; ATTENTION means 14 or more days; OPEN means fewer than 14 days."),
        ("Done? column.", "The fifth column in the carry-over table. A [ ] checkbox per row. You change [ ] to [x] to tell the system that the item is finished. Closures are read by next Friday's rollup and applied automatically. This is the system's single closure surface — used for items that completed in any context, recorded or not."),
        ("ISO week.", "A standardized calendar week, Monday through Sunday, used throughout the system. Week numbers reset each year. Week 22 of 2026 runs Monday May 25 through Sunday May 31."),
        ("Keyword.", "The routing word spoken in the first ten seconds of a recording. The four configured keywords are Kingsway Pharma, Committee, Church, and Personal."),
        ("KPM / KPR / CHM / PM / UN.", "Filename prefixes that identify the file type at a glance. KPM = Kingsway Pharma Meeting. KPR = Kingsway Pharma Rollup. CHM = Church Meeting. PM = Personal Meeting. UN = Uncategorized."),
        ("Lock screen.", "The screen that appears when you press Windows key + L. The computer remains signed in and continues running scheduled tasks; the screen is simply protected from view."),
        ("OneDrive.", "The Microsoft cloud storage service where all generated documents are filed. The system writes to a folder called Plaud Meetings at the root of your OneDrive."),
        ("Plaud.", "The recording device. The source of truth for raw audio. Recordings are transcribed by Plaud's service and retrieved by our system at the next scheduled run."),
        ("Rollup.", "The Friday weekly summary document. One per Kingsway Pharma work week, filed into the same week folder as the meetings it summarizes."),
        ("Scheduled run.", "A point in time when the system retrieves new recordings, generates documents, and files them into OneDrive. The four scheduled runs each weekday are 11:00 AM, 4:00 PM, 4:30 PM (Friday rollup only), and 3:00 AM (system update check)."),
        ("Self-healing.", "The system's ability to automatically restore the previous working version when a fresh update causes a failure. Performed without human intervention; an alert is sent to the Gallant team within roughly an hour."),
        ("Work week.", "Monday through Friday. Used for bucketing Kingsway Pharma meetings into week folders. Recordings made on Saturday or Sunday land in the following Monday's batch and are filed into the work week they belong to."),
    ]
    rows = "\n".join(
        f'  <p class="glossary-term"><span class="term">{html.escape(t)}</span> {html.escape(d)}</p>'
        for t, d in terms
    )
    return f"""
<h2>13. Glossary</h2>
{rows}
<div class="pagebreak"></div>
"""


def doc_control() -> str:
    rows = [
        ("Document title.",         "Plaud Meetings — User Guide"),
        ("Document ID.",            "PMD-KINGSWAY-2026-CG-01-r1"),
        ("Edition.",                "1.1"),
        ("Issued.",                 "2026-05-25"),
        ("Classification.",         "Confidential — Client Use"),
        ("Prepared for.",           "Kingsway Pharma  ·  John Smith"),
        ("Prepared by.",            "Gallant Solutions  ·  LABS."),
        ("Engagement reference.",   "PMD-KINGSWAY-2026"),
        ("System version at issue.", "plaud-meetings-digest v2.2.5"),
    ]
    rows_html = "\n".join(
        f'  <p><span class="label">{html.escape(l)}</span>{html.escape(v)}</p>'
        for l, v in rows
    )
    return f"""
<h2>14. Document control</h2>
<div class="doc-control">
{rows_html}
</div>
<h3>Revision history</h3>
<table>
  <thead>
    <tr><th>Edition</th><th>Date</th><th>Author</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr><td>1.0</td><td>2026-05-24</td><td>Gallant Solutions</td><td>Initial client edition. Print-ready board-grade layout.</td></tr>
    <tr><td>1.1</td><td>2026-05-25</td><td>Gallant Solutions</td><td>Added v2.2.5 closure mechanism: Done? column on the carry-over table, Saturday closure ritual, third habit.</td></tr>
  </tbody>
</table>
<h3>Contact for corrections</h3>
<p>Notify hello@gallant.solutions of any error in this document. Corrections appear in the next revision and are re-issued at no cost.</p>
<hr style="border:none;border-top:1px solid {DIVID};margin:18pt 0;"/>
<p class="closing">This document is the property of the recipient. Reproduction for internal use is permitted. External distribution requires written consent from Gallant Solutions.</p>
<p class="closing">Gallant Solutions  ·  hello@gallant.solutions</p>
"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_html() -> str:
    body = "\n".join([
        cover(),
        foreword(),
        contents(),
        read_first(),
        first_week(),
        pipeline(),
        onedrive(),
        meeting_doc(),
        rollup_doc(),
        habits(),
        troubleshooting(),
        donot(),
        maintenance(),
        service(),
        reference_card(),
        glossary(),
        doc_control(),
    ])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Plaud Meetings — User Guide (Kingsway Pharma)</title>
{STYLE_BLOCK}
</head>
<body>
{body}
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render CLIENT-USER-GUIDE.md to HTML for Google Docs upload")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_html(), encoding="utf-8")
    print(f"OK  wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
