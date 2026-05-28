# Plaud-Meetings-Digest — Backlog

Polish items + bug fixes discovered after release but not blocking daily use. Move items to a release once they're scoped + targeted.

## v2.3.1 — Claude model pin (SHIPPED 2026-05-28)

Commit `e44795c` · tag `v2.3.1` · release https://github.com/GallantSolutions/plaud-meetings-digest/releases/tag/v2.3.1

- [x] **Pin Claude model per-skill.** `meetings-digest` → `claude-sonnet-4-6` (light per-meeting routing/titling). `weekly-rollup` → `claude-opus-4-7` (heavy Friday synthesis for pharma-grade exec deliverable). Both fall back to Sonnet 4.6 on rate-limit. Operators override via `config.claude_models.<skill>`. Removes silent quality risk of running on whatever the `claude` CLI defaults to.

## v2.3.2 — install hardening (originally scoped for v2.3.1; deferred when model pin took priority)

Triggered by ~15+ blockers during the first real Windows install (Ben/Kingsway 2026-05-26). None blocked install end-to-end (operator + Ben worked through each), but every one is a paper-cut that the next client install should not re-hit. See [[reference_windows_enterprise_install_landmines]] memory for the full 12-item operator checklist + [[feedback_distributable_bundles_need_preflight]] for the higher-order discipline this represents.

- [ ] **BOM-write fix in install.ps1.** PowerShell's `Set-Content` writes UTF-8 with BOM by default; Python's `json.loads()` chokes on it with "Expecting value: line 1 column 1 (char 0)". Use `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` for every JSON file the installer touches (especially `config/digest-config.json` and `~/.claude.json`).
- [ ] **Defense-in-depth UTF-8 sig in digest-runner.py.** Open `config/digest-config.json` with `encoding='utf-8-sig'` so a BOM gets silently stripped on read regardless of how it got written. Belt-and-suspenders against #1.
- [ ] **Auto-set CLAUDE_CODE_GIT_BASH_PATH after Git install.** Git for Windows now installs user-local by default at `C:\Users\<user>\AppData\Local\Programs\Git\bin\bash.exe` instead of `C:\Program Files\Git\bin\bash.exe`. Claude Code on Windows requires bash but only looks at standard paths. Installer should detect Git's actual install location and `[Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", $bashPath, "User")`.
- [ ] **Detect Microsoft Store Python alias upfront.** Windows ships a `python.exe` stub that opens the Microsoft Store instead of running Python. Detect via `(Get-Command python).Source -match "WindowsApps"` and prompt operator to disable the alias at Settings → Apps → App execution aliases BEFORE attempting any Python install.
- [ ] **`claude mcp add` `-y` flag handling.** Current CLI rejects `-y`. Either upstream fix lands (track the Anthropic claude-code repo) OR fall back to direct `~/.claude.json` JSON edit (write the `mcpServers.plaud` entry programmatically). Already implemented this fallback manually for Ben; codify it in install.ps1.
- [ ] **Anthropic claude.ai/install.ps1 closes parent PowerShell.** Switching to `npm install -g @anthropic-ai/claude-code` is more reliable. Document in install.ps1 + remove fallback to the Anthropic installer.

## v2.4.0 — Tray widget (Ben-requested, SHIPPED 2026-05-28)

Shipped 2026-05-28 in response to Ben asking for "a small widget in the windows tray that he can pop open and quickly check off open items before the friday rollup" — explicitly framed as scope-down from the Command Center mockup at [dist/dashboard-demo-2026-05-26.html](dist/dashboard-demo-2026-05-26.html). Kingsway-branded to match the CC (Jost / Nunito Sans / IBM Plex Mono, royal blue + gold, circle-crown logo).

**Architecture:** Python + `pywebview` + `pystray` + `watchdog`. New subpackage at `scripts/tray/` — see [scripts/tray/README.md](scripts/tray/README.md) for the full file map.

- [x] **`scripts/tray/` subpackage shipped**: parser.py extracts action items from per-meeting .docx files (handles both v2.2.x and v2.3.0+ formats), state.py persists check state with weekly auto-reset, widget.html renders the Kingsway-branded popup with checkboxes, widget.py + tray.py wire pywebview + pystray + a watchdog observer that re-renders whenever a new doc lands.
- [x] **`scripts/tray/install_tray.ps1`** standalone Windows installer — installs pywebview/pystray/Pillow/watchdog, copies tray code to `%LOCALAPPDATA%/plaud-tray`, creates Startup shortcut with `pythonw.exe -m scripts.tray.tray`, launches now if not already running. Idempotent.
- [x] **Tabbed Open/Done UI + bucket grouping**. Two tabs with count badges; sections grouped by bucket in fixed order KP → CM → CH → PE with colored swatches + sticky section headers. Checked items fade out of Open and appear in Done with "closed Tue 2:14 PM" timestamps. Closed-empty + open-empty states distinct.
- [x] **Tray icon badge with live open count**. Brand-red pill compositied onto the tray icon, super-sampled 3× and downscaled with LANCZOS for buttery anti-aliasing at any Windows DPI. Tooltip text fallback: "Plaud — N open items" / "Plaud — all clear". Updates on tray startup, watchdog .docx events, and every mark_done click.
- [x] **Weekly rollup integration via `scripts/tray_bridge.py`**. Bridge module maps tray closure IDs (16-char SHA256 of docx_filename+text) → state_store IDs (8-char SHA1 of source_file_id+action) by replaying action-items.jsonl. Weekly-rollup SKILL.md step 0a runs `tray_bridge.py --harvest` and pipes to `state_store.append_closures`. After rollup writes, SKILL calls `tray_bridge.py --mark-fired` which stamps `rollup_fired_at` in state.json; tray's Done tab auto-clears on next refresh. Idempotent. Dedups against existing closures.jsonl so re-runs don't double-append.
- [x] **Wired `install_tray.ps1` into main `install.ps1` Step 5c** so plaud's bootstrap installs the tray automatically. Mac install.sh also copies the tray subpackage so the rollup bridge runs on either host.
- [x] **F-001/F-002/F-004 install-wiring bugs fixed pre-ship** (caught by validation-by-sub-agent pass before tagging). install.ps1 + install.sh now explicitly copy `tray/` subpackage with exclusions (preview.html, README.md, install_tray.ps1, __pycache__). install.ps1 invokes install_tray.ps1 as a sub-step.
- [x] **F-003 timezone-corrupt compare fixed** in `state.clear_done_after_rollup` — parses ISO-8601 timestamps to datetime objects before comparison, tolerating DST shifts and operator timezone changes.
- [ ] **Real-machine Windows verification** — Mac smoke verified parser + state roundtrip + bridge harvest with synthetic JSONL + badge renderer; needs Windows verification (pywebview WebView2 render, pystray icon + badge visibility, watchdog event firing on OneDrive sync, end-to-end rollup-day check → tab clear).

**Known MVP limitations** (deliberate — flagged for v2 if Ben asks): no carry-forward across weeks, no toast on new doc, no "ignore" distinction (only done/not-done). See [scripts/tray/README.md](scripts/tray/README.md#known-limitations-mvp).

## v2.4.0 — observability gate + preflight + 2-stage bootstrap (NEW priorities from 2026-05-28 self-learn pass)

Higher-order discipline items captured in operator memory 2026-05-28 after Kingsway install retrospective. Each ties to a durable feedback memory; collectively raise the install discipline floor for all future Gallant client bundles.

- [ ] **`scripts/preflight.ps1` + `scripts/preflight.sh` — built-in landmine detection** ([[feedback_distributable_bundles_need_preflight]]). Runs FIRST in install.ps1 / install.sh; refuses to proceed until the 12-item Windows enterprise landmine check ([[reference_windows_enterprise_install_landmines]]) passes. Build base template at `04_labs/g_labs/_install-template/preflight.ps1` so RANK installer + future Gallant bundles inherit. ~3h work, saves ~30-60 min PER FUTURE CLIENT INSTALL.
- [ ] **Install isn't complete without observability** ([[feedback_install_not_complete_without_observability]]). install.ps1 must refuse to declare "install complete" until either (a) 4 Healthchecks UUIDs entered, or (b) operator explicitly chooses "skip monitoring" with a 24-hour warning printed. Per-client project memory tracks `installed_at` + `observability_live_at` dates with 24h SLA.
- [ ] **2-stage bootstrap pattern instead of `iwr | iex`** ([[feedback_bootstrap_curl_pipe_iex_fragile_enterprise]]). The current curl-pipe-execute one-liner fails opaquely on enterprise machines (TLS-MITM proxies, AppLocker, EDR LOLBin flags, ExecutionPolicy). Switch to: stage 1 = `Invoke-WebRequest -OutFile`; stage 2 = `powershell.exe -ExecutionPolicy Bypass -File <path> -Client <name> -NonInteractive`. Reproducible, auditable, inspectable.
- [ ] **Dependency-pin manifest in README** ([[feedback_client_bundle_dependency_pinning]]). New section `## Dependency Pin Manifest` listing pinned models / CLI versions / package versions / API versions. /ship skill verifies this section exists + matches code before allowing a release tag.

## v2.4.x — weekly rollup redesign (Ben-requested, not yet scoped)

Ben said "we will work on our rollup design" — separate spec conversation, not a code change. Open questions:

- What format does Ben actually want? (Mindmap-style? Section-color-coded like Plaud's web view? Plain markdown bullets?)
- Should rollup carry forward unresolved action items from prior week's per-meeting docs?
- Cross-bucket view (Kingsway + Committee + Church + Personal in one rollup) or per-bucket rollup separately?
- Push to Teams / email / SharePoint or stay OneDrive-folder-only?

Will spec after Ben confirms v2.3.0+ per-meeting docs look right.

## v2.x — open improvements queued (lower priority)

- [ ] **Refactor `build_client_guide.py` + `build_client_guide_html.py` to read schedule + bucket list from config.** Currently hardcoded; future schedule changes require code edits. Config should be the single source of truth.
- [ ] **Reconsider schedule label names.** `lunch` / `eod` were the original times' rough descriptors; now misleading after Ben's 11AM / 4PM / 4:30 PM shift. Either rename to neutral labels (`morning` / `afternoon`) or document the labels-are-just-keys convention prominently.
- [x] ~~**Healthcheck-bootstrap helper.** Operator currently creates 4 UUIDs by hand at healthchecks.io for every client install. A helper script using the healthchecks.io API (`POST /api/v1/checks/`) could create all 4 checks programmatically given a single client name.~~ **SHIPPED 2026-05-28** at `.claude/scripts/hc_bootstrap.py`. Idempotent via `unique=["name", "tags"]`. Usage: `.claude/scripts/hc_bootstrap.py --client "<Name>" --product plaud`. Used internally going forward (Kingsway's 4 UUIDs were created in UI before the helper existed).

## Considered + Deferred (decisions captured, not building)

### Plaud .docx native export (deferred 2026-05-28)

**The pursuit:** Use Plaud's literal native .docx export instead of rendering Plaud's markdown ourselves via docx_writer.py.

**What we found:** Plaud's web app has a private export endpoint at `POST https://api.plaud.ai/file/document/export` reverse-engineered via DevTools HAR capture. Auth via custom `x-pld-user: <64-hex-token>` header (NOT `Authorization: Bearer`). Request body sends full markdown inline + format/title/timestamps. Response: presigned S3 URL with 20-min TTL pointing to a `.md.docx` file.

**Why deferred:**
1. **Marginal value:** v2.3.0 already gives Ben Plaud's content verbatim (the substance Ben actually asked for). Native Plaud docx is only a styling polish.
2. **Maintenance risk:** Reverse-engineered private API — Plaud can change request body shape, auth scheme, or endpoint URL without notice. We'd find out via broken installs at clients.
3. **Auth uncertainty unresolved:** Need to verify if MCP OAuth token (from `~/.plaud/tokens-mcp.json`) equals the `x-pld-user` web token. Operator has no paid Plaud account on Mac to complete the probe.
4. **Token refresh + S3 download in unattended context:** the 20-min presigned URL TTL is tight; would need defensive token-refresh + retry logic.

**Trigger to revisit:** Either (a) Plaud adds official export endpoint to MCP server (track Plaud changelog), or (b) Ben specifically asks for the styling difference (Ben hasn't), or (c) a future client onboarding surfaces the need.

**Knowledge captured:** API surface documented above for future-self / future-session reference. No code written; no commit; no ship.

## How to move items off this list

When ready to ship a polish-version release:
1. Pick the highest-priority item from the relevant section
2. Implement + test against the install sandbox (`.claude/skills/validate-build`)
3. Run `/validate-build .` to confirm no regressions
4. `/ship` to commit + tag + create GitHub release
5. Strike through (or remove) the item here + note the release version it shipped in
