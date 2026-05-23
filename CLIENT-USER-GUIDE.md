# Plaud Meetings — User Guide

**Prepared by Gallant Solutions**
**Support:** hello@gallant.solutions

---

## What this system does

You record meetings on your Plaud device the way you always have.

Twice each weekday, this system automatically:

1. Pulls your new Plaud recordings
2. Re-reads the transcripts
3. Extracts a recap, action items, decisions, open questions, and notable quotes
4. Writes a clean Word document into the correct OneDrive folder

Each Friday afternoon, it synthesizes a one-page weekly rollup of your Kingsway Pharma meetings — designed to be read over the weekend so Monday starts with priorities locked.

You do not need to open anything, click anything, or remember anything technical. You do need to do two small things on your end, described on the next page.

---

## What you need to do

### 1. State the meeting type at the start of every recording

This is the single most important habit. The system reads the first 30 seconds of each recording and routes it to the right folder based on a keyword. If no keyword is detected, the meeting lands in an "Uncategorized" folder and you have to move it by hand.

There are three keywords:

- **Kingsway Pharma** — routes to the Kingsway Pharma folder, included in the Friday weekly rollup
- **Church** — routes to the Church folder, not in the rollup
- **Personal** — routes to the Personal folder, not in the rollup

**Lines that work:**

> "Kingsway Pharma meeting with John Smith, going over Q3 plans."
>
> "Kingsway Pharma call with Sarah from medical affairs."
>
> "Church reflection — this week's sermon was about patience."
>
> "Personal note, reminder to book the dentist."

**Lines that do not work** (these route to Uncategorized):

> "So I wanted to talk about the Q3 numbers..."
>
> "Just thinking out loud here..."
>
> "Meeting with John about Kingsway Pharma." — keyword is too late; say it first

**The rule:** within the first ten seconds of pressing record, one of `Kingsway Pharma`, `Church`, or `Personal` must be spoken. After that, talk about whatever you want — who you are with, what it is about, what was decided.

**Name your attendees in the opening line.** Names you speak appear in the filename, which makes scanning OneDrive much easier later.

> "Kingsway Pharma meeting with **John Smith and Sarah Jones** about Q3 plans" → file lands as `KPM.Q3 Plans (John Smith, Sarah Jones).docx`

If you forget to name attendees, the file still gets the topic — `KPM.Q3 Plans.docx` — and remains usable, just less scannable.

### 2. Lock your computer at end of day — do not sign out

The system runs in the background on your computer. It only works while you are signed in. If you sign out, the scheduled pulls do not fire.

- **At end of day:** press `Windows key + L` to lock the screen.
- **Closing the laptop lid is fine** — the computer sleeps and wakes when needed.
- **Do not click "Sign out"** unless asked. You can shut down the computer when you want; missed runs catch up when you start it again.

That is the complete user-side checklist. Two habits, both passive.

---

## Where your meetings appear

Open OneDrive. Look for a folder named **Plaud Meetings**. Inside:

```
OneDrive/
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
      UN.Untitled.docx
```

### Filename convention

`<prefix>.<topic> (<attendees>).docx`

The trailing letter on each prefix identifies the file kind, so they are unambiguous even if you keep other files in OneDrive that happen to begin with the same two letters:

| Prefix | Meaning |
|---|---|
| `KPM.` | Kingsway Pharma **Meeting** (single meeting note) |
| `KPR.` | Kingsway Pharma **Rollup** (Friday weekly summary) |
| `CHM.` | Church Meeting |
| `PM.`  | Personal Meeting |
| `UN.`  | Uncategorized |

### How files are organized

- **Kingsway Pharma meetings** are bucketed by work week (Monday through Friday). A meeting recorded any time May 25–29, 2026 — including weekend recordings within that ISO week — lands in `KPM.May 25-29, 2026 (Week 22)/`. The Friday weekly rollup for that week lives in the same folder. One folder represents one week's worth of work.
- **Church and Personal** are flat — files sit directly in the folder with no week subfolders. Sparse-volume content does not need bucketing.
- The topic in the filename is a three- to six-word summary written by the system from the meeting content. You do not enter it.
- Attendee names come from the opening line. Solo recordings produce filenames without parentheses.

### What is inside each meeting document

Each per-meeting `.docx` is a one- to two-page document with:

- **Title block** — meeting type, topic, attendees, date, duration
- **Recap** — a two- to three-sentence executive summary
- **Action items** — each with `[ ]` checkbox, owner, due date, priority
- **Decisions recorded** — what was decided and why
- **Open questions** — anything raised but unresolved
- **Notable quotes** — verbatim statements worth preserving

To mark an action item complete: open the document in Word, change `[ ]` to `[x]`, save. The system does not auto-detect completion — your edits are for your own tracking.

### What is inside the Friday weekly rollup

The weekly rollup opens with **Open Items from Prior Weeks** rendered as a 4-column table sorted oldest-first:

| Action Item | Days Open | Status | Source Meeting |

The Status column uses three text labels:

- **CRITICAL** — open 21+ days
- **ATTENTION** — open 14+ days
- **OPEN** — open under 14 days

This section is intentionally at the top of the document. Stuck commitments across weeks are the highest-leverage information; confront them before planning next week's focus.

If you have closed everything out, the section reads simply: "All prior-week items closed. No carry-overs this week."

Subsequent sections, in order:

1. Next Week's Focus Picks — 3 to 5 high-leverage items with rationale
2. High Priority (This Week)
3. Action Items by Context — grouped by category
4. Decisions Recorded
5. Open Questions
6. Observations — recurring patterns the system identified
7. Summary — one-line totals

---

## When something looks off

### A meeting landed in the "Uncategorized" folder

The keyword was not stated at the start. Two options:

1. Re-record if possible.
2. Manually move the `.docx` from `Uncategorized/` into the correct folder.

Occasional misses are normal. If it starts happening regularly, contact support and we will revisit the keyword set.

### A meeting did not appear at all

Wait until after the next scheduled pull (12:30 PM or 5:00 PM that day). The system catches up on whatever is in Plaud. A recording made at 11:00 AM will appear after 12:30 PM. A recording made at 4:00 PM will appear after 5:00 PM.

If it still has not appeared by the next morning, email `hello@gallant.solutions`. Do not attempt to fix it yourself.

### The Friday rollup is empty

That means there were no Kingsway Pharma meetings that week. The rollup is for Kingsway Pharma only. Church and Personal recordings remain in their folders but do not roll up.

### Something looks wrong or unexpected

Email `hello@gallant.solutions` with:

- What you were doing
- What you expected
- What you actually saw (a screenshot is helpful but not required)
- Approximate time of day

Support is notified automatically when something breaks technically. The team is usually already investigating before you notice. Even so, please tell us if you see something off.

---

## What not to do

These will not break the system permanently but they create avoidable work:

- **Do not edit files in your `.claude` folder.** It is hidden by default. If you find it, leave it.
- **Do not delete Plaud recordings before they appear in OneDrive.** Plaud is the source of truth; OneDrive is the output. If you delete from Plaud before the system has pulled the recording, the meeting is lost.
- **Do not install Plaud or Claude updates yourself.** The system handles its own updates automatically.
- **Do not disconnect your OneDrive account.** Meetings stop appearing if OneDrive is signed out.
- **Do not move the "Plaud Meetings" folder out of OneDrive.** Move files within it freely; the parent folder stays where it is.
- **Do not change the meeting keywords** without telling us. If you start saying "KP meeting" instead of "Kingsway Pharma," nothing routes correctly. To add a new meeting type (a new project, a new client, etc.), contact support.

---

## Updates run automatically

Each night at 3:00 AM, the system checks for a new version and installs it silently if available. You will not notice. A fix published at 6:00 PM today will be in place by tomorrow morning.

If an update breaks something, support is alerted within roughly an hour of the next scheduled run failing. The system also self-heals: it automatically reverts to the previous version when a fresh update causes a failure.

For this to work, the computer must be on, signed in (lock screen is fine), and on the internet at 3:00 AM. A typical office computer satisfies this.

---

## Quick reference

**Record** — Say `Kingsway Pharma` / `Church` / `Personal` within the first ten seconds. Then name attendees. Then talk normally.

**End of day** — Lock the screen (`Windows key + L`). Do not sign out.

**Find your meetings** — OneDrive → Plaud Meetings → the folder matching your keyword. Kingsway Pharma meetings are bucketed by work week: `KPM.May 25-29, 2026 (Week 22)/`.

**Read the Friday rollup** — Same week folder as the meetings. The file begins with `KPR.` instead of `KPM.`. Best read Saturday morning.

**Mark an action item complete** — Open the document in Word. Change `[ ]` to `[x]`. Save.

**Filename cheat sheet** — `KPM.` Kingsway Pharma Meeting · `KPR.` Kingsway Pharma Rollup · `CHM.` Church · `PM.` Personal · `UN.` Uncategorized.

**Something is off** — Email `hello@gallant.solutions`. Do not attempt to fix.

**Three valid opening lines**

- "Kingsway Pharma meeting with [name], regarding [topic]..."
- "Church reflection on [topic]..."
- "Personal note, [topic]..."

**Three things not to do**

- Do not delete Plaud recordings until they have appeared in OneDrive.
- Do not sign out at end of day — lock the screen instead.
- Do not edit files in folders you do not recognize.

---

*Questions: `hello@gallant.solutions`. Same-day response.*

*Guide version 2.0 — last updated 2026-05-23.*
