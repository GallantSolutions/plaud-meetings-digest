# Plaud Meetings Digest

Turn your Plaud recordings into routed, structured action items — automatically. Cross-platform (Windows + Mac) with OS-appropriate destinations:

| Platform | Default destination | Per-meeting output | Weekly rollup output |
|---|---|---|---|
| **Windows** | OneDrive folders | One Word `.docx` per meeting in `OneDrive\Plaud Meetings\<meeting-type>\` | Word `.docx` in `<meeting-type>\_weekly\` |
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
- **Windows**: `<OneDrive>\Plaud Meetings\<meeting-type>\<YYYY-MM-DD HHMM> <title>.docx` — one `.docx` per meeting; action items rendered as ☐ checklist items
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

## Versions

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
