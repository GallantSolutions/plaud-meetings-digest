# Plaud Meetings Digest

Turn your Plaud recordings into routed, structured action items — automatically. Cross-platform (Windows + Mac) with OS-appropriate destinations:

| Platform | Default destination | Per-meeting output | Weekly rollup output |
|---|---|---|---|
| **Windows** | OneDrive folders | One Word `.docx` per meeting in `OneDrive\Plaud Meetings\<meeting-type>\<per-week subfolder>\` — filename `<prefix>.<short topic> (<attendees>).docx` (e.g. `Kingsway Pharma\KPM.May 25-29, 2026 (Week 22)\KPM.Q3 Plans (John Smith).docx`). Weekly subfolders apply when `weekly_subfolders: true` per meeting type (default: KP yes, CH/P no). | Word `.docx` in the SAME week folder as that week's meetings — filename `<rollup_prefix>.<date range>, <year> (Week <N>).docx` (e.g. `KPR.May 25-29, 2026 (Week 22).docx`) |
| **Mac**     | Notion             | One row per meeting in "Plaud Meetings" DB (recap in page body, action items as checkboxes) | Notion page under the parent page |

Built by **Gallant**.

## What it does

Every weekday at **12:30 PM** and **5:00 PM** local time, plus a synthesis run on **Friday at 5:30 PM**, it:

1. Pulls the latest Plaud recordings
2. **Routes each one to a folder/tag based on the spoken opening line.** The client says "Kingsway Pharma meeting with John Smith" → it goes to the Kingsway Pharma folder. Says "Sunday morning church reflection" → goes to Church. Says "Personal note about the kids" → goes to Personal. No keyword detected → Uncategorized.
3. Extracts action items, decisions, open questions, key quotes from the transcript (NOT Plaud's built-in AI summary — re-extracted by Claude for quality)
4. Writes the per-meeting output to the routed destination
5. On Friday at 5:30 PM, synthesizes a **weekly rollup** for ONLY the meeting types flagged for rollup (default: Kingsway Pharma only — Church and Personal stay in their folders but don't roll up)

You stop hand-copying notes out of Plaud. Action items show up where you actually work, sorted by the meetings that matter for the rollup.

## Critical training point for the client

**Always state the meeting type at the start of every Plaud recording.** Examples:

- ✅ "Kingsway Pharma meeting with John Smith, we're going over Q3 plans"
- ✅ "Church reflection, this week's sermon was about…"
- ✅ "Personal note, reminder to call the dentist"
- ❌ "Hey, so I wanted to talk about…" (no keyword → routes to Uncategorized)

The skill scans the first ~30 seconds for the keyword. Default keywords for this client: **Kingsway Pharma**, **Church**, **Personal**. Operator can customize the list at install time or by editing `~/.claude/skills/meetings-digest/config.json`.

## How to use it (recipient)

### Automatic (you don't do anything)

Three scheduled jobs run on their own:

- **12:30 PM daily** — pull morning meetings
- **5:00 PM daily** — pull afternoon meetings
- **5:30 PM Friday** — synthesize the weekly rollup (Kingsway Pharma only)

Outputs land in:
- **Windows**: `<OneDrive>\Plaud Meetings\<meeting-type>\<per-week subfolder>\<prefix>.<short topic> (<attendees>).docx` (e.g. `Kingsway Pharma\KPM.May 25-29, 2026 (Week 22)\KPM.Q3 Plans (John Smith).docx`) — one `.docx` per meeting; action items rendered as ☐ checklist items. Meeting prefixes (`KPM` / `CHM` / `PM` / `UN`) carry a trailing `M` so the client can distinguish meeting files from anything else with the same 2-letter prefix in their OneDrive. The Friday rollup uses `KPR.` and lands in the same week folder as the week's meetings.
- **Mac**: one row per meeting in your "Plaud Meetings" Notion database; the row's page body has the full recap with action items as interactive checkboxes you can tick off as you complete them. The Friday rollup lands as a separate page under the same parent page.

### Manual

1. Open a terminal (Mac) or PowerShell (Windows)
2. Type `claude` → Enter
3. Type one of:
   - `/meetings-digest` — pull and route new meetings now
   - `/weekly-rollup` — synthesize the weekly rollup for Kingsway Pharma
   - `/meetings-digest --days 14` — wider window
   - `/meetings-digest --force` — re-extract everything (ignores dedup)

## What could go wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Meeting in "Uncategorized" folder | Client forgot to state the meeting type at the start | Re-record OR manually move the .docx |
| No recordings found | No Plaud meetings in the window | Check Plaud; record a test meeting |
| Asked to re-authorize Plaud | OAuth expired (rare) | Re-run install — it re-OAuths |
| Scheduled run didn't fire | Computer was asleep at the run time | Self-resolves when it wakes; or run manually |
| Friday rollup empty | No Kingsway Pharma meetings this week | Expected — nothing to roll up |
| Same meeting appearing twice | `--force` was used; or dedup state was reset | Edit duplicates manually |

For anything else: contact the Gallant operator who installed this.

## Privacy

- Plaud transcripts go **Plaud → Plaud's MCP server → Claude Code on your computer → your OneDrive / Notion**.
- **No data flows to Gallant.** Runs entirely on your computer, writes to your accounts.
- Notion API key (Mac) is stored in `~/.claude/skills/meetings-digest/config.json` with file permissions `600`.
- Plaud OAuth token is managed by the Plaud MCP server in its own credential store.

## Updates & alerting (operator-side)

Updates push automatically. A nightly Scheduled Task (Windows) / launchd job (Mac) at **3:00 AM local time** checks GitHub Releases; if a new release is published, the bundle replaces itself silently (snapshotting the previous version to `<install-prefix>/.versions/` for rollback). You'll see the new version in the next morning's run — zero client action required.

Every scheduled run pings [Healthchecks.io](https://healthchecks.io) before/after it runs. If a ping doesn't arrive within the expected window (machine asleep, Claude died, Scheduled Task de-registered, network down), the operator gets an email / Slack alert automatically — usually within ~1 hour of the missed window. Operator runbook for per-client Healthchecks setup: see [`OPERATOR-INSTALL-GUIDE.md`](OPERATOR-INSTALL-GUIDE.md).

To pin to a specific version (e.g., if a bad release ships): edit `~\.claude\skills\meetings-digest\config.json` and set `gallant_auto_update.pinned_version` to a release tag (e.g., `"v2.1.4"`). Auto-update will respect the pin. Set back to `null` to unpin.

## Versions

- **v2.2.2** — Per-week subfolders + meeting/rollup prefix disambiguation. Meeting types with `weekly_subfolders: true` (default for Kingsway Pharma) bucket their meetings into a `KPM.<date range>, <year> (Week N)/` subfolder. The weekly rollup lives in the SAME folder as that week's meetings — open one folder, see the week. Prefixes updated to disambiguate file kinds: `KPM` (Kingsway Pharma Meeting) + `KPR` (Kingsway Pharma Rollup) + `CHM` (Church Meeting) + `PM` (Personal Meeting). The trailing M/R disambiguates meeting/rollup files from any other files the client might keep with the same 2-letter prefix. Config schema adds `weekly_subfolders` + `rollup_filename_prefix` per type. Backwards-compatible: pre-v2.2.2 `_weekly/` folders + flat `<prefix>.<title>` files stay where they are; new meetings land in the new structure.
- **v2.2.1** — New filename convention: `<prefix>.<short topic> (<attendees>).docx` instead of `<YYYY-MM-DD HHMM> <title>.docx`. Each meeting type gets a 1-3 char prefix (KP / CH / P / UN by default). Claude generates the short topic (3-6 words) and extracts attendees from the spoken opening line. Files now sort by topic in OneDrive, not by date. Date is preserved in the document metadata and appended to the filename automatically only when there's a same-title collision. Rollup files match: `KP.Weekly Rollup (2026-W21).docx`. Config schema adds `filename_prefix` per meeting type + `fallback_filename_prefix` for Uncategorized. Pre-v2.2.1 installs that auto-update will pick up the new schema; existing `.docx` files are NOT renamed (old format files stay where they are; new meetings land in the new format).
- **v2.2.0** — Gallant standard install pattern retrofitted. Adds (a) nightly auto-update Scheduled Task / launchd job that pulls latest GitHub Release at 3 AM local; (b) Healthchecks.io heartbeat wrapping on every scheduled run so the operator gets alerted to silent failures within ~1 hour; (c) soft rollback via per-version snapshots at `<install-prefix>/.versions/`. Reusable as the `install-pattern` skill (`.claude/skills/install-pattern/`) — same pattern will land in every future client-facing build.
- **v2.1.4** — Windows install correctness pass. Four critical fixes validated on a clean `windows-latest` cloud runner: UTF-8 BOM on every `.ps1` file (Windows PowerShell was parser-erroring on the multi-byte chars used in banners); `install.ps1` probes 6 known Claude Code install locations after install (no shell restart needed); defensive null-handling on `Read-Host` returns; `schedule.ps1` drops the deprecated `[Microsoft.PowerShell.ScheduledJob.ScheduledJobTrigger]` type constraint that didn't ship with PowerShell 7. End-to-end install now lands all 3 Scheduled Tasks on a clean Windows machine.
- **v2.1.0** — One Notion row per MEETING (was one row per action item). Action items render as interactive Notion checkboxes you can tick off. Word docs use ☐ ballot-box characters for the same visual checklist UX. Claude Code Windows install fixed (correct package name + Anthropic's official PowerShell installer).
- **v2.0.0** — Cross-platform (Windows + Mac). Meeting-type routing from spoken opening line. Twice-daily ingestion (12:30 PM + 5:00 PM) + Friday 5:30 PM weekly rollup. Windows: Word docs in OneDrive folders. Mac: Notion. Weekly rollup filters to meeting types flagged `include_in_weekly_rollup: true` (default Kingsway Pharma only).
- **v1.2.0** — Mac, Notion-only. Friday 5:00 PM weekly rollup chained as `/meetings-digest --days 7` → `/weekly-rollup`.
- **v1.1.0** — Mac, Notion-only. Twice-daily schedule + dedup.
- **v1.0.0** — Mac, Notion-only. Friday rollup.

## Install correctness

Cross-platform install behavior is validated end-to-end on a clean `windows-latest` GitHub Actions runner via [`.github/workflows/test-install.yml`](.github/workflows/test-install.yml). Each Gallant pre-ship gate runs `bootstrap → install → assert` against a fresh Windows VM: winget installs Node/Python/Claude Code, `install.ps1` walks all 6 setup steps, and a final assertion step verifies that all 3 Scheduled Tasks register, both skills land in `%USERPROFILE%\.claude\skills\`, and `config.json` parses with `platform=windows`. Workflow runs are visible under [Actions](https://github.com/GallantSolutions/plaud-meetings-digest/actions).

## Uninstall

**Windows**: from `%LOCALAPPDATA%\plaud-meetings-digest\` run `.\uninstall.ps1`
**Mac**: from `~/Library/Application Support/plaud-meetings-digest/` (or the source folder you installed from) run `./uninstall.sh`

This removes the skill, scheduled tasks, and config. Your past meeting outputs (Word docs in OneDrive, Notion entries) stay with you.

---

*Built by Gallant. Questions? Contact the operator who installed this.*
