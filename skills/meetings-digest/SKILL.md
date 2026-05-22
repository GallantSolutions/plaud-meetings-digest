---
name: meetings-digest
description: Pull Plaud recordings, route each one to the correct meeting-type folder based on the spoken opening line (e.g., "Kingsway Pharma with John Smith"), extract structured action items / decisions / open questions, and write the output to the configured destination — Word documents in OneDrive on Windows, Notion database rows on Mac. Also append items to a local JSONL state file so the weekly-rollup skill can synthesize cross-meeting summaries.
---

# meetings-digest

This skill pulls recordings from Plaud AI via the Plaud MCP server, re-extracts structured information from the transcripts (NOT trusting Plaud's built-in AI summary), routes each recording to the correct meeting-type folder, and writes the output to the configured destination.

**Destination branches by OS** (picked at install time, written into `config.json`):

- **Windows** → Word `.docx` files written to OneDrive folders (per-meeting-type subfolders, with meeting routing)
- **Mac** → Notion database rows (one row per action item), grouped by meeting type via the `Context` property

Same skill, same routing logic, same JSONL state file — only the WRITE step branches.

## Operating mode

This skill runs **twice daily** by default — at 12:30 PM (lunch) and 5:00 PM (EOD) local time — plus any manual invocations. Dedup state at `~/.claude/skills/meetings-digest/state/processed-file-ids.json` ensures meetings aren't double-processed across runs.

The Friday 5:00 PM run is chained: this skill fires first; the [[weekly-rollup]] skill fires at 5:30 PM (configured in `schedule.ps1` on Windows, `schedule.sh` on Mac) to synthesize the week's Kingsway Pharma items into a rollup `.docx`.

## When this skill fires

- `/meetings-digest` — process new recordings since the last run (default window: 3 days, dedup-filtered)
- `/meetings-digest --days 14` — override window
- `/meetings-digest --since 2026-05-19` — explicit start
- `/meetings-digest --force` — ignore dedup, re-process everything in window
- "Pull my new Plaud meetings"

## Pre-flight

1. **Read the config** at `~/.claude/skills/meetings-digest/config.json`:
   - `destination.type` — `word_onedrive` (Windows default) | `notion` (Mac default) | `folder` (universal fallback, plain markdown)
   - `destination.onedrive_folder` — base OneDrive path (word_onedrive mode only, e.g., `C:\Users\client\OneDrive`)
   - `destination.notion_api_key` / `destination.notion_database_id` / `destination.notion_parent_page_id` — Notion mode only
   - `destination.folder` — markdown folder (folder mode only)
   - `meeting_routing.types` — list of `{keyword, folder, include_in_weekly_rollup}` entries
   - `meeting_routing.fallback_folder` — where unrouted recordings go (default `Uncategorized`)
   - `meeting_routing.scan_first_seconds` — how much of the transcript to scan for routing (default 30)
   - `window_days` — default lookback window (default 3 — covers weekend + missed runs)
   - `contexts` — operator-defined context tags for action items
   - `timezone` — IANA timezone
   - `dedup.enabled`, `dedup.retention_days`

2. **Verify Plaud MCP is connected.** Tool calls available under the `plaud` namespace: `list_files`, `get_file`, `get_transcript`, `get_note`. If unavailable, ask the user to re-run install (which re-authorizes Plaud).

3. **Load dedup state** via `state_store.load_dedup()`. The skill calls the helper from the shell (`python3 -c "from state_store import load_dedup; ..."`) or invokes the diagnostic CLI directly.

4. **Resolve the time window.** Default: last `window_days` ending now.

## Pull recordings

Call `list_files` with the resolved date range. Filter to recordings only. Sort chronologically.

**Apply dedup filter.** Remove any recording whose `file_id` is in the dedup state — unless `--force`. If everything is deduped out, exit cleanly with `No new recordings since last run.`

For each remaining recording:
1. Call `get_transcript` to fetch the full transcript with speaker labels + timestamps.
2. Read recording metadata: title, duration, recorded_at, speakers.

**Do NOT call `get_note`.** We re-extract from the transcript ourselves.

If a recording has no transcript yet (still processing), skip it AND do not mark it processed in dedup state (so next run picks it up once Plaud finishes).

## Route by meeting type

For each transcript, identify the meeting type by scanning the first `scan_first_seconds` of speech (default 30 sec — typically the first ~500–800 characters of the transcript).

**Algorithm:**

1. Take the first 30 seconds of transcript text. Strip speaker labels and timestamps; keep just the spoken words.
2. For each `meeting_routing.types` entry, in order:
   - Substring search for `entry.keyword` (case-insensitive) in the opening text.
   - First match wins. Set `meeting_type = entry.folder`, `include_in_rollup = entry.include_in_weekly_rollup`.
3. If no keyword matches, set `meeting_type = meeting_routing.fallback_folder` (default `Uncategorized`) and `include_in_rollup = false`.

**Example for this client's config:**

```json
"meeting_routing": {
  "scan_first_seconds": 30,
  "types": [
    {"keyword": "Kingsway Pharma", "folder": "Kingsway Pharma", "include_in_weekly_rollup": true},
    {"keyword": "Church",          "folder": "Church",          "include_in_weekly_rollup": false},
    {"keyword": "Personal",        "folder": "Personal",        "include_in_weekly_rollup": false}
  ],
  "fallback_folder": "Uncategorized"
}
```

Recording opens with "Kingsway Pharma meeting with John Smith…" → routes to `Kingsway Pharma/` AND will appear in the Friday rollup. Recording opens with "Sunday morning church reflection…" → routes to `Church/` and stays out of the rollup.

## Extract structured information

For each transcript, identify these categories. Stay disciplined — only include items the transcript actually supports.

### Action items

A line counts as an action item if it has BOTH:
- An imperative or commitment ("we need to," "I'll send," "let's get," "follow up on…", "by end of week," "before our next call")
- AND an implied or explicit owner (specific person named, or "I" / "we" where the speaker is identifiable)

For each, extract: **owner**, **action** (5–15 words), **due** (resolved to absolute date if mentioned), **priority** (High/Medium/Low — inferred from urgency cues), **context** (from `contexts` list in config — best fit; ask only if no contexts make sense; default to first context), **source_timestamp** (HH:MM:SS into recording).

Skip:
- Discussion-only mentions
- Hypotheticals
- Past actions
- Soft asks ("would be nice")

### Decisions made

Things explicitly decided. Look for "OK, let's go with…", "Decided:", "Final answer:", "We're going to…"

Each: **what**, **why** (if stated), **source_timestamp**.

### Open questions

Questions raised but not resolved. "What about…", "I don't know…", "should we…", "we need to figure out…"

Each: **question**, **raised_by**, **source_timestamp**.

### Notable quotes (optional, max 3–5 per meeting)

Direct quotes worth preserving. Each: **quote**, **speaker**, **source_timestamp**.

## Write to the configured destination

Branch on `destination.type`:

### Mode A: `word_onedrive` (Windows default)

For each processed recording, build a JSON object matching the `docx_writer.py` input shape:

```json
{
  "meeting_type": "Kingsway Pharma",
  "recording_title": "Kingsway Pharma w/ John Smith",
  "recorded_at": "2026-05-22T14:30:00-04:00",
  "duration_minutes": 47.3,
  "speakers": ["Garrett", "John Smith"],
  "source_file_id": "rec_abc123",
  "transcript_excerpt": "...first 500 chars (for audit trail)...",
  "action_items": [...],
  "decisions": [...],
  "open_questions": [...],
  "notable_quotes": [...]
}
```

Write it to a tempfile, then invoke:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/docx_writer.py --input /tmp/meeting-<file_id>.json
```

The script computes the output path automatically: `{onedrive_folder}/Plaud Meetings/{meeting_type}/<YYYY-MM-DD HHMM> <title>.docx`. Prints the resolved path on success.

### Mode B: `notion` (Mac default)

**v2.0.0 shape: one Notion database row per MEETING (not per action item).** The full recap goes in the page body of that row. Action items render as Notion checkboxes (`to_do` blocks) so the client can tick them off as they complete them.

Build a JSON object matching the SAME shape `docx_writer.py` accepts (one meeting per invocation):

```json
{
  "meeting_type": "Kingsway Pharma",
  "recording_title": "Kingsway Pharma w/ John Smith",
  "recorded_at": "2026-05-22T14:30:00-04:00",
  "duration_minutes": 47.3,
  "speakers": ["Garrett", "John Smith"],
  "source_file_id": "rec_abc123",
  "transcript_excerpt": "...",
  "action_items": [...],
  "decisions": [...],
  "open_questions": [...],
  "notable_quotes": [...]
}
```

Write to a tempfile and invoke:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/notion-write.py --input /tmp/meeting-<file_id>.json
```

The helper creates one row in the "Plaud Meetings" database with these properties: `Title`, `Meeting Type` (the routed folder name), `Date`, `Duration`, `Speakers`, `Action Items` (count), `Decisions` (count), `Open Questions` (count), `Status` (defaults to "New"), `Source File ID`. The page body of the row contains:

- Metadata header (date · duration · speakers · meeting type)
- **Action items** section (each item is a `to_do` block — interactive checkbox)
- **Decisions made** section (bulleted)
- **Open questions** section (bulleted)
- **Notable quotes** section (quote blocks)
- Footer with generation timestamp + Plaud file ID

The client can filter the DB by `Meeting Type = Kingsway Pharma` to see Kingsway recaps; or sort by `Date`; or filter `Status = New` to find unreviewed meetings. The weekly rollup queries the LOCAL state JSONL (not the Notion DB) so synthesis stays fast and is destination-agnostic.

### Mode C: `folder` (universal fallback)

Append to `{destination.folder}/{YYYY}-W{WW}.md` under sections for each meeting type. Same shape as previously documented.

## Append to state JSONL

After the `.docx` write succeeds, append each action item to `~/.claude/skills/meetings-digest/state/action-items.jsonl` via the `state_store.append_items()` helper. Each row carries:

```json
{
  "action": "...",
  "owner": "...",
  "context": "...",
  "due": "...",
  "priority": "...",
  "meeting_type": "Kingsway Pharma",
  "source_file_id": "rec_abc123",
  "source_recording_title": "...",
  "source_recorded_at": "...",
  "source_timestamp": "...",
  "extracted_at": "<UTC now ISO>"
}
```

The weekly-rollup skill reads this JSONL filtered by `meeting_type` to build the Friday rollup.

## Record dedup state

After both the `.docx` and JSONL writes succeed for a recording, call `state_store.mark_processed([file_id])` to add it to the dedup state. Prune entries older than `dedup.retention_days` (default 90).

If either write FAILED, do NOT mark processed — next run will retry.

## Report to the user

```
✓ Plaud Meetings Digest — YYYY-MM-DD HH:MM (source: lunch|eod|manual)

Window:      last N days
Found:       M recordings in window
Skipped:     K already processed (dedup); J still processing (no transcript yet)
Processed:   P new recordings (total NN min)

Routed:
  Kingsway Pharma:   X recordings → "{OneDrive}/Plaud Meetings/Kingsway Pharma/"
  Church:            Y recordings → "{OneDrive}/Plaud Meetings/Church/"
  Personal:          Z recordings → "{OneDrive}/Plaud Meetings/Personal/"
  Uncategorized:     W recordings (opening line had no recognized keyword)

Extracted:   X action items, Y decisions, Z open questions
```

If nothing was new: `No new recordings since last run. (M already processed in the last N-day window.)`

Do NOT paste the full digest into the chat — it belongs in the Word docs.

## Anti-patterns

- **Do not trust Plaud's `get_note`** — re-extract from the transcript.
- **Do not invent action items** — if the transcript doesn't support a commitment, leave it out.
- **Do not skip routing** — every recording goes to a folder, even if it's `Uncategorized`. Surface uncategorized counts in the report so the operator notices when the client forgets to say the meeting type.
- **Do not split a single recording across folders** — meeting type is determined ONCE per recording from the opening line; pick first match and apply consistently.
- **Do not write the .docx before extraction completes** — if extraction fails, no partial .docx should land.
- **Do not modify past .docx files** — each recording produces one .docx, immutable. Re-extraction (via `--force`) creates a NEW .docx with the same name plus a re-run suffix.
- **Do not mark a recording processed unless BOTH writes succeed** (`.docx` + JSONL append). Otherwise next run will pick it up.

## Edge cases

- **No recordings in window** → print "No Plaud recordings found in the {N}-day window" and exit; don't touch state.
- **All recordings already processed** → print "No new recordings since last run" and exit.
- **Plaud OAuth expired** → surface error; tell user to re-run install (which re-OAuths).
- **OneDrive folder missing / not yet synced** → surface error with path; tell user OneDrive needs to be installed + signed in.
- **Routing keyword matches multiple types** → first match in the `types` list wins. Operator orders the list with most specific first.
- **`--force` flag** → bypass dedup; re-extract everything in window. Creates new .docx files (won't overwrite the originals — appends a `(re-run HHMM)` suffix to the filename). Dedup state is still updated.
- **Dedup state corrupted** → `state_store` backs it up as `.bak` and starts fresh with a warning.
- **Non-English recording** → use the transcript as source of truth; extract in whatever language it's in.

## Config schema (reference)

```json
{
  "version": "2.0.0",
  "installed_at": "ISO-8601 timestamp",
  "platform": "windows | macos",
  "destination": {
    "type": "word_onedrive | notion | folder",
    "onedrive_folder": "C:\\Users\\client\\OneDrive (word_onedrive only)",
    "notion_api_key":          "secret_... (notion only)",
    "notion_database_id":      "32-char hex (notion only)",
    "notion_parent_page_id":   "32-char hex (notion only — for weekly rollup pages)",
    "folder":                  "/path/to/folder (folder only)"
  },
  "meeting_routing": {
    "enabled": true,
    "scan_first_seconds": 30,
    "types": [
      {"keyword": "Kingsway Pharma", "folder": "Kingsway Pharma", "include_in_weekly_rollup": true},
      {"keyword": "Church",          "folder": "Church",          "include_in_weekly_rollup": false},
      {"keyword": "Personal",        "folder": "Personal",        "include_in_weekly_rollup": false}
    ],
    "fallback_folder": "Uncategorized"
  },
  "window_days": 3,
  "timezone": "America/New_York",
  "contexts": ["Sales", "Operations", "Strategic", "Compliance", "Personal"],
  "default_owner": "me",
  "skip_recordings_under_minutes": 2,
  "dedup": {
    "enabled": true,
    "retention_days": 90
  },
  "schedule": {
    "lunch":  {"hour": 12, "minute": 30},
    "eod":    {"hour": 17, "minute":  0},
    "rollup": {"day_of_week": 5, "hour": 17, "minute": 30}
  }
}
```
