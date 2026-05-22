---
name: weekly-rollup
description: Synthesize the week's action items for ONLY the meeting types flagged include_in_weekly_rollup (default for this client = Kingsway Pharma) into a single Friday-evening rollup. Output destination matches the install — Word doc in OneDrive on Windows; Notion page on Mac. Includes next-week focus picks, carry-overs from prior weeks, decisions, themes Claude noticed across the week's meetings.
---

# weekly-rollup

This skill produces the **weekly rollup** the user opens Friday evening to plan the coming week — designed so they have the weekend to think on it and walk into Monday with priorities locked.

It does NOT pull from Plaud directly — that's [[meetings-digest]]'s job (twice daily). This skill reads the local JSONL state file populated by `meetings-digest` and synthesizes a focused rollup.

**Critical scope filter:** only meeting types where `include_in_weekly_rollup: true` are pulled in. For this client's default config, that means **Kingsway Pharma only**. Church and Personal meetings stay in their respective folders/properties but never roll up — that's intentional, per the client's request.

## Operating mode

Runs **Friday at 5:30 PM** local time, scheduled 30 minutes after the Friday 5:00 PM `meetings-digest` run so the latest day's items are guaranteed in the JSONL before synthesis. Also invokable manually.

## When this skill fires

- `/weekly-rollup` — synthesize the week ending now for all meeting types flagged for rollup
- `/weekly-rollup --week 2026-W21` — explicit ISO week (Mon–Sun)
- `/weekly-rollup --since 2026-05-18 --until 2026-05-22` — explicit range
- `/weekly-rollup --meeting-type "Kingsway Pharma"` — restrict to one specific type
- `/weekly-rollup --preview` — synthesize but DON'T write; return markdown to chat for review
- "What's on my plate next week for Kingsway Pharma?"

## What it produces

A single document (Word `.docx` on Windows, Notion page on Mac) titled `<Meeting Type> — Weekly Rollup, Week of <YYYY-MM-DD>`. If multiple meeting types are flagged for rollup, one document per type. Sections, in order:

1. **🎯 Next week's focus** — Claude's pick of 3–5 highest-leverage items to tackle Monday. One-line "Why" each.
2. **🔴 High priority (open)** — items added this week with `Priority: High`
3. **By context** — items added this week, grouped by `context` (Sales / Operations / Strategic / etc.)
4. **🔁 Carry-overs from prior weeks** — items added before this week that are still in the active backlog (within the last 30 days). Aging markers: `[Open N days]`, `⚠️` after 14, `🚨` after 21.
5. **🧠 Decisions made** — synthesized from the week's recordings
6. **❓ Open questions still unresolved** — synthesized from the week's recordings
7. **📊 Themes** — 2–3 patterns Claude noticed across the week's meetings (recurring names, repeated commitments, etc.)
8. **Stats** — N meetings processed, M new action items, X carry-overs

## Pre-flight

1. **Read the config** at `~/.claude/skills/meetings-digest/config.json` (same config as `meetings-digest`).

2. **Determine which meeting types to roll up.** Filter `meeting_routing.types` to entries with `include_in_weekly_rollup: true`. For this client's defaults, that's exactly `["Kingsway Pharma"]`.

3. **Resolve the week.**
   - Default: the just-completed work week — `Monday 00:00` of the current ISO week through the moment the skill fires (Friday 17:30). Captures Mon → Fri.
   - `--week YYYY-WWW` → explicit ISO week (Mon–Sun)
   - `--since` + `--until` → explicit range

## Pull the substrate

For each meeting type to roll up:

1. Call `state_store.read_items(since, until, meeting_types=[mtype])` to fetch the week's action items as a list of dicts.
2. Call `state_store.read_items(meeting_types=[mtype], created_before=since)` and filter to items still in the active backlog (within `weekly_rollup.carry_over_window_days`, default 30) — these are carry-overs.

State store is read-only here. The skill does NOT modify the JSONL.

## Synthesize

Apply the discipline below per meeting type. Stay tight; the operator opens this Friday evening for weekend thinking — wants to skim in 2 minutes.

### Next week's focus (Claude's pick)

Pick 3–5 highest-leverage items. Criteria:
- High priority + already overdue or due next week → almost always include
- Items appearing as themes across multiple meetings → escalate
- Items blocking other items → upstream gets focus
- Quick wins (low effort, high momentum) → include if otherwise low priority

For each: 1 line reasoning, "Pick because…"

Opinionated. NOT a re-list. If only 1 item is genuinely high-leverage, pick 1.

### By context

Group open items added this week under their `context` value, sorted by Priority (High→Medium→Low) then Due (earliest first).

### Carry-overs from prior weeks

For each carry-over, calculate `days_open = today - source_recorded_at`. Sort oldest-first. Apply aging markers (`⚠️` at warn_days, `🚨` at loud_days from config).

### Themes

Look across the week's meeting sources and action items. Find 2–3 patterns:

- A person/company name appearing in 3+ recordings
- A repeated commitment ("send the proposal", "schedule the call") pushed 2+ weeks
- A context getting disproportionate items (workload spike vs. focus drift?)
- A decision discussed in multiple meetings but never resolved

Each theme: 2–3 sentences. Name the pattern, name the implication, name a next step.

If nothing genuinely recurs: write "No strong recurring themes this week." That's fine.

## Write the rollup

Branch on `destination.type`:

### Mode A: `word_onedrive` (Windows default)

Build a JSON synthesis matching `rollup_docx_writer.py` input shape:

```json
{
  "meeting_type": "Kingsway Pharma",
  "week_start": "2026-05-18",
  "week_end": "2026-05-22",
  "generated_at": "2026-05-22T17:30:00-04:00",
  "stats": {"meetings_processed": 7, "action_items_new": 23, "carry_overs_open": 5, "themes_detected": 3},
  "focus_picks":    [ {action, owner, reason, due, source_recording}, ... ],
  "high_priority":  [ {action, owner, due, source_recording_title, ...}, ... ],
  "by_context":     {"Sales": [...], "Operations": [...]},
  "carry_overs":    [ {action, days_open, owner, source_recording_title}, ... ],
  "decisions":      [ {what, why, source_recording_title}, ... ],
  "open_questions": [ {question, raised_by, source_recording_title}, ... ],
  "themes":         [ {title, body}, ... ]
}
```

Write to tempfile, invoke:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/rollup_docx_writer.py --input /tmp/rollup-<mtype>-<week>.json
```

The script writes to `{onedrive_folder}/Plaud Meetings/{meeting_type}/_weekly/<YYYY-WW> <meeting_type> Weekly Rollup.docx`. Prints the resolved path on success.

### Mode B: `notion` (Mac default)

Build a markdown body covering all the sections above (use the same structure but render to plain markdown). Save to a tempfile, then create a Notion child page under the configured parent page:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/notion-page-write.py \
  --title "Kingsway Pharma — Weekly Rollup, Week of 2026-05-18" \
  --body /tmp/rollup-body.md
```

The page lands as a child of `destination.notion_parent_page_id`. If a page with the same title already exists, the helper creates a new one with a `(re-run HH:MM)` suffix — operator deletes the dupe.

### Mode C: `folder` (universal fallback)

Write to `{destination.folder}/_weekly/<YYYY>-W<WW>-<meeting-type-slug>.md`. Append a new `## Re-run at YYYY-MM-DD HH:MM` section if the file already exists.

## Report to the user

```
✓ Weekly Rollup — Week of 2026-05-18 → 2026-05-22

Meeting types rolled up: Kingsway Pharma
(Skipped per config: Church, Personal — include_in_weekly_rollup=false)

Period:        Mon 2026-05-18 → Fri 2026-05-22
Items:         N new action items this week (Kingsway Pharma only)
Carry-overs:   M items from prior weeks still in the active backlog
Overdue:       X items past due

Top focus next week:
  1. {first pick}
  2. {second pick}
  3. {third pick}

Themes:
  • {first theme}
  • {second theme}

Rollup written to: {path or Notion URL}
```

Do not paste the full rollup into chat.

## Anti-patterns

- **Do not pull from Plaud directly.** Work off the JSONL state file populated by `meetings-digest`. If JSONL is stale (e.g., the Friday 5pm meetings-digest run failed), surface the staleness (`Last meetings-digest entry: <date>`) but don't try to fix it from here — the operator decides.
- **Do not modify existing action items.** Read-only against the JSONL.
- **Do not roll up meeting types where `include_in_weekly_rollup: false`.** Church and Personal stay in their own folders/properties; the rollup is strictly for Kingsway Pharma (or whatever types the operator has flagged true).
- **Do not invent themes.** A theme requires 2+ datapoints. If there's no real pattern, the section says so.
- **Do not double-count.** A carry-over from last week shouldn't also appear in "new items added this week."
- **Do not pad focus picks.** If only 1 item is genuinely high-leverage, only pick 1.

## Edge cases

- **Empty week (no items in JSONL for the configured meeting types)** — write the rollup anyway with sections noting "No new items this week." Carry-overs may still populate.
- **`destination.notion_parent_page_id` not set** (Notion mode) — surface the error; tell operator to re-run install.
- **OneDrive folder unavailable** (Windows mode) — surface error; tell operator OneDrive must be signed in + sync'd.
- **No meeting types flagged for rollup** — surface a warning ("No meeting types have include_in_weekly_rollup=true; rollup has nothing to produce. Edit config.json to enable.")
- **Multiple meeting types flagged for rollup** — produce one rollup document per type. Run the synthesis loop once per type.

## Config schema additions (relative to meetings-digest)

```json
{
  "weekly_rollup": {
    "enabled": true,
    "include_focus_picks": true,
    "max_focus_picks": 5,
    "carry_over_warn_days": 14,
    "carry_over_loud_days": 21,
    "carry_over_window_days": 30
  }
}
```

Schedule entry (from meetings-digest config) for Friday rollup:

```json
"schedule": {
  "rollup": {"day_of_week": 5, "hour": 17, "minute": 30}
}
```

`day_of_week: 5` = Friday. Fires 30 minutes after the Friday 5pm `meetings-digest` run so the latest day's items are guaranteed in the JSONL.
