# Plaud-Meetings-Digest — Backlog

Polish items + bug fixes discovered after release but not blocking daily use. Move items to a release once they're scoped + targeted.

## v2.3.1 — install hardening (discovered during Ben/Kingsway install 2026-05-26)

Triggered by ~15+ blockers during the first real Windows install. None blocked install end-to-end (operator + Ben worked through each), but every one is a paper-cut that the next client install should not re-hit.

- [ ] **BOM-write fix in install.ps1.** PowerShell's `Set-Content` writes UTF-8 with BOM by default; Python's `json.loads()` chokes on it with "Expecting value: line 1 column 1 (char 0)". Use `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` for every JSON file the installer touches (especially `config/digest-config.json` and `~/.claude.json`).
- [ ] **Defense-in-depth UTF-8 sig in digest-runner.py.** Open `config/digest-config.json` with `encoding='utf-8-sig'` so a BOM gets silently stripped on read regardless of how it got written. Belt-and-suspenders against #1.
- [ ] **Auto-set CLAUDE_CODE_GIT_BASH_PATH after Git install.** Git for Windows now installs user-local by default at `C:\Users\<user>\AppData\Local\Programs\Git\bin\bash.exe` instead of `C:\Program Files\Git\bin\bash.exe`. Claude Code on Windows requires bash but only looks at standard paths. Installer should detect Git's actual install location and `[Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", $bashPath, "User")`.
- [ ] **Detect Microsoft Store Python alias upfront.** Windows ships a `python.exe` stub that opens the Microsoft Store instead of running Python. Detect via `(Get-Command python).Source -match "WindowsApps"` and prompt operator to disable the alias at Settings → Apps → App execution aliases BEFORE attempting any Python install.
- [ ] **`claude mcp add` `-y` flag handling.** Current CLI rejects `-y`. Either upstream fix lands (track the Anthropic claude-code repo) OR fall back to direct `~/.claude.json` JSON edit (write the `mcpServers.plaud` entry programmatically). Already implemented this fallback manually for Ben; codify it in install.ps1.
- [ ] **Anthropic claude.ai/install.ps1 closes parent PowerShell.** Switching to `npm install -g @anthropic-ai/claude-code` is more reliable. Document in install.ps1 + remove fallback to the Anthropic installer.

## v2.4.0 — weekly rollup redesign (Ben-requested, not yet scoped)

Ben said "we will work on our rollup design" — separate spec conversation, not a code change. Open questions:

- What format does Ben actually want? (Mindmap-style? Section-color-coded like Plaud's web view? Plain markdown bullets?)
- Should rollup carry forward unresolved action items from prior week's per-meeting docs?
- Cross-bucket view (Kingsway + Committee + Church + Personal in one rollup) or per-bucket rollup separately?
- Push to Teams / email / SharePoint or stay OneDrive-folder-only?

Will spec after Ben confirms v2.3.0 per-meeting docs look right.

## v2.x — open improvements queued (lower priority)

- [ ] **Refactor `build_client_guide.py` + `build_client_guide_html.py` to read schedule + bucket list from config.** Currently hardcoded; future schedule changes require code edits. Config should be the single source of truth.
- [ ] **Reconsider schedule label names.** `lunch` / `eod` were the original times' rough descriptors; now misleading after Ben's 11AM / 4PM / 4:30 PM shift. Either rename to neutral labels (`morning` / `afternoon`) or document the labels-are-just-keys convention prominently.
- [ ] **Healthcheck-bootstrap helper.** Operator currently creates 4 UUIDs by hand at healthchecks.io for every client install. A helper script using the healthchecks.io API (`POST /api/v1/checks/`) could create all 4 checks programmatically given a single client name.

## How to move items off this list

When ready to ship a polish-version release:
1. Pick the highest-priority item from the relevant section
2. Implement + test against the install sandbox (`.claude/skills/validate-build`)
3. Run `/validate-build .` to confirm no regressions
4. `/ship` to commit + tag + create GitHub release
5. Strike through (or remove) the item here + note the release version it shipped in
