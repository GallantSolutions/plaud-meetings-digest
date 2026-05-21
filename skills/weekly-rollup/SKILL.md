---
name: weekly-rollup
description: Synthesize the just-completed work week's action items (already extracted by the meetings-digest skill that runs immediately before this one as part of the Friday-5pm chain) into a single rollup page so the user can think on it over the weekend and walk into Monday ready to act. Includes high-priority items, carry-overs from prior weeks, decisions made, themes noticed across meetings, and a "next week's focus" block.
---

# weekly-rollup

This skill produces the **weekly action-items rollup** the user receives Friday evening — designed so they have the weekend to think on it and walk into Monday with priorities locked. It does NOT pull from Plaud directly — that's [[meetings-digest]]'s job (it runs immediately before this skill in the Friday-5pm chain, pulling the week's recordings and writing raw action items as rows in the Notion DB). This skill QUERIES that DB, synthesizes, and writes a single rollup page.

## When this skill fires

Triggers:

- `/weekly-rollup` — synthesize the past week (Mon→Sun) and write the rollup page
- `/weekly-rollup --week 2026-W21` — explicit week
- `/weekly-rollup --since 2026-05-14 --until 2026-05-20` — explicit date range
- `/weekly-rollup --preview` — synthesize but DON'T write to Notion (returns the markdown to chat for review)
- "Give me my weekly rollup"
- "What's on my plate this week?"
- "Synthesize last week's action items"

## What it produces

A single Notion page (or markdown file in folder mode) titled `Week of YYYY-MM-DD — Action Items Rollup` covering the just-completed work week (Monday → Friday of the week the skill fires in). Sections, in order:

1. **🎯 Next week's focus** — Claude's pick of the 3–5 highest-leverage items to tackle Monday morning. Reasoning shown in 1 line each. These are what the user thinks about over the weekend.
2. **🔴 High priority (open)** — every action item with `Priority: High` and `Status: Open` from this work week
3. **By context** — all open items added this work week, grouped by Context (RANK / Client work / etc.)
4. **🔁 Carry-overs from prior weeks** — items with `Status: Open` and `Created: >7 days ago` that are still hanging. These get loud — if something has been open for 3+ weeks, it deserves a decision.
5. **⚠️ Overdue** — items with `Due` in the past and `Status: Open`. Sorted oldest-first.
6. **✅ Closed this week** — items moved to `Done` this work week (a small victory log)
7. **🧠 Decisions made** — synthesized from meetings-digest decisions during the week
8. **❓ Open questions still unresolved** — pulled from meetings-digest open questions
9. **📊 Themes** — Claude looks across all the week's meetings and flags 2–3 recurring threads (e.g., "Acme follow-up showed up in 4 meetings — that's a real pattern, escalate?")
10. **Stats** — N meetings processed, M new action items, X closed, Y carry-over

## Pre-flight

1. **Read the config** at `~/.claude/skills/meetings-digest/config.json`. Same config as meetings-digest. Specifically need:
   - `destination.type` — folder | notion
   - `destination.notion_api_key` + `destination.notion_database_id` + `destination.notion_parent_page_id`
   - `destination.folder` (if folder mode)
   - `timezone` — for week boundary

2. **Resolve the week.**
   - Default: the just-completed work week in the configured timezone — `Monday 00:00` through the moment the skill fires (Friday 17:00). So the Friday-evening run captures Mon → Fri of the current week.
   - `--week YYYY-WWW` → explicit ISO week (Mon–Sun)
   - `--since` + `--until` → explicit range
   - Print the resolved range before doing anything.

## Query the substrate

Call the Notion query helper:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/notion-query.py \
  --since YYYY-MM-DD --until YYYY-MM-DD --output /tmp/week-items.json
```

This returns a JSON array of every action item in the DB with `Source date` (when the source meeting happened) in the date range. Each item includes: action text, context, owner, due, status, priority, source recording, source date, week tag.

Also pull two adjacent slices:

- **Carry-overs:** every item with `Status=Open` and `Created < since` (added before this week but still open). Use a second `notion-query.py` call with `--status Open --created-before YYYY-MM-DD`.
- **Closed this week:** every item with `Status=Done` and `Last edited >= since`. (If Notion API doesn't expose last-edited filtering cheaply, skip this section or estimate from Created date as a proxy.)

For decisions and open-questions sources: meetings-digest writes those as Notion pages (one per run, titled "YYYY-MM-DD — Run {friday-rollup|manual}"). Query for child pages of the parent page with a title prefix matching the date range, then fetch their content.

## Synthesize

For each section, apply the discipline below. Stay tight; the operator opens this Monday morning and wants to skim it in 2 minutes, not 20.

### This week's focus (Claude's pick)

Pick 3–5 items that are the highest-leverage to actually do this week. Criteria:

- High priority + already overdue or due this week → almost always include
- Items that show up as themes across multiple meetings → escalate
- Items blocking other items (if a downstream item's `Source` mentions waiting on an upstream item) → upstream gets focus
- Quick wins (small effort, big momentum) → include if priority is otherwise low

For each pick, give 1 line of reasoning: "Pick because…"

NOT a re-list of everything. NOT items the operator already closed. The focus block is opinionated.

### By context

Just group the open items added in the last 7 days under their Context value, sorted by Priority (High→Medium→Low) then Due (earliest first). One bullet per item: `- {action} — {owner}, due {date or "no deadline"} _(from "{Source recording}")_`

### Carry-overs from prior weeks

For each carry-over, show how long it's been open:

`- [Open 14 days] {action} — {context}, {owner}. _(from "{Source recording}")_`

Sort oldest-first. After 14 days, append `⚠️` to the line. After 21 days, append `🚨`. The goal is to make stale items visually loud so the operator notices.

### Themes

Look across the week's meeting sources and action items. Find 2–3 patterns:

- A person/company name that appeared in 3+ meetings
- An action ("send the proposal", "schedule the call") that's been pushed 2+ weeks
- A context that's getting a lot of items vs. others (signal of focus drift OR genuine workload spike)
- A decision that was discussed in multiple meetings but never made

Each theme: 2–3 sentences. Naming the pattern, naming the implication, naming a recommended next step.

## Write the rollup

Branch on `destination.type`:

### Notion destination

Use the page-writer helper:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/notion-page-write.py \
  --parent-page <notion_parent_page_id> \
  --title "Week of YYYY-MM-DD — Action Items Rollup" \
  --body /tmp/rollup-body.md
```

The helper creates a child page under the configured parent page, with the markdown body rendered to Notion blocks.

If a page with the same title already exists under the parent, **don't overwrite**. Create a new page with a `(re-run HH:MM)` suffix so both versions are visible. The operator can delete the older one.

### Folder destination

Write to `{destination.folder}/_weekly/{YYYY}-W{WW}.md`. Create the `_weekly/` subdirectory if missing.

If the file exists, append a new `## Re-run at HH:MM` section — never overwrite.

## Report to the user

```
✓ Weekly Rollup — Week of YYYY-MM-DD → YYYY-MM-DD

Period:      Mon YYYY-MM-DD → Sun YYYY-MM-DD
Items:       N new action items this week
Carry-over:  M items still open from prior weeks
Closed:      X items moved to Done this week
Overdue:     Y items past due

Top focus this week:
  1. {first focus pick}
  2. {second focus pick}
  3. {third focus pick}

Themes:
  • {first theme}
  • {second theme}

Rollup page: {Notion URL or file path}
```

Do not paste the full rollup into chat. It belongs in the destination.

## Anti-patterns

- **Do not re-pull from Plaud.** This skill works off what's already in Notion. If meetings-digest hasn't run twice today + over the weekend, the rollup will be missing recent items — surface that gap ("Last meetings-digest run: {time} — N hours stale") but don't try to fix it from here.
- **Do not modify existing action items.** Read-only against the DB rows. The rollup is a NEW page that REFERENCES rows; it doesn't update them.
- **Do not invent themes.** A "theme" requires 2+ datapoints. If you can't find a real pattern, the Themes section is just "No strong recurring themes this week" — and that's fine.
- **Do not double-count.** A carry-over from last week shouldn't also appear in "new items added this week."
- **Do not pad the focus block.** If only 1 item is genuinely high-leverage, only pick 1. Better than 5 picks where 4 are filler.

## Edge cases

- **Empty week (no meetings recorded)** — write the rollup anyway, but contents will be carry-overs + open items only. Note at top: "No meetings recorded this week."
- **Notion query rate-limited** — Notion's API allows 3 req/sec. The helper paginates; if it hits rate limits, sleep + retry. Surface to user if a retry chain fails.
- **Notion parent page deleted** — the rollup write helper will 404. Surface error; tell operator to either restore the page or re-run install.sh to point at a new parent.
- **DB has 1000+ items in the week** — pagination handles this. The synthesis may take longer; show progress per phase.
- **Cross-week boundary at run time** — always use the COMPLETED week (Mon→Sun ending before today). If today IS Monday, that's last week. If today is Sunday, the week is the prior Mon→Sun (don't include today's items in the rollup — they'll show in next week's).

## Config schema additions (relative to meetings-digest)

```json
{
  "destination": {
    "notion_parent_page_id": "32-char hex — same parent that holds the action-items DB"
  },
  "weekly_rollup": {
    "enabled": true,
    "include_focus_picks": true,
    "max_focus_picks": 5,
    "carry_over_warn_days": 14,
    "carry_over_loud_days": 21
  },
  "schedule": {
    "label": "friday-rollup",
    "day_of_week": 5,
    "hour": 17,
    "minute": 0
  }
}
```

`day_of_week: 5` is Friday (launchd convention; Sunday=0, Monday=1, ... Friday=5). Default fires at 17:00 — the scheduled run chains `meetings-digest` (pulls the week's recordings + extracts items) and then this skill (synthesizes the rollup page). The user gets the rollup roughly 5:05–5:15 PM Friday, in time for end-of-day. Operator can shift in `~/Library/LaunchAgents/com.gallant.plaud-meetings-digest.friday-rollup.plist` if a different cadence (e.g., Sunday evening) is preferred.
