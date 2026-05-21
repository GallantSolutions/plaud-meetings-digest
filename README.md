# Plaud Meetings Digest

A small tool that turns your Plaud recordings into a clean weekly action-items rollup — every Friday at 5pm, in Notion or as a markdown file.

Built by **Gallant**.

## What it does

Every **Friday at 5:00 PM local time**, it:

1. Pulls all your Plaud recordings from the past week
2. Extracts the action items, decisions, and open questions from each transcript
3. Drops them into your Notion workspace (or a folder on your Mac)
4. Synthesizes a **weekly rollup page** — one focused document showing your top priorities for next week, carry-over items still open, decisions made, and themes Claude noticed across your meetings

You walk out of the office Friday evening with the rollup in hand, think on it over the weekend, and walk into Monday with priorities locked. You stop hand-copying notes out of Plaud. The thinking shows up where you actually work.

## Who set this up for you

A Gallant operator installed this on your Mac. You shouldn't need to do anything in the terminal — they handled all the setup.

This file is for your reference. The full installer-guide is in `OPERATOR-INSTALL-GUIDE.md` if you're curious.

## How to use it

### Automatic (you don't do anything)

Every **Friday at 5:00 PM local time**, the scheduled job runs. Within ~5–10 minutes:

- Action items from the week appear in your Notion database
- The **weekly rollup page** appears under the same Notion parent page, titled `Week of YYYY-MM-DD — Action Items Rollup`

(Folder mode: the rollup lands at `~/Plaud-Digests/_weekly/YYYY-WWW.md`.)

### Manual (when you want an immediate pull)

1. Open Terminal (Cmd+Space → type "Terminal" → Enter)
2. Type:

   ```
   claude
   ```

   Press Enter. You're now in Claude Code.

3. Type one of:

   ```
   /meetings-digest          # just pull this week's meetings into Notion
   /weekly-rollup            # synthesize the weekly rollup page
   ```

   Press Enter after the one you want. To do both (full Friday-style flow), run them in sequence.

4. When done, type `/exit` to leave.

### To pull a custom window

If you want more or fewer days:

```
/meetings-digest --days 14
```

(Last 14 days instead of the default 7.)

Or a specific start date:

```
/meetings-digest --since 2026-05-01
```

### To re-extract a meeting you already saw

The skill dedupes — once a meeting is in your Notion DB, it won't be re-processed. To force a re-extract (e.g., after editing the contexts config):

```
/meetings-digest --force
```

This re-processes every meeting in the window. New rows will appear in Notion; the old ones aren't deleted (so review + clean up the duplicates manually if needed).

## Where your action items go

Depending on what was set during install:

**Notion mode** — Open your Notion workspace. You'll have a database called **Plaud Meeting Action Items** with one row per action item:

| Action | Context | Owner | Due | Status | Priority | Source |
|---|---|---|---|---|---|---|
| Send Bristol the audit PDF | RANK | You | 2026-05-23 | Open | Medium | Bristol discovery call @ 00:23:15 |

Mark items "Done" in the Status column as you complete them. The skill never reads back, so your status edits are safe.

**Folder mode** — Open Finder → go to `~/Plaud-Digests/`. There's one markdown file per ISO week (`2026-W21.md`, `2026-W22.md`, etc.) holding raw action items, and a `_weekly/` subfolder with the synthesized rollup pages. Open in any text editor (TextEdit, Obsidian, VS Code — your choice).

## What the AI is doing

For each meeting:
- Pulls the **transcript** (the speaker-labeled text) — NOT Plaud's built-in AI summary. This skill explicitly ignores Plaud's AI because we re-extract with a more reliable model.
- Identifies **action items**: imperative + owner + (sometimes) deadline
- Identifies **decisions** that were explicitly made (not just discussed)
- Identifies **open questions** that came up but weren't resolved
- Tags each with a context (Client work / Internal ops / Strategic / Sales / Personal)

The default contexts are tuned for typical knowledge-worker meetings. If they don't fit your work, your installer can customize them by editing `~/.claude/skills/meetings-digest/config.json`.

## What could go wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| "No recordings found" | No Plaud meetings in the past week | Check Plaud directly; record a test meeting |
| Notion DB empty after run | Integration not connected to parent page | Contact your installer |
| Weekly rollup page not appearing | Parent page lost the integration permission | Contact your installer |
| Asked to re-authorize Plaud | OAuth expired (rare; ~once/year) | Contact your installer — they re-run install.sh |
| Scheduled run didn't fire | Mac was asleep Friday at 5pm | Self-resolves when Mac wakes; or run manually |
| Same meeting appearing twice | Dedup state was reset; or you ran `--force` | Edit the duplicates manually in Notion |
| "claude: command not found" | Terminal needs a refresh | Close + reopen Terminal |

For anything else: contact the Gallant operator who set this up.

## Privacy

- **Your Plaud transcripts** never leave the chain Plaud → Plaud's MCP server → Claude Code on your Mac → Notion (or your folder)
- **No data flows to Gallant.** This tool runs entirely on your Mac and writes to your accounts (your Notion, your folder).
- **The Notion API key** is stored in `~/.claude/skills/meetings-digest/config.json` with file permissions `600` (only you can read it).
- **The Plaud OAuth token** is stored by the Plaud MCP server in its own credential store.

## Uninstalling

If you want to remove this:

1. Find the original install folder (typically `~/Downloads/plaud-meetings-digest/`)
2. Open Terminal in that folder, run `./uninstall.sh`

This removes the skill, scheduled job, and config. It does **not** delete your past Notion entries or markdown files — those stay with you.

## Versions

- **v1.2.0** — Friday 5:00 PM weekly rollup. Two skills: `/meetings-digest` pulls + extracts action items into Notion; `/weekly-rollup` synthesizes a focused rollup page (top priorities for next week, carry-overs, decisions, themes). Both skills chain in the scheduled Friday run; both available for manual invocation.
- **v1.1.0** — Twice-daily schedule (deprecated in v1.2.0). Dedup by Plaud file ID.
- **v1.0.0** — Initial release. Plaud → Notion / folder. Weekly schedule.

---

*Built by Gallant Solutions. Questions? Contact the operator who installed this.*
