---
name: meetings-digest
description: Pull Plaud recordings from a configurable time window, extract structured action items / decisions / open questions grouped by context, and write the digest to the configured destination (folder or Notion).
---

# meetings-digest

This skill pulls recordings from Plaud AI via the Plaud MCP server, re-extracts structured information from the transcripts (NOT trusting Plaud's built-in AI summary), and writes a digest to the configured destination.

## When this skill fires

Triggers on user intent to generate a meeting digest:

- `/meetings-digest` — process new recordings from the last 7 days (the default work-week window)
- `/meetings-digest --days 14` (override window)
- `/meetings-digest --since 2026-05-14` (explicit start)
- `/meetings-digest --force` (ignore dedup, re-process everything in window)
- "Pull my new Plaud meetings"
- "Process this week's calls"

## Operating mode

This skill runs **once a week on Friday at 5:00 PM local time** as the first half of the Friday weekly-rollup chain (immediately followed by `/weekly-rollup` which synthesizes the rollup page). It can also be invoked manually any time. Each run:

1. Pulls all recordings in the `window_days` window (default: 7 days — covers the just-completed work week)
2. **Deduplicates** against the processed-file-ids state file so meetings already extracted in a prior manual run aren't double-written
3. Extracts action items / decisions / open questions from each NEW recording
4. Writes to the configured destination (Notion DB rows or markdown file)
5. Records the newly processed file IDs in the state file

## Pre-flight

1. **Read the config** at `~/.claude/skills/meetings-digest/config.json`. This file holds:
   - `destination.type` — `folder` or `notion`
   - `destination.folder` — output folder path (if folder mode)
   - `destination.notion_api_key` + `destination.notion_database_id` (if notion mode)
   - `window_days` — default lookback window (default: 7 — the just-completed work week)
   - `contexts` — operator-defined context tags
   - `timezone` — IANA timezone (e.g., `America/New_York`)
   - `dedup.enabled` — true by default
   - `dedup.state_file` — path to the processed-file-ids state file
   - `dedup.retention_days` — how long to keep IDs in the state file (default: 90)

2. **Verify Plaud MCP is connected.** Tool calls should be available under the `plaud` namespace: `list_files`, `get_file`, `get_transcript`, `get_note`. If unavailable, ask the user to run `npx -y @plaud-ai/mcp@latest install` and complete OAuth.

3. **Load the dedup state file.** Path is `~/.claude/skills/meetings-digest/.processed-file-ids.json` (or whatever `dedup.state_file` resolves to). Shape:

   ```json
   {
     "processed": [
       { "file_id": "rec_abc123", "processed_at": "2026-05-21T12:30:15Z" },
       { "file_id": "rec_def456", "processed_at": "2026-05-21T17:00:08Z" }
     ]
   }
   ```

   If the file doesn't exist, create it with `{"processed": []}`. Prune entries older than `dedup.retention_days` (default 90) before writing back.

4. **Resolve the time window.** Default: last `window_days` (= 7) ending now. If the user gave `--days N` or `--since YYYY-MM-DD`, honor that. For the Friday-5pm scheduled run, this naturally captures Monday → Friday of the current work week.

## Pull recordings

Call `list_files` with the resolved date range. Filter to recordings only (not other file types). Sort chronologically.

**Apply dedup filter.** Remove any recording whose `file_id` is in the dedup state file's `processed` list — UNLESS the user passed `--force`. If everything is deduped out, exit cleanly with `No new recordings since last run. (N already processed in window.)` and skip the rest.

For each REMAINING recording:
1. Call `get_transcript` to fetch the full text with speaker labels + timestamps.
2. Note the recording metadata: title, duration, recorded_at, speaker count.

**Do NOT call `get_note`.** Plaud's built-in AI summary is what we're replacing. Pull the transcript and re-extract everything ourselves.

If a recording has no transcript yet (still processing), skip it AND do not add it to the dedup state (so the next run picks it up once Plaud finishes processing). Note in the digest under "Skipped: still processing."

## Extract structured information

For each transcript, identify these four categories. Stay disciplined — only include items the transcript actually supports.

### Action items

A line counts as an action item if it has BOTH:
- An imperative or commitment ("we need to," "I'll send," "let's get," "follow up on…," "by end of week," "before our next call")
- AND an implied or explicit owner (specific person named, or "I" / "we" where the speaker is identifiable)

For each action item, extract:
- **Owner** — who's responsible. Use the speaker's name if "I'll do X." Use the named person if "Sarah, can you…" If unclear, mark as `owner: unclear` and note in the digest.
- **Action** — the imperative in 5–15 words.
- **Due** — explicit date if mentioned ("by Friday," "next week," "end of month") resolved to an absolute date. Otherwise null.
- **Source** — recording title + timestamp where the commitment was made.
- **Context** — which `contexts` bucket from config this belongs to. If unclear, ask before assigning to a default.

Skip these (NOT action items):
- Discussion-only mentions ("we should think about X" with no commitment)
- Hypotheticals ("if we did X, then Y")
- Past actions ("we already shipped Y")
- Soft asks ("would be nice to have")

### Decisions made

Things explicitly decided in the meeting (vs. discussed but unresolved). Look for phrases like "OK, let's go with…", "Decided: …", "Final answer: …", "We're going to…"

For each decision:
- **What** — the decision in one sentence
- **Why** — rationale if stated
- **Affects** — which project/context
- **Source** — recording + timestamp

### Open questions raised

Questions that came up but weren't resolved. Phrased as "what about…", "I don't know…", "should we…", "we need to figure out…"

For each:
- **Question** — the question in one sentence
- **Raised by** — who asked it
- **Context** — which project/area
- **Source** — recording + timestamp

### Notable quotes (optional)

Direct quotes worth preserving — strong opinions, important context, surprising statements. Limit to 3–5 per digest.

## Write the digest

Branch on `destination.type`:

### Folder destination

Write to `{destination.folder}/{YYYY}-W{WW}.md` — one file per ISO week (since the scheduled run is weekly on Fridays). If a file already exists for this week (manual run earlier in the week), **append** a new section dated with the current run timestamp under a `## Run at YYYY-MM-DD HH:MM` heading — never overwrite. Past weeks' files are immutable.

Format:

```markdown
# Week of YYYY-MM-DD — Meeting Digest

## Run at YYYY-MM-DD HH:MM ({source: friday-rollup | manual})

_Generated YYYY-MM-DD HH:MM by Plaud Meetings Digest._

## Sources
- YYYY-MM-DD — "Recording title" (NN min, M speakers)
- YYYY-MM-DD — "Recording title" (NN min, M speakers)

## Action items by context

### {Context A}
- [ ] {Action} — {owner}, due {date or "no deadline"} _(from "Recording", HH:MM)_
- [ ] ...

### {Context B}
- [ ] ...

## Decisions made
- **{Decision}** — {context}. {Why if stated}. _(from "Recording", HH:MM)_

## Open questions raised
- **{Question}** — raised by {who}, {context}. _(from "Recording", HH:MM)_

## Notable quotes
- > {Quote} — {Speaker}, "{Recording}" HH:MM

## Skipped
- {Recording title} — still processing
```

### Notion destination

For each action item, call the helper script:

```bash
python3 ~/.claude/skills/meetings-digest/scripts/notion-write.py \
  --action-items <path-to-tempfile.json>
```

Where the tempfile is a JSON array of objects with shape:

```json
[
  {
    "action": "Send Bristol Barber Co the audit PDF",
    "owner": "Garrett",
    "context": "RANK",
    "due": "2026-05-23",
    "source_recording": "Bristol discovery call",
    "source_recorded_at": "2026-05-19T14:30:00Z",
    "source_timestamp": "00:23:15",
    "priority": "medium"
  }
]
```

The Notion helper creates one row per action item in the configured database. Each row has properties: Action (title), Context (select), Owner (text), Due (date), Source (text), Status (Open by default), Priority (Medium by default), Created (today).

Decisions, open questions, and notable quotes are written to a single Notion page (created via Notion API) titled "YYYY-MM-DD — Run {friday-rollup|manual}" linked to the action-item rows it generated.

## Record dedup state

After successfully writing each recording's extracted items to the destination, append its `file_id` and the current ISO-8601 UTC timestamp to the dedup state file. Write atomically (temp file + rename). Prune entries older than `dedup.retention_days` (default 90) at the same time.

If the destination write FAILED for a recording — do NOT mark it processed. The next run will pick it up again.

## Report to the user

After writing the digest, print a short summary:

```
✓ Plaud Meetings Digest — YYYY-MM-DD HH:MM (source: friday-rollup|manual)

Window:     last N days
Found:      M recordings in window
Skipped:    K already processed (dedup); J still processing (no transcript yet)
Processed:  P new recordings (total NN min)
Extracted:  X action items, Y decisions, Z open questions

Highlights:
  • {first 3 action items, one per line}

Written to: {destination path or Notion DB link}
```

If nothing was new (dedup skipped everything in the window):

```
No new recordings since last run. (M already processed in the last N-day window.)
```

Do NOT paste the full digest into the chat. The digest belongs in the destination.

## Anti-patterns

- **Do not trust Plaud's `get_note` output.** The user explicitly chose this skill because Plaud's built-in AI is weak. Re-extract from the transcript.
- **Do not invent action items.** If the transcript doesn't clearly support a commitment, leave it out. False positives erode trust.
- **Do not skip recordings silently.** If a recording is in the window but can't be processed (no transcript, error), surface it in the "Skipped" section.
- **Do not overwrite past digests.** Folder mode appends; Notion mode creates new rows.
- **Do not change the destination on the fly.** If the user wants to change destination, run the installer again — don't reconfigure inside the skill.
- **Do not log Notion API keys.** When debugging, mask them as `secret_xxx...{last4}`.

## Edge cases

- **No recordings in window** — print `No Plaud recordings found in the {N}-day window ending {date}. (Nothing to do.)` and exit cleanly without touching the dedup state.
- **All recordings already processed (dedup hit)** — print the "no new recordings since last run" message and exit cleanly.
- **Plaud OAuth expired** — surface the error and tell the user to re-run the installer (which re-OAuths). Do NOT update the dedup state.
- **Notion API key invalid** — surface the error and tell the user to re-run the installer with a fresh integration token. Do NOT update the dedup state.
- **`--force` flag passed** — bypass dedup filter; re-extract everything in the window. Useful for re-running after a bad extraction. The dedup state is still updated (so subsequent normal runs don't double-process).
- **Recording is non-English** — let Plaud's transcript be the source of truth; extract in whatever language the transcript uses.
- **Dedup state file corrupted** — back it up as `.processed-file-ids.json.bak` and start fresh with `{"processed": []}`. Print a warning; do not abort.

## Config schema (reference)

```json
{
  "version": "1.1.0",
  "installed_at": "ISO-8601 timestamp",
  "destination": {
    "type": "folder | notion",
    "folder": "/path/to/folder (folder mode)",
    "notion_api_key": "secret_... (notion mode)",
    "notion_database_id": "32-char hex (notion mode)"
  },
  "window_days": 3,
  "timezone": "America/New_York",
  "contexts": ["RANK", "Client work", "Portfolio", "Internal ops", "Personal"],
  "default_owner": "Garrett",
  "skip_recordings_under_minutes": 2
}
```
