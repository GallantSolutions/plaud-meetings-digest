# Plaud Tray Widget

A small Windows system-tray widget that aggregates the open action items from this week's Plaud meeting docs and lets the operator check them off before the Friday rollup fires.

Kingsway-branded to match the [Command Center mockup](../../dist/dashboard-demo-2026-05-26.html) — same brand tokens, same checkbox pattern, same typography.

## How it works

1. The plaud-meetings-digest skill writes `.docx` files into the operator's OneDrive `Plaud Meetings/{bucket}/{week-folder}/` as meetings get recorded throughout the week.
2. The tray widget runs in the background (autostarted at login), watching that folder via `watchdog`. When any `.docx` is added or modified, the widget re-parses and the open-items list refreshes automatically.
3. The operator clicks the tray icon → small window pops open with two tabs:
   - **Open** — every unfinished action item from the current ISO week, grouped in fixed order: Kingsway Pharma → Committee → Church → Personal. Each section has a colored swatch + count.
   - **Done** — items checked off this week, same bucket grouping, with a "closed Tue 2:14 PM" timestamp on each row.
4. Checking an item in the Open tab fades it out and moves it to the Done tab. State persists to `%APPDATA%/plaud-tray/state.json`.
5. Friday's weekly rollup harvests this state via `scripts/tray_bridge.py --harvest` (see below) — every item the operator checked off in the tray gets excluded from the Friday rollup automatically.
6. After the rollup writes successfully, the skill calls `scripts/tray_bridge.py --mark-fired` which stamps `rollup_fired_at` into state.json. On the next refresh, the Done tab clears — the operator starts the next week with a fresh slate.
7. Safety net: state auto-resets every Monday (new ISO week) regardless of whether the rollup fired.

## File map

| File | Purpose |
|---|---|
| `tray.py` | Entry point — pystray icon + watchdog file watcher + threading orchestration |
| `widget.py` | Pywebview window + JS API (refresh, mark_done, open_source, open_onedrive) |
| `widget.html` | The popup UI — Kingsway-branded, single self-contained file |
| `parser.py` | `.docx` → action items extractor (heading-driven, handles both v2.2.x and v2.3.0+ formats) |
| `state.py` | `state.json` read/write with atomic temp+rename, auto-reset on new ISO week |
| `config.py` | Bridge to existing plaud config + OneDrive resolution (reuses `onedrive_resolve.py`) |
| `assets/kingsway-logo.png` | Tray icon + widget header logo (copied from `dist/assets/kingsway/logo-circle.png`) |
| `install_tray.ps1` | Windows installer — installs deps, copies files, creates Startup shortcut |

And one sibling module up at `scripts/tray_bridge.py`:

| File | Purpose |
|---|---|
| `../tray_bridge.py` | Bridge between tray state.json and state_store closures.jsonl. Run by the weekly-rollup skill on Friday — `--harvest` emits closures, `--mark-fired` clears the Done tab. |

## Dependencies

- `pywebview` — renders the HTML widget in a native window (uses Edge WebView2 on Windows, already on Win10+)
- `pystray` — system tray icon
- `Pillow` — required by pystray for image loading
- `watchdog` — OneDrive folder change detection
- `python-docx` — already a plaud dep; reused here

## Install (manual, for testing)

From this directory on a Windows machine that already has plaud-meetings-digest installed:

```powershell
.\install_tray.ps1
```

To remove:

```powershell
.\install_tray.ps1 -Uninstall
```

For the production install path, this will be invoked from `install.ps1` in plaud v2.4.0+.

## Item ID stability

Item IDs are SHA256(meeting_filename + "\x00" + item_text)[:16]. Same meeting + same text = same ID across re-scans. If a meeting doc gets re-rendered with slightly different wording, the ID changes and the item appears as a new unchecked entry. That's deliberate — meaningful text changes deserve a fresh look.

## Known limitations (MVP)

- **No carry-forward across weeks.** State resets every Monday. If an action item was open Friday and still open the following Monday (Plaud re-recorded it in a new meeting), it appears as new.
- **No native Windows badge count.** The tray icon doesn't show a number overlay; the Open/Done counts are visible only when the widget is open (where they appear as tab badges).
- **No toast notifications.** When a new `.docx` lands, the widget refreshes silently; the operator only sees the new items if they open the widget.
- **No "ignore" — only "done."** Can't differentiate "I did this" from "this isn't actually an action item for me." Both treated as done.

Each of these is a v2 candidate if Ben asks.
