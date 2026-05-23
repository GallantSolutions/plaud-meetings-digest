# Plaud Meetings — Your User Guide

**Prepared by Gallant Solutions**
**Support:** hello@gallant.solutions

---

## What this system does for you

You record meetings on your Plaud device the way you always have.

Twice a day, this system automatically:

1. Pulls your new Plaud recordings
2. Reads them
3. Pulls out the action items, decisions, and key quotes
4. Drops a clean Word document into the right OneDrive folder

Every Friday afternoon, it writes you a one-page weekly rollup of your Kingsway Pharma meetings — read it over the weekend, walk into Monday ready.

**You don't need to open anything, click anything, or remember anything technical.** You just have to do two small things on your end. They're on the next page.

---

## The only two things you need to do

### 1. Say the meeting type at the very start of every recording

This is the most important habit. The system listens to the **first 30 seconds** of each recording. If it hears one of three keywords, it routes the meeting to the right folder. If it doesn't, the meeting ends up in an "Uncategorized" folder and you have to move it by hand.

There are three keywords for you:

- **Kingsway Pharma** — goes to the Kingsway Pharma folder, IS included in the Friday rollup
- **Church** — goes to the Church folder, NOT in the rollup
- **Personal** — goes to the Personal folder, NOT in the rollup

**Examples that work:**

> ✅ "Kingsway Pharma meeting with John Smith, we're going over Q3 plans."
>
> ✅ "Kingsway Pharma call with Sarah from medical affairs."
>
> ✅ "Church reflection — this week's sermon was about patience."
>
> ✅ "Personal note, reminder to book the dentist for the kids."

**Examples that do NOT work** (these route to Uncategorized):

> ❌ "Hey, so I wanted to talk about the Q3 numbers..."
>
> ❌ "Just thinking out loud here..."
>
> ❌ "Meeting with John about Kingsway Pharma." *(keyword too late — say it FIRST)*

**The rule:** Within the first ~10 seconds of pressing record, your second or third word should be one of `Kingsway Pharma`, `Church`, or `Personal`. After that, talk about whatever you want — who you're with, what it's about, what was decided.

**Also say who you're with.** Names you speak in the opening line end up in the filename, so you can scan your OneDrive folder and instantly see which Kingsway Pharma meeting was which.

> "Kingsway Pharma meeting with **John Smith and Sarah Jones** about Q3 plans" → file lands as `KP.Q3 Plans (John Smith, Sarah Jones).docx`

If you forget to name them, the file just gets the topic — `KP.Q3 Plans.docx` — which is still fine, just less scannable later.

### 2. Lock your computer at end of day — don't sign out

The system runs on your computer in the background. It only works when you're signed in. If you sign out fully, the scheduled pulls won't fire.

- **At end of day:** press `Windows key + L` to lock the screen. That's it. Walk away.
- **Closing your laptop lid** is fine — the computer sleeps and wakes up when needed.
- **Don't click "Sign out"** unless someone has asked you to. (You can shut down the computer when you want; missed runs catch up when you turn it back on.)

That's it. Those are the only two things you have to remember.

---

## Where your meetings appear

Open OneDrive on your computer. Look for a folder called **Plaud Meetings**. Inside it:

```
OneDrive/
  Plaud Meetings/
    Kingsway Pharma/        ← work meetings land here
      KP.Q3 Plans (John Smith).docx
      KP.Pricing Pushback (Sarah Jones, Mark Lee).docx
      KP.Compounding Demo (John Smith).docx
      _weekly/              ← Friday rollups land here
        KP.Weekly Rollup (2026-W21).docx
    Church/                 ← church reflections
      CH.Sermon on Patience.docx
    Personal/               ← personal notes
      P.Dentist Reminder.docx
    Uncategorized/          ← meetings where you forgot the keyword
      UN.Untitled.docx
```

**Filename format:** `<prefix>.<topic> (<who you met with>).docx`

- `KP.` = Kingsway Pharma · `CH.` = Church · `P.` = Personal · `UN.` = Uncategorized
- The topic is a short 3-6 word summary (the system writes this for you — you don't have to do anything)
- Attendee names come from your spoken opening line ("Kingsway Pharma meeting with **John Smith and Sarah Jones** about Q3" → `(John Smith, Sarah Jones)`)
- Solo recordings (Personal, Church) just get `P.Topic.docx` with no attendees in the name

Click any `.docx` to open it in Word. Each document has:

- **Recap** — a clean 2-3 sentence summary of the meeting
- **Action items** — rendered as `☐` checklist boxes you can tick off as you complete them
- **Decisions made** — anything that was settled in the meeting
- **Open questions** — anything that came up and didn't get resolved
- **Key quotes** — important things people actually said, verbatim

You can rename files, move them, edit them — they're yours. The system doesn't reach back into OneDrive once a meeting has been written.

### The Friday weekly rollup

Every Friday at 5:30 PM, you get a one-page document at:

```
OneDrive/Plaud Meetings/Kingsway Pharma/_weekly/KP.Weekly Rollup (2026-W##).docx
```

This is the most important file of your week. It synthesizes everything from your Kingsway Pharma meetings that week:

- The top 5 things you said you'd do this week
- Anything you said you'd do that's been carrying over for 14+ days (red flag)
- Open questions you still need to answer
- Key themes / patterns

Read this Saturday morning with coffee. It will set up your Monday.

---

## When things look off

### A meeting landed in the "Uncategorized" folder

You forgot to say the keyword at the start of the recording. Two options:

1. **Re-record it** (if you can — sometimes you can't).
2. **Manually move the `.docx`** from Uncategorized into the right folder (drag-and-drop in OneDrive).

Don't worry about this happening once in a while. The system tracks it. If it starts happening every day, the support team will reach out to retrain you.

### A meeting didn't appear at all

Wait until after the next scheduled pull (12:30 PM or 5:00 PM that day). The system catches up on whatever's there. If you recorded at 11 AM, it'll appear after 12:30 PM. If you recorded at 4 PM, it'll appear after 5:00 PM.

**If it still hasn't appeared by the next morning:** email Gallant support (`hello@gallant.solutions`). Don't try to "fix" it yourself.

### The Friday rollup is empty

That just means you had no Kingsway Pharma meetings that week. The rollup is for Kingsway Pharma only. Church and Personal meetings stay in their folders but don't roll up.

### Something looks wrong / weird / broken

**Do NOT try to fix it yourself.** The system has a lot of moving parts and changes you make can break things in ways that are hard to debug remotely.

**Instead:** email `hello@gallant.solutions` with:

- What you were doing when it happened
- What you expected to see
- What you actually saw (a screenshot helps, but isn't required)
- Roughly what time of day it happened

The support team gets an automatic alert when something breaks on the technical side. Usually they'll already be on it before you notice. But if you see something we missed, let us know.

---

## Things you should NOT do

These won't break the world, but they create extra work for the support team:

- **Don't open or edit the `.claude` folder** in your user directory. It's invisible by default — if you happen to find it, leave it alone.
- **Don't delete recordings from Plaud** until you've seen them appear in OneDrive. Plaud is the source of truth; OneDrive is the output. If you delete from Plaud before the system has pulled it, the meeting is gone.
- **Don't try to install Plaud or Claude updates yourself.** The system handles its own updates automatically every night.
- **Don't disconnect from your OneDrive account.** If you do, meetings stop appearing.
- **Don't move the "Plaud Meetings" folder out of OneDrive.** Move files inside it freely, but the parent folder stays where it is.
- **Don't change the meeting keywords (Kingsway Pharma / Church / Personal)** without telling us. If you start saying "KP meeting" instead of "Kingsway Pharma," nothing routes correctly. If you want different keywords (e.g., a new project), email us and we'll add them.

---

## Updates happen automatically

Every night at 3:00 AM (while you're asleep), the system checks if there's a new version of itself and installs it silently. You won't notice anything. If we push a fix at 6 PM today, you'll have it by tomorrow morning.

If something happens during an update and it breaks, the support team gets an automatic alert within ~1 hour. Usually we'll fix it before you start your day.

This requires the computer to be on, signed in (lock screen is fine), and connected to the internet at 3 AM. Most office computers meet this naturally.

---

## Quick reference card (the one-page version)

**RECORD:** Say `Kingsway Pharma` / `Church` / `Personal` in the first ~10 seconds. Then say who you're with. Then talk normally.

**END OF DAY:** Lock the screen (`Windows key + L`). Don't sign out.

**FIND YOUR MEETINGS:** OneDrive → Plaud Meetings → the folder matching your keyword.

**THE FRIDAY ROLLUP:** OneDrive → Plaud Meetings → Kingsway Pharma → _weekly. Read it Saturday morning.

**ACTION ITEMS:** Open any `.docx`. Look for `☐` checkboxes. Tick them off as you finish.

**SOMETHING'S OFF:** Email `hello@gallant.solutions`. Don't try to fix it.

**THREE GOOD OPENING LINES:**
- "Kingsway Pharma meeting with [name]..."
- "Church reflection on..."
- "Personal note about..."

**THE THREE THINGS NOT TO DO:**
- Don't delete Plaud recordings until they've appeared in OneDrive
- Don't sign out of your computer at end of day (lock it)
- Don't edit files in folders you don't recognize

---

*Questions? Email `hello@gallant.solutions`. We respond same-day.*

*This guide is version 1.0 — last updated 2026-05-23.*
