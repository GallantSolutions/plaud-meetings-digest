# Plaud Meetings — User Guide

**Prepared for:** Kingsway Pharma
**Recipient:** John Smith
**Prepared by:** Gallant Solutions · LABS.
**Engagement reference:** PMD-KINGSWAY-2026
**Document classification:** Confidential — Client Use
**Edition:** 1.1 · 2026-05-25

---

## Foreword

John,

This document accompanies the meeting-capture system Gallant has built and deployed for your work at Kingsway Pharma. The system runs quietly in the background on your computer. Twice each weekday it gathers your recordings, transforms them into clean, well-structured Word documents, and files them into OneDrive. Each Friday it produces a one-page weekly rollup that brings the week into focus before the weekend.

Two things matter for it to work well. They take seconds. They are described in detail on the pages that follow, and summarized on the pull-out reference card near the back.

We have engineered the system to take care of itself — it updates automatically each night, alerts our team within an hour if something fails, and reverts itself when a fresh update misbehaves. You should not need to think about it. If something ever looks off, we ask only that you tell us; you do not need to attempt to fix it.

This is a relationship, not a software install. Treat us as the line of escalation any time the system surprises you. Same-day response is the standard you should hold us to.

Welcome aboard.

— The Gallant team
hello@gallant.solutions

---

## Contents

1. Read this first
2. Your first week
3. How recordings become documents
4. Where your meetings appear in OneDrive
5. What is inside each meeting document
6. What is inside the Friday weekly rollup
7. Daily and weekly habits
8. When something looks off
9. What not to do
10. How the system maintains itself
11. Service and support
12. Quick reference card *(pull-out)*
13. Glossary
14. Document control

---

## 1. Read this first

If you read only one page of this guide, read this one.

**Three habits.** That is the complete user-side checklist.

1. **At the start of every recording, say one of three keywords within the first ten seconds:** `Kingsway Pharma`, `Church`, or `Personal`. Then name the people you are meeting with. Then talk normally.
2. **At end of day, lock your screen** with `Windows key + L`. Do not sign out. Do not shut down except when you choose to.
3. **Saturday morning, open the Friday rollup and close out finished items.** Read the "Open Items from Prior Weeks" table at the top. For anything that's actually done — even if no meeting captured it (a hallway handoff, an email you sent, a deliverable that arrived on your desk) — change the `[ ]` in the **Done?** column to `[x]` and save. Takes 60 seconds. Next Friday's rollup will exclude those items automatically.

**That is it.** Recordings flow into Plaud the way they always have. Twice each weekday, the system pulls anything new, generates a clean Word document for each meeting, and files it into OneDrive under `Plaud Meetings / [matching folder]`. Each Friday afternoon you receive a one-page rollup of the week's Kingsway Pharma meetings.

**You never open a tool, click a button, or run a command.** The system is designed so the only software you interact with is OneDrive — where the finished documents appear — and Word — where you read and annotate them.

**If something looks off, email** `hello@gallant.solutions`**.** Do not attempt repairs. Our team is usually already aware before you are.

---

## 2. Your first week

A short orientation. Each step takes under a minute.

### Day 1 — Record a single Kingsway Pharma meeting

Press record on your Plaud as you normally would. Say aloud: *"Kingsway Pharma meeting with [name], about [topic]."* Speak naturally for the rest of the meeting.

Within a few hours, open OneDrive and navigate to **Plaud Meetings / Kingsway Pharma**. You will see a week folder named for the current work week (e.g., `KPM.May 25-29, 2026 (Week 22)/`). Inside it: a Word document named after the topic and attendees you spoke. Open it. Read it. This confirms the routing works for you.

### Day 2 — Record a Church or Personal note

Press record. Say *"Personal note, [topic]"* or *"Church reflection on [topic]."* Verify the file appears in **Plaud Meetings / Personal** or **Plaud Meetings / Church**. You now have direct evidence that the three keywords route to three different folders.

### Day 3 to Friday — Use the system normally

Record meetings as they happen. Keep the keyword-first habit. Lock your screen at end of day rather than signing out.

### Friday afternoon — Read your first rollup

Open **Plaud Meetings / Kingsway Pharma / [this week's folder]**. The rollup file begins with `KPR.` and is named for the work week (e.g., `KPR.May 25-29, 2026 (Week 22).docx`). The rollup opens with **Open Items from Prior Weeks** — items still outstanding from earlier meetings, sorted oldest first.

In the first week there will be no carry-overs (no prior weeks exist yet). The section will read: *"All prior-week items closed. No carry-overs this week."* From week two onward, this is the most important section of the rollup; it surfaces commitments that are quietly aging.

**Beginning week two, this is also where you close things out.** The carry-over table includes a **Done?** column with a `[ ]` checkbox per row. Read the table Saturday morning, change `[ ]` to `[x]` on anything that's actually finished — whether it was completed in a recorded meeting, by an email you sent, by a colleague who dropped off the deliverable, or anything else — and save the document. Next Friday's rollup will exclude what you closed. This is the only piece of bookkeeping the system asks of you, and it takes under a minute.

### End of week 1 — One brief check-in call

A member of the Gallant team will reach out for a 15-minute call. Bring any friction, confusion, or "I wish it did this" observations. Adjustments made in the first week are free (within reason); adjustments made in month two require a coordinated update.

---

## 3. How recordings become documents

The system operates on a fixed daily schedule. You do not need to remember the schedule — it is described here so that the rhythm of new documents appearing is predictable rather than mysterious.

| When | What happens |
|---|---|
| 12:30 PM each weekday | Pulls all morning recordings, generates documents, files into OneDrive |
| 5:00 PM each weekday | Pulls all afternoon recordings, generates documents, files into OneDrive |
| 5:30 PM each Friday | Synthesizes the Kingsway Pharma weekly rollup |
| 3:00 AM each night | Checks for system updates; installs silently if available |

A recording made at 11:00 AM appears after 12:30 PM. A recording made at 4:00 PM appears after 5:00 PM. A recording made over the weekend lands the following Monday at 12:30 PM.

**The pipeline, in plain terms:**

1. You press record on Plaud and speak. The first ten seconds determine routing.
2. Plaud transcribes the recording on your behalf.
3. At the next scheduled run, our system retrieves the transcript.
4. It re-reads the transcript carefully and extracts the meaning: a recap, action items, decisions, open questions, and notable quotes.
5. It writes a Word document with that content and files it into the correct OneDrive folder.

The entire process is supervised by software designed to fail safely. If any step misbehaves, our team is notified within an hour, the previous working version is restored automatically, and the missed recordings catch up on the following scheduled run.

---

## 4. Where your meetings appear in OneDrive

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

The trailing letter on each prefix identifies the file type, so they remain unambiguous if you happen to keep other files in OneDrive that begin with the same two letters.

| Prefix | Meaning |
|---|---|
| `KPM.` | Kingsway Pharma **Meeting** (single meeting note) |
| `KPR.` | Kingsway Pharma **Rollup** (Friday weekly summary) |
| `CHM.` | Church Meeting |
| `PM.`  | Personal Meeting |
| `UN.`  | Uncategorized (keyword missing — manual triage) |

### How files are organized

- **Kingsway Pharma meetings** are bucketed by work week (Monday through Friday). A meeting recorded any time May 25–29, 2026 — including weekend recordings within that ISO week — lands in `KPM.May 25-29, 2026 (Week 22)/`. The Friday weekly rollup for that week lives in the same folder. One folder represents one week's worth of Kingsway Pharma work.
- **Church and Personal** are flat — files sit directly in the folder with no week subfolders. Sparse-volume content does not need bucketing.
- The topic in the filename is a three- to six-word summary the system writes from the meeting content. You do not enter it.
- Attendee names come from the opening line. Solo recordings produce filenames without parentheses.

---

## 5. What is inside each meeting document

Each per-meeting document is one to two pages with the following structure:

- **Title block** — meeting type, topic, attendees, date, and recording duration
- **Recap** — a two- to three-sentence executive summary capturing the essence of the conversation
- **Action items** — each with a `[ ]` checkbox, owner, due date, and priority
- **Decisions recorded** — what was decided and why
- **Open questions** — anything raised but unresolved
- **Notable quotes** — verbatim statements worth preserving

To mark an action item complete, open the document in Word, change `[ ]` to `[x]`, and save. The system does not auto-detect completion; your edits are for your own tracking and visible to anyone you share the document with.

---

## 6. What is inside the Friday weekly rollup

The rollup is engineered to be read in roughly seven minutes over a Saturday morning coffee, leaving Monday already prioritized.

The document opens with **Open Items from Prior Weeks** as a five-column table sorted oldest-first:

| Action Item | Days Open | Status | Source Meeting | Done? |

The Status column uses three text labels:

- **CRITICAL** — open 21 or more days
- **ATTENTION** — open 14 or more days
- **OPEN** — open fewer than 14 days

The **Done?** column carries a `[ ]` checkbox per row. This is your closure surface — the one place you tell the system that something is finished. Spend 60 seconds Saturday morning reviewing the table and flipping `[ ]` to `[x]` on anything that's actually complete. Save the document. Next Friday's rollup will exclude those items automatically.

**Closure works for anything, recorded or not.** If a colleague dropped off a deliverable on Wednesday and no meeting captured the handoff, the system has no way to know — only you do. Mark `[x]`. If you sent an email completing an action item, mark `[x]`. The system doesn't try to guess. It just listens to your gesture.

This section is intentionally placed at the top. Stuck commitments across weeks are the highest-leverage information in the document; the layout is designed to make them impossible to skip.

If you have closed everything out, the section reads simply: *"All prior-week items closed. No carry-overs this week."*

Subsequent sections, in order:

1. **Next Week's Focus Picks** — three to five high-leverage items with rationale
2. **High Priority (This Week)** — items demanding attention in the coming week
3. **Action Items by Context** — grouped by category
4. **Decisions Recorded** — the week's commitments
5. **Open Questions** — what remains unresolved
6. **Observations** — recurring patterns the system identified
7. **Summary** — one-line totals across the document

---

## 7. Daily and weekly habits

### The recording habit

The opening ten seconds of every recording determine where the file lands. Three forms work consistently:

> "Kingsway Pharma meeting with John Smith, going over Q3 plans."
>
> "Church reflection — this week's sermon was about patience."
>
> "Personal note, reminder to book the dentist."

These do **not** work:

> "So I wanted to talk about the Q3 numbers..."  *(no keyword)*
>
> "Meeting with John about Kingsway Pharma..."  *(keyword too late)*

**The rule:** within the first ten seconds, one of `Kingsway Pharma`, `Church`, or `Personal` must be spoken. After that, talk about whatever you want — who you are with, what it is about, what was decided.

**Name your attendees in the opening line.** Spoken names appear in the filename, which makes scanning OneDrive much easier later.

> "Kingsway Pharma meeting with **John Smith and Sarah Jones** about Q3 plans" → file lands as `KPM.Q3 Plans (John Smith, Sarah Jones).docx`

If you forget to name attendees, the file still gets the topic — `KPM.Q3 Plans.docx` — and remains usable, just less scannable.

### The end-of-day habit

The system runs in the background on your computer. It only works while you are signed in. If you sign out, the scheduled runs do not fire.

- **At end of day:** press `Windows key + L` to lock the screen.
- **Closing the laptop lid is fine.** The computer sleeps and wakes for scheduled runs.
- **Do not click "Sign out"** unless asked. You can shut down the computer when you want; missed runs catch up the next time you start it.

That is the complete user-side checklist. Two habits, both passive.

---

## 8. When something looks off

### A meeting landed in the "Uncategorized" folder

The keyword was not stated at the start. Two options:

1. Re-record if possible.
2. Manually move the document from `Uncategorized/` into the correct folder.

Occasional misses are normal. If it begins happening regularly, contact support and we will review the keyword set with you.

### A meeting did not appear at all

Wait until after the next scheduled run (12:30 PM or 5:00 PM that day). The system catches up on whatever Plaud has. A recording made at 11:00 AM will appear after 12:30 PM; a recording made at 4:00 PM will appear after 5:00 PM.

If it still has not appeared by the next morning, email `hello@gallant.solutions`. Do not attempt to fix it yourself.

### The Friday rollup is empty

There were no Kingsway Pharma meetings that week. The rollup is for Kingsway Pharma only; Church and Personal recordings remain in their folders but do not roll up.

### Something looks wrong or unexpected

Email `hello@gallant.solutions` with:

- What you were doing
- What you expected
- What you actually saw (a screenshot is helpful but not required)
- Approximate time of day

Support is notified automatically when something breaks technically — the team is usually already investigating before you notice. Even so, please tell us if you see something off. The combination of automated alerts and your eyes-on report is what keeps the system invisible to you.

---

## 9. What not to do

These will not break the system permanently, but they create avoidable work for both of us:

- **Do not edit files in your `.claude` folder.** It is hidden by default. If you find it, leave it.
- **Do not delete Plaud recordings before they appear in OneDrive.** Plaud is the source of truth; OneDrive is the output. If you delete from Plaud before the system has retrieved the recording, the meeting is lost.
- **Do not install Plaud or Claude updates yourself.** The system handles its own updates automatically.
- **Do not disconnect your OneDrive account.** Meetings stop appearing if OneDrive is signed out.
- **Do not move the "Plaud Meetings" folder out of OneDrive.** Move files within it freely; the parent folder stays where it is.
- **Do not change the meeting keywords** without telling us. If you start saying "KP meeting" instead of "Kingsway Pharma," nothing routes correctly. To add a new meeting type — a new project, a new client — contact support and we will configure it.

---

## 10. How the system maintains itself

Each night at 3:00 AM the system checks for a new version and installs it silently if one is available. You will not notice. A fix published at 6:00 PM today will be in place by tomorrow morning.

**Self-healing.** If an update causes the system to fail, the previous working version is automatically restored at the next scheduled run. Our team is alerted within roughly an hour. You will see no interruption.

**Required conditions.** For automatic updates to work, the computer must be on, signed in (lock screen is fine), and connected to the internet at 3:00 AM. A typical office computer with the lid closed and on Wi-Fi satisfies all three.

You will never be asked to apply an update manually. If we ever do need physical access to your machine, we will reach out first and schedule it.

---

## 11. Service and support

### Standard channels

| Channel | Use it for | Response time |
|---|---|---|
| `hello@gallant.solutions` | Anything off, anything unclear, anything you want changed | Same business day |
| Scheduled check-in call | End-of-week-1, then quarterly | 30 minutes, pre-booked |

### What our team monitors automatically

Behind the scenes, the system reports to a monitoring service every time a scheduled run completes successfully. If a run fails, or fails to run at all, our team is alerted within an hour. In the great majority of cases the system has already restored itself by the time we look. You typically receive no notification because there is nothing to notice; we keep the rolling log so that we have evidence in the rare case that something needs escalation.

### Escalation path

1. **First response — email.** `hello@gallant.solutions`. Same business day. Most issues resolve here.
2. **Second response — phone, by request.** When email exchange is slower than the situation warrants, ask for a call.
3. **On-site, if ever needed.** We have engineered the system so this is extremely unlikely. If your situation truly requires it, we will travel.

### Hours

Standard support is Monday through Friday, 9 AM to 6 PM Eastern. Outside those hours, our system continues to monitor itself; human response resumes at the start of the next business day. If a recording is missed because the system was offline overnight, the next morning's 12:30 PM run will catch it up automatically.

---

## 12. Quick reference card

*Tear out and keep near your computer.*

---

**RECORD** — Within the first ten seconds, say `Kingsway Pharma`, `Church`, or `Personal`. Then name the people present. Then talk normally.

**END OF DAY** — Lock the screen with `Windows key + L`. Do not sign out.

**FIND YOUR MEETINGS** — OneDrive → `Plaud Meetings` → folder matching your keyword. Kingsway Pharma meetings are bucketed by work week, e.g., `KPM.May 25-29, 2026 (Week 22)/`.

**READ THE FRIDAY ROLLUP** — Same week folder. The file begins with `KPR.` rather than `KPM.`. Best read Saturday morning.

**CLOSE OUT FINISHED ITEMS** — In the rollup's **Open Items from Prior Weeks** table, change `[ ]` to `[x]` in the **Done?** column for anything finished — recorded, hallway-handoff, your own work, anything. Save. Next Friday's rollup will exclude it.

**MARK A PER-MEETING ACTION COMPLETE** — Open the meeting document in Word. Change `[ ]` to `[x]` next to the action. Save. Personal tracking only; for system closure use the rollup's Done? column.

**FILENAME CHEAT SHEET** — `KPM.` Kingsway Pharma Meeting · `KPR.` Kingsway Pharma Rollup · `CHM.` Church Meeting · `PM.` Personal Meeting · `UN.` Uncategorized.

**THREE VALID OPENING LINES**

- "Kingsway Pharma meeting with [name], regarding [topic]..."
- "Church reflection on [topic]..."
- "Personal note, [topic]..."

**THREE THINGS NOT TO DO**

- Do not delete Plaud recordings until they have appeared in OneDrive.
- Do not sign out at end of day — lock the screen instead.
- Do not edit files in folders you do not recognize.

**SOMETHING OFF?** — Email `hello@gallant.solutions`. Same business day. Do not attempt to fix.

---

## 13. Glossary

**Action item.** A commitment captured during a meeting that requires follow-up. Each action item carries an owner, due date, and priority. Marked complete by changing `[ ]` to `[x]` in the document.

**Carry-over.** An open action item from a prior week that has not yet been marked complete. Carry-overs appear at the top of each Friday rollup, sorted oldest-first, with a status label of CRITICAL, ATTENTION, or OPEN.

**Done? column.** The fifth column in the carry-over table. A `[ ]` checkbox per row. You change `[ ]` to `[x]` to tell the system that the item is finished. Closures are read by next Friday's rollup and applied automatically. This is the system's single closure surface — used for items that completed in any context, recorded or not.

**Critical / Attention / Open.** Aging labels applied to carry-overs in the weekly rollup. CRITICAL means an item has been open 21 or more days; ATTENTION means 14 or more days; OPEN means fewer than 14 days.

**ISO week.** A standardized calendar week, Monday through Sunday, used throughout the system. Week numbers reset each year. Week 22 of 2026 runs Monday May 25 through Sunday May 31.

**Keyword.** The routing word spoken in the first ten seconds of a recording. The three configured keywords are `Kingsway Pharma`, `Church`, and `Personal`.

**KPM / KPR / CHM / PM / UN.** Filename prefixes that identify the file type at a glance. KPM = Kingsway Pharma Meeting. KPR = Kingsway Pharma Rollup. CHM = Church Meeting. PM = Personal Meeting. UN = Uncategorized.

**Lock screen.** The screen that appears when you press `Windows key + L`. The computer remains signed in and continues running scheduled tasks; the screen is simply protected from view.

**OneDrive.** The Microsoft cloud storage service where all generated documents are filed. The system writes to a folder called `Plaud Meetings` at the root of your OneDrive.

**Plaud.** The recording device. The source of truth for raw audio. Recordings are transcribed by Plaud's service and retrieved by our system at the next scheduled run.

**Rollup.** The Friday weekly summary document. One per Kingsway Pharma work week, filed into the same week folder as the meetings it summarizes.

**Scheduled run.** A point in time when the system retrieves new recordings, generates documents, and files them into OneDrive. The four scheduled runs each weekday are 12:30 PM, 5:00 PM, 5:30 PM (Friday rollup only), and 3:00 AM (system update check).

**Self-healing.** The system's ability to automatically restore the previous working version when a fresh update causes a failure. Performed without human intervention; an alert is sent to the Gallant team within roughly an hour.

**Work week.** Monday through Friday. Used for bucketing Kingsway Pharma meetings into week folders. Recordings made on Saturday or Sunday land in the following Monday's batch and are filed into the work week they belong to.

---

## 14. Document control

**Document title.** Plaud Meetings — User Guide
**Document ID.** PMD-KINGSWAY-2026-CG-01-r1
**Edition.** 1.1
**Issued.** 2026-05-25
**Classification.** Confidential — Client Use
**Prepared for.** Kingsway Pharma · John Smith
**Prepared by.** Gallant Solutions · LABS.
**Engagement reference.** PMD-KINGSWAY-2026
**System version at issue.** plaud-meetings-digest v2.2.5

### Revision history

| Edition | Date | Author | Notes |
|---|---|---|---|
| 1.0 | 2026-05-24 | Gallant Solutions | Initial client edition. Print-ready board-grade layout. |
| 1.1 | 2026-05-25 | Gallant Solutions | Added v2.2.5 closure mechanism: Done? column on the carry-over table, Saturday closure ritual, third habit. |

### Contact for corrections

Notify `hello@gallant.solutions` of any error in this document. Corrections appear in the next revision and are re-issued at no cost.

---

*This document is the property of the recipient. Reproduction for internal use is permitted. External distribution requires written consent from Gallant Solutions.*

*Gallant Solutions · hello@gallant.solutions*
