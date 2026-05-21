# Operator Install Guide — Plaud Meetings Digest

**Audience:** Garrett (or any Gallant operator) installing this on a client's Mac. The client has Plaud and Notion but has never touched a terminal. **You do the install; they don't touch anything except their browser when prompted.**

**Expected total time on the client's machine:** 30–45 minutes (first-time install). 20 of that is unattended (Xcode CLT + Homebrew installs).

> **First-time setup:** if you haven't published this bundle to GitHub yet, read `docs/PUBLISH-TO-GITHUB.md` first (one-time, ~15 min). After publishing, every client install becomes a single curl command. Without the repo, you can still ship via the AirDrop+zip fallback path documented in Step 7.

---

## Pre-visit prep (do this BEFORE you sit with the client)

### 1. Confirm the client has the prerequisites

- [ ] **Plaud account** with at least one meeting already recorded (you'll test against real data)
- [ ] **Notion workspace** (any plan; free works)
- [ ] **macOS 11+** (Big Sur or newer). Check via Apple menu → About This Mac.
- [ ] **Admin password** on their Mac (needed for Homebrew + Xcode CLT)
- [ ] **At least 5GB free disk space**

If any of these are missing — resolve before the visit. Especially `macOS 11+`: a Mac on Catalina (10.15) or earlier needs an OS upgrade first, which is a multi-hour task you don't want to do mid-install.

### 2. Bundle the ship folder

From this vault:

```bash
cd "/Users/garrett3ratton/Documents/Claude MASTER/04_labs/g_labs"
zip -r plaud-meetings-digest.zip plaud-meetings-digest \
  -x 'plaud-meetings-digest/.DS_Store' \
  -x 'plaud-meetings-digest/*/.DS_Store'
```

The resulting `plaud-meetings-digest.zip` (~30 KB) is what you carry to the client. AirDrop / email / USB — whatever works.

### 3. Test the install on your own Mac first

**This is non-negotiable for the first ship.** Run `./install.sh` on YOUR Mac with YOUR Plaud + a throwaway Notion page. Verify the full flow works end-to-end before going to the client. Catch any environment-specific bugs in your house, not theirs.

If your Mac already has Claude Code + Node + Homebrew (it does), the installer will skip the prereq install steps. To simulate a fresh-machine experience, optionally test on a separate user account on your Mac.

---

## On the client's Mac — install sequence

Sit at their Mac. Open Terminal (`Cmd+Space` → type `Terminal` → Enter).

### Step 1 — Verify macOS version

```bash
sw_vers
```

Confirm `ProductVersion: 11.x` or higher. If `10.x`, stop — upgrade required first.

### Step 2 — Install Xcode Command Line Tools (if missing)

```bash
xcode-select --install
```

If you see "command line tools are already installed" — skip ahead. Otherwise a popup appears: click **Install**. This takes 5–15 minutes. While it installs, you can prep Step 3 mentally.

After it completes, verify:

```bash
xcode-select -p
```

Should print something like `/Library/Developer/CommandLineTools`.

### Step 3 — Install Homebrew (if missing)

```bash
command -v brew
```

If it prints a path — skip ahead. If it prints nothing:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

The client will be asked for their **admin password**. Have them type it; you don't need to see it. Takes 3–8 minutes.

After install completes, the Homebrew installer prints two lines telling you to add brew to PATH. **Copy and run them exactly as printed.** On Apple Silicon (M1/M2/M3) Macs, they look like:

```bash
echo >> ~/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Verify:

```bash
brew --version
```

Should print `Homebrew 4.x.x`.

### Step 4 — Install Node 20+

```bash
brew install node@20
brew link --overwrite node@20
```

Takes 1–3 minutes. Verify:

```bash
node -v
```

Should print `v20.x.x` or higher.

### Step 5 — Install Claude Code CLI

```bash
brew install --cask claude-code
```

If `--cask` isn't available or the cask doesn't exist on this Homebrew tap, use the official installer:

```bash
curl -fsSL https://claude.ai/code/install.sh | bash
```

Verify:

```bash
claude --version
```

Should print a version string. If not found, the cask install probably worked but PATH hasn't refreshed — open a new terminal tab or run `source ~/.zprofile`.

### Step 6 — Log into Claude Code (client-driven, you watch)

```bash
claude
```

Claude Code opens its first-run flow. The client picks their auth method — typically **claude.ai login** (browser opens, they sign in with their Anthropic/Google email).

If they don't have a claude.ai account yet, they create one at https://claude.ai (free) before continuing.

Once logged in, the Claude Code REPL is ready. Type `/exit` to quit back to the shell.

### Step 7 — Run the one-liner installer

**Primary path (after the GitHub repo is published — see `docs/PUBLISH-TO-GITHUB.md`):**

Paste this exact command into the client's Terminal:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/GallantSolutions/plaud-meetings-digest/main/bootstrap.sh)
```

(Replace `GallantSolutions` with the GitHub owner of the repo you published. If you set up the repo at `GallantSolutions/plaud-meetings-digest`, that's the value.)

The bootstrap downloads the latest release, drops it at `~/Library/Application Support/plaud-meetings-digest/`, and chains directly into the install walkthrough below.

**Fallback path (offline / no internet / pre-publication):**

If the client's Mac can't reach GitHub, or you're shipping before the repo is set up, AirDrop the bundle zip and run it manually:

```bash
cd ~/Downloads
unzip plaud-meetings-digest.zip
cd plaud-meetings-digest
./install.sh
```

Either path lands at the same interactive walkthrough below.

The installer walks through 6 steps. Most are automatic. The two interactive parts:

**Part 7a — Plaud OAuth**

When prompted, press Enter. A browser tab opens at Plaud. The client signs into their Plaud account (they have one) and clicks **Authorize**. Browser confirms; terminal continues.

**Part 7b — Output destination**

Choose **2** (Notion).

Now you need:

1. **Notion Integration Token.** Walk the client through:
   - Open https://www.notion.so/my-integrations in their browser
   - Click **+ New integration**
   - Name: `Plaud Meeting Digest`
   - Associated workspace: their workspace
   - Click **Submit**
   - Click **Show** next to "Internal Integration Secret"
   - Copy the token (starts with `secret_` or `ntn_`)

2. **Parent page ID.** Have the client:
   - Open Notion, navigate to where they want the meeting-digest database (e.g., a "Work" workspace page)
   - Click the **`…`** menu (top right) → **Connect to** → select **Plaud Meeting Digest** integration
   - Click **Confirm** when Notion asks about access
   - Copy the page URL — paste it to you — the 32-char hex string after the page title is the parent page ID. Example URL:

     ```
     https://www.notion.so/clientname/Work-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
     ```

     Parent page ID = `1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d`

Paste both into the installer when prompted. It calls the Notion API and creates the database under that page automatically (with the right schema).

**Part 7c — Friday weekly rollup schedule**

Answer **Y** when asked. The installer creates **one** launchd job:
- `com.gallant.plaud-meetings-digest.friday-rollup` — fires every Friday at 5:00 PM local time

The Friday run is a **chained** invocation: first `/meetings-digest` pulls the week's Plaud recordings and writes action items as Notion rows, then `/weekly-rollup` synthesizes the rollup page in Notion. The whole chain takes ~5–10 minutes depending on the number of meetings.

**Timezone caveat:** launchd uses the Mac's LOCAL time. If the client's Mac timezone isn't already Eastern, set it via System Settings → General → Date & Time → Time Zone → Automatic (off) → pick `Eastern Time`. Otherwise the Friday schedule fires at 17:00 in whatever zone the Mac is in.

To change time after install: edit `~/Library/LaunchAgents/com.gallant.plaud-meetings-digest.friday-rollup.plist` (change `Hour` / `Minute` integers; `Weekday` is 5 for Friday — change to 0=Sun, 6=Sat, etc. if needed), then `launchctl unload` + `launchctl load` it.

### Step 8 — Verify

Run a live test:

```bash
claude -p "/meetings-digest"
```

You'll see Claude Code process the client's last 7 days of Plaud recordings. **If they have no recent recordings, do a quick fake meeting on Plaud (5 min, just speak some action items aloud) so there's something to test against.**

After the digest finishes:
- Open the client's Notion → check the **Plaud Meeting Action Items** database
- Confirm rows appeared with correct Action / Owner / Due / Context

If nothing appeared but the run reported success — check that the Notion integration was connected to the parent page (Step 7b item 2). Without that connection, the database is created in a different scope and rows go nowhere visible to the client.

### Step 9 — Train the client (5 minutes)

Show them three things, in this order:

1. **Where action items appear (Friday 5pm).** Open Notion → Plaud Meeting Action Items database (raw action items) AND show the parent page where the weekly rollup pages will appear. "Every Friday at 5pm this fills up automatically with the action items from your week's meetings, and a rollup page lands here summarizing what to focus on next week. You read the rollup over the weekend, walk in Monday ready."

2. **How to trigger it manually.** Open Terminal → type `claude` → Enter → type `/meetings-digest` → Enter. "If you need a digest mid-week, this is how. Otherwise the schedule handles it."

3. **What to do if something breaks.** They have your phone/email. Common issues:
   - "I don't see any new items this week" → maybe no meetings recorded; check Plaud
   - "It asked me to log in again" → Plaud OAuth expired; they call you to re-run `./install.sh`

Don't overwhelm them with config knobs. The defaults are tuned.

---

## Handoff checklist

Before leaving:

- [ ] Test run produced action items in the client's Notion database AND a rollup page under the parent page
- [ ] Friday schedule verified: `launchctl list | grep plaud-meetings-digest` shows one row (`.friday-rollup`)
- [ ] Mac timezone confirmed (Eastern, since that's what the user requested)
- [ ] Client knows how to manually trigger (`/meetings-digest` then `/weekly-rollup`; showed them once)
- [ ] Notion database AND parent page are both bookmarked in their browser
- [ ] You have a follow-up date scheduled for the next Friday after install to verify the scheduled run fired and the rollup landed correctly

Send them a follow-up email with:

- Digest cadence (Friday 5:00 PM Eastern, weekly)
- Notion DB direct URL + parent page URL (where rollup lives)
- Your contact for issues
- A note that they can edit the Status column of action items as they complete them ("Open" → "Done"); the next rollup will list anything closed that week as a victory log
- A note that if Plaud takes a while to transcribe a meeting (rare, but happens for long ones), it'll be picked up by the NEXT Friday's run (the skill skips not-yet-transcribed recordings and re-checks via dedup)

---

## Troubleshooting

### "Notion DB isn't populating" after a run

Likely causes:
1. Notion integration token doesn't have access to the parent page → re-do Step 7b item 2 (connect integration to page)
2. Wrong database ID in config → check `~/.claude/skills/meetings-digest/config.json` against the actual DB URL
3. Notion API returned 401/403 → token revoked or wrong; re-run `./install.sh` and supply a fresh token

Quick diagnostic — write a single test row manually:

```bash
echo '[{"action":"test row","context":"Internal ops","owner":"test","priority":"Low"}]' > /tmp/test.json
python3 ~/.claude/skills/meetings-digest/scripts/notion-write.py --action-items /tmp/test.json
```

If that succeeds — the API + DB are fine; the issue is in the skill's extraction. If it fails — read the error message; it's almost always a permissions/token issue.

### "Plaud says no recordings this week"

```bash
claude
```

Then in the REPL:

```
List my Plaud recordings from the last 30 days.
```

If that returns recordings, the issue is the 7-day window. If it returns nothing, the client truly has no recent recordings — not a bug.

### Scheduled job isn't firing

```bash
launchctl list | grep plaud-meetings-digest
```

Expected: one row — `com.gallant.plaud-meetings-digest.friday-rollup`. If missing:

```bash
launchctl load ~/Library/LaunchAgents/com.gallant.plaud-meetings-digest.friday-rollup.plist
```

Check the logs:

```bash
tail -100 ~/Library/Logs/plaud-meetings-digest.log
tail -100 ~/Library/Logs/plaud-meetings-digest.stderr.log
```

Most common cause: macOS sleep at 5pm Friday. launchd defers, then fires when the Mac wakes. Should self-resolve at the next wake.

To run it manually right now (for testing):

```bash
launchctl start com.gallant.plaud-meetings-digest.friday-rollup
```

### Dedup state needs a reset

If for some reason the dedup state is wrong (e.g., the client wants to re-process a week of meetings into a freshly rebuilt Notion DB):

```bash
mv ~/.claude/skills/meetings-digest/.processed-file-ids.json \
   ~/.claude/skills/meetings-digest/.processed-file-ids.json.bak
# Then run with a wider window:
claude -p "/meetings-digest --days 14"
```

The skill will treat every meeting as new. Verify in Notion, then restore the backup if needed.

### "claude command not found" (after Step 5)

PATH hasn't been re-read. Either:

```bash
source ~/.zprofile
```

Or close + reopen Terminal.

### "Permission denied" running install.sh

```bash
chmod +x install.sh uninstall.sh scripts/*.sh scripts/*.py
./install.sh
```

(The zip should preserve executable bits, but some delivery methods strip them — AirDrop is fine, some email clients aren't.)

### Re-running install.sh after a problem

Safe and idempotent. The installer detects existing state and re-OAuths / re-writes config / re-installs the skill without leaving cruft. The Notion database is reused (not duplicated) if one already exists under the same parent page with the standard name.

### Removing everything

```bash
cd ~/Downloads/plaud-meetings-digest
./uninstall.sh
```

This removes the skill, scheduled job, and config. Plaud MCP can optionally be removed too (the uninstaller asks). The Notion database in the client's workspace is left alone (you don't want to delete their action-item history).

---

## What this bundle does NOT include (intentionally)

- **A way to edit action items from the terminal.** Action items are managed in Notion. The skill writes; the client manages from Notion.
- **A way to manually mark items "Done."** Same — the Notion DB has a Status column the client toggles. The skill doesn't read back.
- **Auto-deletion of old digests.** Past weeks accumulate in Notion. Client decides when to archive.
- **A web dashboard.** Plain folder mode produces markdown files; Notion mode produces a Notion database. No additional UI.
- **Multi-user support.** One install per Mac. If the client has a team, each person installs their own (each has their own Plaud).
- **Mobile/iOS support.** Mac-only. The launchd job is Mac-native. Plaud MCP via npx runs on macOS only.

---

## Versioning + updates

This is **v1.1.0**.

To ship an update later: bundle a new zip from `04_labs/g_labs/plaud-meetings-digest/`, deliver to the client, walk them through:

```bash
cd ~/Downloads
rm -rf plaud-meetings-digest
unzip plaud-meetings-digest-v1.1.0.zip
cd plaud-meetings-digest
./install.sh
```

The installer detects existing config and re-uses it (doesn't ask them to redo the Notion setup). Skill + scripts get refreshed; schedule gets re-loaded.

For breaking changes (e.g., config schema bump), document the migration step in the next version's CHANGELOG.

---

## Gallant-internal notes (don't share with client)

- **Build location:** `04_labs/g_labs/plaud-meetings-digest/` in the Claude MASTER vault
- **Source pillars:** G.Labs (this is the agent-factory pattern), CORE. (substrate-agnostic distribution per ADR-004 — Notion as a capability, not vendor-locked)
- **Why CLI not Desktop:** Claude Desktop doesn't support launchd-triggered scheduled runs against local MCP servers. CLI is the only Claude surface that does. Documented this decision so future versions don't relitigate.
- **Why Notion, not Obsidian:** trimmed at operator request (this client doesn't use Obsidian). To add an Obsidian destination later, mirror the `notion-write.py` pattern: a write helper that takes the same JSON action-items array shape and writes markdown to a vault folder. Add `obsidian` as a third `destination.type` in config.json. ~80 lines of Python.
- **Future v2 ideas:** (1) Slack/Teams notification when digest runs, (2) Notion property updates back to Plaud (mark recording as "processed"), (3) Multi-Plaud-account support, (4) iOS Shortcut to invoke digest from phone.
