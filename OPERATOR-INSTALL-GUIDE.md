# Operator Install Guide — Plaud Meetings Digest

**Audience:** Garrett (or any Gallant operator) installing this on a client's computer. The client has Plaud and either a Notion workspace (Mac) or OneDrive (Windows), but has never touched a terminal. **You do the install; they don't touch anything except their browser when prompted.**

**Expected time on the client's machine:** 25–40 minutes (first-time install on a fresh Windows machine; less if Node/Python/Claude Code already exist).

---

## STEP 0: Pick the right one-liner based on the client's OS

The pipeline is auto-detect end-to-end after this — but the entry point can't be a single command because bash and PowerShell are different shells with incompatible syntax. Pick now, paste in their corresponding shell.

### 🪟 Windows (paste into PowerShell)

```powershell
iwr -useb https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.ps1 | iex
```

### 🍎 Mac (paste into Terminal)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
```

**Both bootstraps refuse to run on the wrong OS** and print the correct one-liner if you paste the wrong one. From here on, every prereq install, scheduler, output destination, log path, and file path adapts to the client's OS automatically.

---

---

## Pre-visit prep (do this BEFORE you sit with the client)

### 1. Confirm the client has the prerequisites

**Both platforms:**
- [ ] **Plaud account** with at least one recording (for test)
- [ ] **Admin password** on their computer (needed for prereq installers)
- [ ] **At least 5 GB free disk space**

**Windows:**
- [ ] **Windows 10 build 1809+** or Windows 11 (older versions lack winget)
- [ ] **OneDrive** signed in and syncing (verify via the OneDrive system-tray icon → folder open without errors)
- [ ] **PowerShell** (built-in)

**Mac:**
- [ ] **macOS 11+** (Big Sur or newer)
- [ ] **Notion workspace** (any plan, free works)

### 2. Test the one-liner on your own machine first

**Non-negotiable.** Run the appropriate one-liner on YOUR computer with YOUR Plaud + a throwaway Notion page / OneDrive folder. Verify the full flow before you go.

### 3. Print the client user guide for the LABS-branded folder

The client manual is the leave-behind. It lives at `CLIENT-USER-GUIDE.md` (source of truth) and renders to a board-grade `.docx` via:

```bash
python3 scripts/build_client_guide.py
```

Output lands at `dist/CLIENT-USER-GUIDE.docx`. Open in Word, print double-sided on letter paper (color recommended — status labels in the rollup section reference brand colors), slip into a Gallant LABS-branded folder. Hand it to the client at the start of the install visit.

The .docx is regenerated from markdown each release; do not edit the .docx by hand. To change wording, edit `CLIENT-USER-GUIDE.md` and re-run the build.

---

## On the client's computer — the one-liner install

Sit at their computer. Open the right shell, paste the right one-liner, walk through the interactive prompts.

### Windows path

Open **PowerShell** (Start menu → type `PowerShell` → Enter).

Paste this single command:

```powershell
iwr -useb https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.ps1 | iex
```

Press Enter. The script:

1. Resolves the latest release
2. Downloads + extracts to `%LOCALAPPDATA%\plaud-meetings-digest\`
3. Chains into `install.ps1` which does everything else:
   - Detects + installs missing prereqs via winget (Node 20, Python 3.11, Claude Code, python-docx)
   - Installs Plaud MCP + opens browser for OAuth (client clicks Authorize)
   - Detects OneDrive folder + creates `Plaud Meetings\` inside it
   - Asks about meeting routing (accept defaults: Kingsway Pharma + Committee + Church + Personal — all four roll up)
   - Installs both skills (meetings-digest + weekly-rollup) into Claude Code
   - Installs three Windows Task Scheduler jobs (lunch 11:00 AM, EOD 4:00 PM daily, Friday rollup 4:30 PM)

### Mac path

Open **Terminal** (Spotlight → `Terminal` → Enter).

Paste this single command:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
```

Press Enter. The script does the equivalent on Mac:

1. Resolves the latest release
2. Downloads + extracts to `~/Library/Application Support/plaud-meetings-digest/`
3. Chains into `install.sh` which:
   - Detects + installs missing prereqs (xcode-select, Homebrew, Node 20, Claude Code, python-docx)
   - Installs Plaud MCP + opens browser for OAuth
   - Defaults destination to Notion: walks you through creating a Notion integration + parent page
   - Asks aboBut meeting routing (defaults: Kingsway Pharma + Committee + Church + Personal — all four roll up)
   - Installs both skills into Claude Code
   - Installs three launchd jobs (lunch 11:00 AM, EOD 4:00 PM daily, Friday rollup 4:30 PM)

---

## Interactive prompts during install

Both platforms walk through the same logical steps:

### Plaud OAuth
A browser tab opens at Plaud. **Client signs in and clicks Authorize.** Terminal continues automatically.

### Output destination
- **Windows**: auto-uses OneDrive (resolved from environment variables). The installer creates `Plaud Meetings\` inside the detected OneDrive folder.
- **Mac**: prompts for Notion or folder. Default is Notion. If Notion:
  1. Open https://www.notion.so/my-integrations → **+ New integration** → name `Plaud Meeting Digest` → workspace = theirs → Submit
  2. Click **Show** next to Internal Integration Secret → copy token
  3. Open the Notion page that should hold the database → click `…` → **Connect to** → pick the integration → Confirm
  4. Copy the page URL → paste it → the installer extracts the 32-char hex (the last segment of the URL)

### Meeting routing
Accept defaults (**Y** when prompted). Defaults for Kingsway are:
- `Kingsway Pharma` → folder `Kingsway Pharma` → meetings `KPM.*` + rollup `KPR.*` → **INCLUDED in weekly rollup**
- `Committee` → folder `Committee` → meetings `CMM.*` + rollup `CMR.*` → **INCLUDED in weekly rollup**
- `Church` → folder `Church` → meetings `CHM.*` + rollup `CHR.*` → **INCLUDED in weekly rollup**
- `Personal` → folder `Personal` → meetings `PM.*` + rollup `PR.*` → **INCLUDED in weekly rollup**

All four buckets roll up per Ben's request (one `.docx` per bucket per week). To customize later (e.g., add another meeting type or turn off a bucket's rollup): edit `~/.claude/skills/meetings-digest/config.json` and re-run the schedule script — no need to re-run the full install.

### Heartbeat (Step 4b/5b — operator alerts when something breaks)

The installer prompts for Healthchecks.io check UUIDs — one per scheduled job (lunch / eod / rollup). If you provide them, every scheduled run pings Healthchecks before/after it fires, and you get an email or Slack alert within ~1 hour when a run misses its window.

**One-time Gallant setup (do this ONCE, ever):**
1. Sign up at [healthchecks.io](https://healthchecks.io) using your operator email (free tier covers 20 checks)
2. Create a project: "Gallant Client Installs"
3. Add a Slack or email integration so missed pings notify you

**Per-client setup (every new install — ~2 min):**

Before sitting with the client, in Healthchecks → "+ Add Check" 3 times with these settings:

| Check name | Period | Grace |
|---|---|---|
| `<client-slug> — plaud lunch` | 1 day | 30 min |
| `<client-slug> — plaud EOD` | 1 day | 30 min |
| `<client-slug> — plaud Friday rollup` | 1 week | 1 hour |

Copy each check's ping UUID (the 32-char hex string after `https://hc-ping.com/`). Paste them when the installer prompts during Step 4b (Windows) / 5b (Mac). Pressing Enter on all three skips heartbeat — operator gets no alerts but the install still completes.

To set non-interactively (e.g., re-running install for a fresh sandbox), set:
```bash
export GALLANT_HEARTBEAT_CHECK_LUNCH=<uuid>
export GALLANT_HEARTBEAT_CHECK_EOD=<uuid>
export GALLANT_HEARTBEAT_CHECK_ROLLUP=<uuid>
```

### Schedule (Step 6/7)
Accept default (**Y** when prompted). Installs three jobs (lunch + EOD + Friday rollup).

### Updates (operator-initiated)

Updates are applied by the operator, not on a nightly schedule. When you publish a new GitHub Release (`gh release create vX.Y.Z`), upgrade a client by running `update.ps1` on their machine — it pulls the latest release and overwrites the install (config + state survive). Run `update.ps1 -Check` first to see whether a newer version is available without applying it. There is no nightly self-update task.

**To pin a client to a specific version** (e.g., if a bad release shipped):
1. SSH / TeamViewer into the client machine
2. Edit `~\.claude\skills\meetings-digest\config.json`
3. Set `gallant_auto_update.pinned_version` to a release tag (e.g., `"v2.1.4"`)
4. `update.ps1` will respect the pin and not upgrade past it until you set it back to `null`

**To roll back manually**:
- Windows: copy contents of `%LOCALAPPDATA%\plaud-meetings-digest\.versions\<old-tag>\` over `%LOCALAPPDATA%\plaud-meetings-digest\`, then re-run `scripts\schedule.ps1`
- Mac: same but at `~/Library/Application\ Support/plaud-meetings-digest/`

---

## Train the client (5 minutes)

The single most important thing to convey:

> **Always state the meeting type at the very start of each Plaud recording.** Examples that work:
> - "Kingsway Pharma meeting with John Smith…"
> - "Committee call about compliance…"
> - "Sunday church reflection…"
> - "Personal note about…"
>
> If they forget, the recording goes to "Uncategorized" — recoverable, but extra work.

Then show them:

1. **Where their outputs appear:**
   - Windows: OneDrive → Plaud Meetings → (the right meeting-type folder)
   - Mac: Notion → Plaud Meeting Action Items database + the parent page where weekly rollups appear
2. **The Friday rollup:** "Every Friday at 4:30 PM, one rollup `.docx` lands per bucket (Kingsway Pharma, Committee, Church, Personal). Read them over the weekend, walk into Monday ready."
3. **Manual trigger:** open Terminal/PowerShell → `claude` → `/meetings-digest` or `/weekly-rollup` for an immediate run.
4. **If something seems off:** contact you.

---

## Verify before leaving

Trigger a test run:

**Windows:**
```powershell
Start-ScheduledTask -TaskName 'PlaudMeetingsDigest_Lunch'
```

**Mac:**
```bash
launchctl start com.gallant.plaud-meetings-digest.lunch
```

Wait ~5 minutes. Check:
- A `.docx` (Windows) or Notion rows (Mac) appeared in the routed location
- The routing worked: a recording opened with "Kingsway Pharma" went into the Kingsway Pharma folder, not Uncategorized

If nothing appeared: check the log file.

- **Windows:** `%LOCALAPPDATA%\plaud-meetings-digest\logs\`
- **Mac:** `~/Library/Logs/plaud-meetings-digest.log`

Most common failure: client recorded a test meeting but didn't say the meeting type at the start → routed to Uncategorized. Have them re-record with a proper opening line.

---

## Handoff checklist

- [ ] Test run produced output in the routed location
- [ ] All three scheduled jobs verified
   - Windows: `Get-ScheduledTask -TaskName 'PlaudMeetingsDigest_*'` shows 3 rows (Lunch, EOD, Rollup)
   - Mac: `launchctl list | grep plaud-meetings-digest` shows 3 rows
- [ ] Computer timezone confirmed = Eastern (or whatever client wants the schedule to fire in)
- [ ] Client knows to state the meeting type at every recording's start
- [ ] Client knows where outputs appear (folder bookmark / Notion bookmark)
- [ ] Follow-up date scheduled for the first Friday post-install to verify the rollup fires

---

## Troubleshooting

### Output is going to Uncategorized

Client didn't say the meeting type clearly at the start. Either:
1. Have them re-record with a clean opening, OR
2. Manually move the `.docx` (Windows) or update the Context property on Notion rows (Mac)

### Friday rollup is empty

Either no meetings landed in any rollup-enabled bucket this week, OR the `meetings-digest` Friday 4:00 PM run failed before the 4:30 PM rollup. Check the log.

### "claude command not found" (after install)

Terminal/PowerShell needs a refresh. Close + reopen.

### Re-running the installer

Safe. Detects existing state, re-OAuths if needed, re-writes config, refreshes the skill. Notion DB / OneDrive folder are preserved.

### Removing everything

**Windows:** `cd $env:LOCALAPPDATA\plaud-meetings-digest; .\uninstall.ps1`
**Mac:** `cd ~/Library/Application\ Support/plaud-meetings-digest && ./uninstall.sh`

Removes skills + scheduled jobs + config. Past Word docs / Notion entries stay.

---

## Versioning + updates

This is **v2.0.0** — cross-platform with meeting routing. To ship updates:

1. Make changes in this vault at `04_labs/g_labs/plaud-meetings-digest/`
2. `cd` to that folder, commit, push
3. `git tag -a v2.1.0 -m "..."` and push the tag
4. Publish a GitHub release for the tag
5. Existing clients: tell them to re-run the same one-liner — it pulls the latest release and overwrites the install. Config + state (dedup state file, Notion DB, OneDrive folder) all survive.

---

## Gallant-internal notes

- **Build location:** `04_labs/g_labs/plaud-meetings-digest/` in the Claude MASTER vault
- **Live repo:** https://github.com/GallantSolutions/plaud-meetings-digest
- **Architectural pivot from v1.2.0:** OS-branched destinations (Word+OneDrive on Windows / Notion on Mac), spoken-opening-line meeting routing, twice-daily schedule restored + Friday 5:30 PM rollup added. Meeting types `include_in_weekly_rollup` flag controls which routed types feed the rollup synthesis.
- **Cross-platform notes:**
  - Python helpers (state_store, docx_writer, rollup_docx_writer, onedrive_resolve, notion-*) are cross-platform
  - Skills (markdown) are cross-platform
  - Install + uninstall + schedule are OS-specific (`.ps1` on Windows / `.sh` on Mac)
  - Bootstrap is OS-specific (`bootstrap.ps1` for Windows, `bootstrap.sh` for Mac)
- **State storage:** `~/.claude/skills/meetings-digest/state/` (action-items.jsonl + processed-file-ids.json). Cross-platform path.
