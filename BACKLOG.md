# Plaud-Meetings-Digest — Backlog

Polish items + bug fixes discovered after release but not blocking daily use. Move items to a release once they're scoped + targeted.

## v2.5.2 — update.ps1 propagates the tray (SHIPPED 2026-06-01)

- [x] **`update.ps1` now refreshes the tray.** After replacing bundle files + re-running `schedule.ps1`, `update.ps1` invokes the freshly-replaced `scripts\tray\install_tray.ps1 -Quiet` (via `powershell.exe -File`, non-fatal try/catch). This restores the tray propagation the old `auto-update.ps1` did and `update.ps1` had dropped — so tray code/fixes now reach the live install through a normal update instead of requiring a full reinstall. Closes the gap tracked under v2.5.1. **Operational impact:** converging a field machine to a tray fix is now a one-command `update.ps1` instead of a full bootstrap reinstall.

## v2.5.1 — tray parse fix + field diagnostic + PS parse-gate (SHIPPED 2026-06-01)

Follow-on to v2.5.0, same day. Three changes, all CI-verified (ps-parse + test-install green on windows-latest):

- [x] **`install_tray.ps1` PS 5.1 parse failure (real bug — likely the "tray never appears" root cause).** The file had no UTF-8 BOM but contained em-dashes (e.g. the "Tray already running - skipping launch" Write-Step string) + box-drawing comment separators. PS 5.1 reads a no-BOM file as cp1252, so the em-dash's multi-byte UTF-8 decoded to bytes that broke the string ("string is missing the terminator" at line 180, cascading from the unterminated string) → the script failed to parse → the tray widget never installed. The v2.4.2 "replace em-dashes" pass fixed only the line-144 Description string and missed the rest. Fix: transliterate all non-ASCII to ASCII (immune regardless of BOM survival) + add a UTF-8 BOM. This is the likely root cause of the persistent "tray app is still not there" symptom on the field machine.
- [x] **`scripts/report-state.ps1` — read-only field-state reporter** (post-install companion to `preflight.ps1`). Captures version + per-file SHA256 across both install copies + scheduler health + redacted config + log tail as a paste-able summary, plus a zip of the real build files. Secrets force-redacted before leaving the box. Lets the operator reconcile a live client install against the canonical tag.
- [x] **`.github/workflows/ps-parse.yml` — PS 5.1 real-parser CI gate.** Tokenizes every `.ps1` via `[System.Management.Automation.Language.Parser]::ParseFile` under `shell: powershell` (5.1 Desktop) on every push. Brace-counting / sub-agent review can't prove a script parses; only a real parser can. Caught the `install_tray.ps1` bug above on its first run — a bug that survived two releases. Covers scripts the install workflow never exercises (report-state, update, uninstall).

**Still deferred to a later patch (unchanged from v2.5.0 list below):** at-launch update-check hint; re-pin stale `claude-opus-4-7` model id; install.ps1 Claude-installer exit-code gap; install.ps1 ~L221 comment still references `auto-update.ps1`.

- [x] **(DONE in v2.5.2) `update.ps1` does not propagate the tray (regression vs old auto-update.ps1).** `update.ps1` excludes `install_tray.ps1` from its file copy (line ~164) and never re-runs the tray install, so it cannot deliver tray code/fixes — pulling v2.5.1 via `update.ps1` would NOT plant the fixed tray. The v2.4.1 `auto-update.ps1` handled this by copying the `tray/` subpackage AND invoking `install_tray.ps1` after file replacement; `update.ps1` dropped that. Fix: after pulling, copy `scripts/tray/` and invoke `install_tray.ps1` (wrapped in try/catch so a tray failure doesn't break the update). Until then, tray fixes must be delivered by running `install_tray.ps1` directly or a full reinstall.

## v2.5.0 — outage fixes + auto-update deprecation (SHIPPED 2026-06-01)

Diagnosed on bblessing's machine (NFI Consumer Products, Win11 domain) 2026-06-01 — v2.4.1 broke ALL scheduled runs since May 29; zero meetings processed for 4 days. Eight bugs fixed + auto-update deprecated. Full account: the bug-by-bug breakdown below, plus the auto-update deprecation rationale in Gallant vault ADR-012 (`04_labs/architecture/adr-012-deprecate-auto-update-operator-initiated.md`).

**Bug fixes (all ported into the bundle):**
- [x] **Bug 1 (critical):** `schedule.ps1` resolved Python via `Get-Command python`, which returns the Microsoft Store WindowsApps alias — unrunnable under Task Scheduler (exits `0x80070001` in ~1s). New `Resolve-PythonExe`: py.exe launcher → per-user install paths → PATH (rejecting the WindowsApps alias).
- [x] **Bug 2 (high):** HC.io outcome ping sent the raw 9-digit HRESULT as the suffix, which HC rejects → silent no-alert. Normalized to 0-255 (`Get-HcSuffix`); `-LogPath` now passed to every task so wrapper-level failures are logged.
- [x] **Bug 3 (high) → deprecated:** auto-update task scheduled at 3 AM with interactive logon never fired (machine locked). **Operator decision: deprecate auto-update entirely** (see ADR-012). Updates now operator-initiated via `update.ps1`.
- [x] **Bug 4 (medium):** weekly rollup skipped the first Friday when installed mid-week (StartBoundary = install time). `Get-NextWeekday` anchors the boundary to the next actual Friday.
- [x] **Bug 5 (critical):** `--` stop-parse token failed under `powershell.exe -File` (bound as a positional value). Removed from `Build-WrappedAction` + the wrapper usage comment.
- [x] **Bug 6 (critical):** `[CmdletBinding()]` alone keeps positional binding on; the inner exe landed in `$BundlePrefix`, runs logged `source=manual`. Added `PositionalBinding=$false`.
- [x] **Bug 7 (high):** `config.json` acquired a UTF-8 BOM from PS 5.1 `Set-Content -Encoding UTF8`, breaking `json.loads`. install.ps1 now writes BOM-less via .NET `UTF8Encoding($false)`; `digest-runner.py` reads with `encoding="utf-8-sig"` (defense-in-depth).
- [x] **Bug 8 (high):** `docx_writer.py` used glibc-only `%-I` → crashed every Windows docx write. Platform-branched to `%#I` on win32.

**Auto-update deprecation (ADR-012):** removed the scheduled task (`schedule.ps1`/`schedule.sh` defensively unregister it), flipped `gallant_auto_update.enabled` → false + `deprecated:true` in the config template, dropped the `auto_update` HC check, deleted `auto-update.{ps1,sh}`, stripped the auto-rollback hook from `run-with-heartbeat.{ps1,sh}`. New operator-initiated `update.ps1` (`-Check` / apply). New `scripts/preflight.ps1` (Python-alias + PS-edition + Claude-CLI + OneDrive-writability detection) wired into install.ps1.

**Deferred to v2.5.1 (tracked, not done):**
- [ ] **At-launch daily update-check hint (operator follow-up #4):** poll GitHub `releases/latest` once/day from an explicit entrypoint (tray or runner) and surface "newer version available." Needs a once-per-day throttle file + a stable entrypoint hook — cleanest once the tray is stable. `update.ps1 -Check` already provides the check primitive.
- [ ] **Residual blocker (separate from the 8 bugs):** on bblessing's machine the Claude CLI under Task Scheduler exits `STATUS_CONTROL_C_EXIT` before producing files. Investigate separately — likely resolved by the planned Playwright→DOCX pivot (no per-meeting Claude CLI call).
- [ ] **Stale model id:** config template defaults `weekly-rollup` to `claude-opus-4-7` — verify/pin to a current model id (dependency-pinning discipline) before next ship.
- [ ] **Install.ps1 line ~221 comment** still references `auto-update.ps1` for the Git prereq rationale — cosmetic, update to `update.ps1`.
- [ ] **install.ps1 Claude-installer fallback (pre-existing, low-severity):** `Invoke-Expression $installer` for the Claude CLI doesn't check `$LASTEXITCODE`, so the winget fallback is effectively unreachable for a non-throwing installer failure (the recursive path-search at ~L325 usually recovers `claude`). Surfaced by the v2.5.0 PowerShell audit; not introduced by v2.5.0. Fix: re-check `Get-Command claude` after the installer and branch to winget if absent.

## v2.4.3 — Tk widget bugfixes (SHIPPED 2026-05-29)

Same-day patch on top of v2.4.2. Two real bugs in widget_tk.py surfaced when the widget was tested programmatically on Mac with a stub Api — both would have made the Tk widget non-functional on Ben's machine had v2.4.2 reached him:

- [x] **`pady=(10, 4)` in `tk.Label` constructor — instant crash.** Tk widget constructors only accept scalar `pady`/`padx`; tuples are only valid in `.pack()` / `.grid()` geometry-manager calls. v2.4.2's bucket-section-header Label passed `pady=(10, 4)` to the constructor, which Tk parsed as a screen distance "10 4" and raised `TclError: bad screen distance "10 4"`. The widget would have crashed on the FIRST `_refresh()` call inside `create_window()`, before any window appeared. Fix: moved the asymmetric pady to the `.pack()` call where tuples are valid.

- [x] **`tk.after()` from a background thread is NOT thread-safe.** v2.4.2's `show()` and `notify_change()` called `_root.after(0, callback)` directly from non-Tk threads (pystray's left-click callback runs on the pystray daemon thread; the OneDrive `.docx` watcher runs on the watchdog observer thread). Tcl/Tk uses thread-local interpreters and undefined behavior results — events queued from background threads may never fire on the Tk loop. **Click-to-show would have silently done nothing on Windows.** Fix: introduced a `queue.Queue` event channel; `show()`/`hide()`/`notify_change()` put string events to the queue; `_drain_events()` runs every 100ms on the Tk thread via `after()` and processes them. Canonical pattern matches the well-trodden `psgtray` library.

- [x] **Mac-side programmatic test** (`/tmp/test_widget_tk_programmatic.py`) — 13 assertions: window construction, widget tree shape (5 checkboxes + 2 buttons + 4 bucket headers), checkbox toggle fires `mark_done` with correct args, re-toggle un-toggles, Refresh button increments refresh count, Open OneDrive button fires callback, `hide()` runs without crash, `notify_change()` from a background thread + drain fires refresh, `show()` from a background thread + drain fires `_do_show`. All 13 pass.

**Operator note**: v2.4.2 reached GitHub but was not deployed to Ben's machine before this patch. Ben's auto-update tonight pulls v2.4.3 (skipping the broken v2.4.2 entirely via the version-walks-forward logic).

## v2.4.2 — tray fixes + canonical bundle location + Windows Tk widget (SHIPPED 2026-05-29)

Patch release surfaced during the Kingsway/Ben install on 2026-05-29. Four real bugs blocked the tray widget from working on Ben's machine; all four shipped with this release.

- [x] **install.ps1: canonical bundle copy** to `%LOCALAPPDATA%\plaud-meetings-digest`. v2.4.1 left the bundle wherever install.ps1 was run from (TEMP, OneDrive-redirected Downloads, USB stick, etc.). Scheduled tasks then pointed at that ephemeral path; when Windows cleared TEMP, all four tasks broke silently. v2.4.2 detects non-canonical $ScriptDir at the top of install.ps1, copies the bundle to canonical location (preserving the logs/ folder), and rebases $ScriptDir so every downstream path derives off the stable location. Re-installs are safe (existing config preserved, existing logs preserved).
- [x] **install_tray.ps1: em-dash mojibake fix.** Line 144's Description string used U+2014 (em dash). PowerShell read the file without a UTF-8 BOM, interpreted the multi-byte sequence as `â€"` in Windows-1252, the embedded `"` byte closed the string mid-expression, parse error halted install_tray.ps1 before anything ran (no pip install, no shortcut, no tray launch). Replaced em-dash with ASCII hyphen throughout the file. Also enforces the durable rule against em-dashes in external-facing content.
- [x] **install_tray.ps1: pip stderr-as-error halt.** Line 107's `& $pythonExe -m pip install ...` could trigger pip's "script X installed in DIR which is not on PATH" warning to stderr. With `$ErrorActionPreference = 'Stop'` at the top of the script, PowerShell raised the warning as a terminating NativeCommandError even though pip itself succeeded — the install halted mid-step (no shortcut, no tray launch). Added `--no-warn-script-location` to suppress the warning + wrapped the pip call in try/catch + explicit `$LASTEXITCODE` check so a benign warning can't break the install.
- [x] **Tk widget on Windows (replaces pywebview).** pywebview's WebView2 COM initialization on the main thread blocks pystray's Shell_NotifyIcon registration with Windows; pywebview also refuses to run on a non-main thread ("pywebview must be run on a main thread") — they fundamentally can't share the main thread. Verdict: drop pywebview on Windows, render the widget with Tkinter instead. New file `scripts/tray/widget_tk.py` provides the same Api surface (`refresh`, `mark_done`, `open_source`, `open_onedrive`) with a native Tk window (440x600, hidden until tray click, scrollable list grouped by bucket KP/CM/CH/PE/OT, checkboxes that call `mark_done`, Refresh + Open OneDrive buttons, mouse-wheel scroll). tray.py imports widget_tk on Windows, widget (pywebview) on Mac/Linux; main() runs Tk mainloop on the main thread with pystray as daemon on Windows. Tkinter ships with Python so no extra deps. The tray icon stays visible AND the widget popup works.
- [x] **Validation**: sub-agent audit pass + Mac-side syntax checks. Tk widget independently tested on Ben's machine: pystray + Kingsway logo render correctly in isolation; the conflict was specifically the pywebview/pystray COM fight on the same main thread.

**Operator note**: Ben's v2.4.1 install on 2026-05-29 hit all four bugs sequentially. Tonight's 3 AM 2026-05-30 auto-update on Ben's machine pulls v2.4.2 — that resolves the tray failure observed during the day.

## v2.4.1 — auto-update tray propagation + install hardening (SHIPPED 2026-05-28)

Same-day patch following v2.4.0. Surfaced during post-ship audit when the user asked "will tonight's auto-update reinstall the tray app + are my action items safe?" Three real gaps surfaced:

- [x] **auto-update.ps1 didn't propagate the tray/ subpackage** to the live install. The earlier `Get-ChildItem -Filter '*.py' -File` filter shipped `tray_bridge.py` but left the `tray/` subdirectory behind, breaking `tray_bridge.py`'s `from tray import state` on Friday rollup day. Patched to recursively copy ALL scripts/ subpackages with the same exclusion list install.ps1 uses (preview.html, README.md, install_tray.ps1, __pycache__).
- [x] **auto-update.ps1 didn't invoke install_tray.ps1**, meaning v2.4.0's tray widget would never appear after a nightly auto-update (only after a fresh `bootstrap.ps1` run). Patched to call `install_tray.ps1` after file replacement, wrapped in try/catch so a tray failure doesn't break auto-update itself.
- [x] **tray_bridge.py defensive import** — the SKILL.md contract promised "if tray isn't installed, exit cleanly with zero closures," but the top-level `from tray import state` crashed before the defensive logic could run. Now wraps the import in try/except and returns [] / no-ops on ImportError. Belt-and-suspenders even after the auto-update fix lands.
- [x] **install.ps1 prereq hardening** for enterprise environments where winget gets blocked / mirror lag / silently fails:
  - Python: switched `Python.Python.3.11` (pinned) → `Python.Python.3` (alias rolls forward to latest 3.x major).
  - Node + Python: added vendor-direct fallback (nodejs.org/dist/latest-v20.x/ for Node, python.org/api JSON for Python) when winget install doesn't take.
  - Git for Windows: added install via winget `Git.Git` with vendor-direct fallback (git-for-windows GitHub releases). Auto-sets `CLAUDE_CODE_GIT_BASH_PATH` env var so Claude Code finds bash.exe (the Kingsway install hit this gap manually).
- [x] **Validation**: sandbox dry-run via `/validate-build` passed all 5 assertions on the patched bundle. Re-audited via fresh sub-agent: 0 critical, 0 regressions.

**Operator note**: tonight's 3 AM 2026-05-29 auto-update on Ben's machine pulls v2.4.1 (assuming this commit + tag lands before then). That installs the tray widget correctly via the patched auto-update path. Without v2.4.1, tonight's v2.4.0 update would have failed to bring up the tray + crashed the Friday rollup.

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
