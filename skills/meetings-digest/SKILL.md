---
name: meetings-digest
description: Pull Plaud recordings, route each one to the correct meeting-type folder based on the spoken opening line (e.g., "Kingsway Pharma with John Smith"), and write Plaud's native note (summary, action items, key points) 1:1 into a Word document in OneDrive on Windows or a Notion row on Mac. Lightly extracts only the filename metadata (title, attendees) — the actual meeting content comes verbatim from Plaud's get_note().
---

# meetings-digest

This skill pulls recordings from Plaud AI via the Plaud MCP server, calls `get_note()` to fetch Plaud's native structured summary, and writes that summary **1:1** into a Word document in the routed OneDrive folder (or a Notion row on Mac). Plaud's own summary is the source of truth — Claude does NOT re-paraphrase or re-extract action items. Claude's only reasoning role per meeting is (a) routing to the correct bucket via keyword match on the opening 30 seconds of transcript, and (b) generating a short 3-6 word title for the filename.

**Destination branches by OS** (picked at install time, written into `config.json`):

- **Windows** → Word `.docx` files written to OneDrive folders (per-meeting-type subfolders, with meeting routing)
- **Mac** → Notion database rows (one row per action item), grouped by meeting type via the `Context` property

Same skill, same routing logic, same JSONL state file — only the WRITE step branches.

## Operating mode

This skill runs **twice daily** by default — at 11:00 AM (lunch) and 4:00 PM (EOD) local time — plus any manual invocations. Dedup state at `~/.claude/skills/meetings-digest/state/processed-file-ids.json` ensures meetings aren't double-processed across runs.

The Friday 4:00 PM run is chained: this skill fires first; the [[weekly-rollup]] skill fires at 4:30 PM (configured in `schedule.ps1` on Windows, `schedule.sh` on Mac) to synthesize the week's rollup-flagged items into rollup `.docx` files.

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

### Step 0 — Check Playwright staging folder (v2.5.0+)

Before calling MCP `list_files`, check whether `plaud_playwright_runner.py` already populated the staging folder this run.

**Path** — Windows: `%LOCALAPPDATA%\plaud-meetings-digest\.playwright-staging\_manifest.json`. Mac: `~/Library/Application Support/plaud-meetings-digest/.playwright-staging/_manifest.json`.

**If the manifest exists and `manifest.error` is null AND `manifest.results` is non-empty:** Plaud's rich Export-tier Summary has been pre-fetched for each listed `file_id`. For each result, read its `staging_path` file (markdown or .docx) — this content REPLACES the MCP `get_note()` call entirely. Treat the staged content as `plaud_note_markdown` for the downstream write step.

**If the manifest is missing, has an error, or has an empty results list:** fall through to the MCP path described below. The skill must remain MCP-compatible — the staging folder is the preferred fetch surface, not the only one. Log which path was taken per meeting.

After processing each staged file, delete it from the staging folder (or move to `_consumed/`) so a re-run doesn't double-process. The runner clears the folder at the start of each run anyway.

### Step 1 — MCP path (default for clients on `plaud.method = "mcp_only"`, fallback for `auto`)

Call `list_files` with the resolved date range. Filter to recordings only. Sort chronologically.

**Apply dedup filter.** Remove any recording whose `file_id` is in the dedup state — unless `--force`. Skip any `file_id` already handled by the staging step above. If everything is deduped out, exit cleanly with `No new recordings since last run.`

For each remaining recording:
1. Call `get_transcript` to fetch the first ~30 seconds of transcript (just enough for keyword routing — see "Route by meeting type" below).
2. Call `get_note` to fetch Plaud's native structured summary. **This is the meeting content that will be written 1:1 into the docx.** Capture the response as `plaud_note_markdown` (it's already markdown; do not paraphrase, re-extract, or transform it).
3. Read recording metadata: title, duration, recorded_at, speakers.

If a recording has no transcript yet (still processing), skip it AND do not mark it processed in dedup state (so next run picks it up once Plaud finishes). Same applies if `get_note` returns empty / not-yet-summarized.

### v2.5.0 fetch-source discipline

- The Playwright-staged path delivers Plaud's Export-tier multi-section analytical Summary (the same artifact Plaud's web Export button produces). It is richer than MCP `get_note` and is preferred when available.
- The MCP path delivers the basic transcript+summary tier. It's always available as long as Plaud MCP is connected; it's the floor, not the ceiling.
- The downstream write step (`docx_writer.write_doc`) treats both inputs identically — it just renders `plaud_note_markdown` into a branded Word doc. Nothing downstream changes based on source.
- Per-meeting logging MUST record which path was used. JSONL row gets a `fetch_source` field: `"playwright"` or `"mcp"`. This is how the operator can later quantify staging-path coverage.

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
    {"keyword": "Kingsway Pharma", "folder": "Kingsway Pharma", "filename_prefix": "KP", "include_in_weekly_rollup": true},
    {"keyword": "Church",          "folder": "Church",          "filename_prefix": "CH", "include_in_weekly_rollup": false},
    {"keyword": "Personal",        "folder": "Personal",        "filename_prefix": "P",  "include_in_weekly_rollup": false}
  ],
  "fallback_folder": "Uncategorized",
  "fallback_filename_prefix": "UN"
}
```

Recording opens with "Kingsway Pharma meeting with John Smith…" → routes to `Kingsway Pharma/` AND will appear in the Friday rollup. Recording opens with "Sunday morning church reflection…" → routes to `Church/` and stays out of the rollup.

## Extract minimum metadata for filename + routing

In v2.3.0 the meeting BODY comes from Plaud's `get_note()` verbatim. Claude only generates the small handful of fields needed for filename construction + routing.

### Meeting title (the filename component)

**A short, operator-meaningful 3-6 word summary of what the meeting was ABOUT.** This is what shows up in the filename (e.g., `KP.Q3 Plans (John Smith).docx` — the title is `Q3 Plans`). The operator needs to scan a OneDrive folder and instantly remember which meeting was which.

Good examples:
- `Q3 Plans`
- `Compounding Tech Demo`
- `Pricing Pushback Conversation`
- `Pharma Wholesaler Rollout`
- `Sermon on Patience`
- `Dentist Reminder`

Bad examples (do NOT produce these):
- `Meeting with John Smith` ❌ — attendees go in their own field; don't repeat them in the title
- `Kingsway Pharma Q3 Plans` ❌ — meeting type is already encoded in the filename prefix and the folder; don't repeat it
- `A discussion about the various aspects of the upcoming Q3 quarterly planning cycle` ❌ — too long; trim aggressively to 3-6 words
- `Meeting` ❌ — useless; extract the actual topic

Set this as `recording_title` in the JSON input to docx_writer.py. If the transcript is too thin to support a title, use the first concrete noun phrase that appears in the first minute (e.g., "Q3 Plans" mentioned at 0:15 → title = "Q3 Plans"). Last resort: use a 2-word date label like `Morning Note`.

### Attendees (the filename suffix)

**The people the operator met WITH — NOT including the operator themselves.** Extract from the spoken opening line first (most reliable, since the operator intentionally names them: "Kingsway Pharma meeting with John Smith and Sarah Jones..." → attendees = `["John Smith", "Sarah Jones"]`). Fall back to the `speakers` voice-diarization list with the operator's name filtered out.

Rules:
- Use first + last name when both are spoken. First name only is acceptable if last name isn't in the transcript.
- Skip generic labels like "Speaker 1," "Speaker 2," "the team," "everyone."
- Skip the operator (usually "Garrett" or whoever's wearing the Plaud — the operator's name is in `config.default_owner`).
- For Personal recordings (solo notes) attendees can be an empty list `[]` — the filename then just reads `P.Dentist Reminder.docx`.
- For Church reflections (also typically solo) attendees can be empty.

Set this as `attendees` in the JSON input to docx_writer.py — a list of strings.

### Action items, decisions, key points, quotes — DO NOT extract these

Plaud's `get_note()` already returns these as part of its structured summary, formatted to Plaud's conventions. **Pass that summary through verbatim.** Do not re-derive, paraphrase, or split it into your own fields. The weekly-rollup skill still does cross-meeting synthesis on Friday — that's where Claude reasoning lives now. Per-meeting documents are Plaud 1:1.

### State-JSONL note (v2.3.0 behavior)

Because Claude no longer parses individual action items from each meeting, the per-action `action-items.jsonl` lines are derived best-effort by the weekly-rollup skill from the Plaud notes themselves at rollup time. Per-meeting writes still append a single JSONL row recording that the meeting was processed (file_id, meeting_type, recorded_at, title, plaud_note_markdown) so the rollup has substrate to read from.

## Write to the configured destination

Branch on `destination.type`:

### Mode A: `word_onedrive` (Windows default)

For each processed recording, build a JSON object matching the `docx_writer.py` input shape (v2.3.0):

```json
{
  "meeting_type": "Kingsway Pharma",
  "recording_title": "Q3 Plans",
  "attendees": ["John Smith"],
  "recorded_at": "2026-05-22T14:30:00-04:00",
  "duration_minutes": 47.3,
  "speakers": ["Garrett", "John Smith"],
  "source_file_id": "rec_abc123",
  "plaud_note_markdown": "## Summary\n\nReviewed Q3 forecast scenarios...\n\n## Action Items\n\n- John to circulate updated deck by Friday\n- Garrett to confirm Q4 commit numbers Monday\n\n## Key Points\n\n..."
}
```

The `plaud_note_markdown` field is the verbatim markdown response from Plaud's `get_note()` MCP call. docx_writer.py detects this field and renders it 1:1 below the title block — preserving Plaud's section structure (Summary, Action Items, Key Points, etc.) without paraphrasing.

The structured fields (`action_items`, `decisions`, `open_questions`, `notable_quotes`, `recap`) are **no longer required** in v2.3.0+ for per-meeting documents. The writer will accept them if present (for backward compatibility) but will prefer `plaud_note_markdown` if it exists.

Write it to a tempfile, then invoke:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/docx_writer.py --input /tmp/meeting-<file_id>.json
```

The script computes the output path automatically. Layout depends on the meeting type's `weekly_subfolders` flag:

- **`weekly_subfolders: true`** (default for Kingsway Pharma): files get bucketed into a per-week subfolder.
  ```
  OneDrive/Plaud Meetings/Kingsway Pharma/
    KPM.May 25-29, 2026 (Week 22)/
      KPM.Q3 Plans (John Smith).docx
      KPM.Pricing Pushback (Sarah Jones, Mark Lee).docx
      KPR.May 25-29, 2026 (Week 22).docx     ← rollup lives in the same week folder
  ```

- **`weekly_subfolders: false`** (default for Church + Personal): flat layout.
  ```
  OneDrive/Plaud Meetings/Personal/
    PM.Dentist Reminder.docx
  ```

Prefix conventions (the trailing M disambiguates meeting files from any other files the client keeps with the same 2-letter prefix — `KP` could be many things, `KPM` is unambiguously a Plaud meeting):

- `KPM.` — Kingsway Pharma Meeting (per-meeting file)
- `KPR.` — Kingsway Pharma Rollup (weekly synthesis file)
- `CHM.` — Church Meeting
- `PM.`  — Personal Meeting
- `UN.`  — Uncategorized (fallback when routing fails)

Same-title collisions get a date suffix appended automatically. Prints the resolved path on success.

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

- **DO use Plaud's `get_note` verbatim** (v2.3.0+) — Plaud's summary is the source of truth; pass it through unchanged. Do NOT re-paraphrase or split it into your own fields.
- **Do not invent action items** — Plaud's `get_note` already lists them; pass through what's there, do not add or subtract.
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
      {"keyword": "Kingsway Pharma", "folder": "Kingsway Pharma", "filename_prefix": "KPM", "rollup_filename_prefix": "KPR", "weekly_subfolders": true,  "include_in_weekly_rollup": true},
      {"keyword": "Church",          "folder": "Church",          "filename_prefix": "CHM", "rollup_filename_prefix": null, "weekly_subfolders": false, "include_in_weekly_rollup": false},
      {"keyword": "Personal",        "folder": "Personal",        "filename_prefix": "PM",  "rollup_filename_prefix": null, "weekly_subfolders": false, "include_in_weekly_rollup": false}
    ],
    "fallback_folder": "Uncategorized",
    "fallback_filename_prefix": "UN"
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
