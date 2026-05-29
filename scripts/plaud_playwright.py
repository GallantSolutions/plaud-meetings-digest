#!/usr/bin/env python3
"""
plaud_playwright.py — Playwright client for Plaud web export.

Pulls Plaud's rich Export-tier Summary documents directly from web.plaud.ai —
the same artifact Plaud's web "Export" button produces. The Plaud MCP server's
`get_note` only returns the basic summary; the rich multi-section analytical
Summary lives only in the web Export. This module fetches it.

ARCHITECTURE
------------
- Persistent Chromium profile at PROFILE_DIR (cross-restart auth).
- Headed first-run via `playwright_setup.ps1` for interactive Plaud login.
- Headless thereafter, reusing the saved session cookies.
- Default Chromium fingerprint (no stealth tricks — they add detection
  surface). We're a legitimate user accessing our own account.
- Throttled to human-realistic timings (configurable; defaults below).
- All selectors externalized to config so UI updates don't require redeploy.
- Every action timeout'd; falls back to MCP via the caller on any failure.

NOT IN SCOPE
------------
- Detection-evasion tricks (canvas-fingerprint spoofing, navigator.webdriver
  removal, headless flag patching). Plaud's TOS doesn't prohibit automation
  but if they implement detection later, the legitimate path is to revert to
  MCP, not to escalate evasion.
- Multi-account orchestration (one Plaud user per install).
- Concurrent runs (singleton — guarded by lockfile).

USAGE
-----
    from plaud_playwright import PlaudPlaywright

    async with PlaudPlaywright(config) as client:
        if not await client.ensure_session():
            return False
        meetings = await client.list_new_meetings(since_file_id=last_id, limit=20)
        for m in meetings:
            path = await client.export_meeting(m["file_id"])
            # path is now a .md or .docx in staging folder

SELECTORS
---------
Externalized to config.plaud.playwright.selectors so they can be tuned via
config edit when Plaud updates their UI without redeploying. Defaults are
placeholders verified-empirically against web.plaud.ai during the first
codegen pass (see playwright_setup.ps1 -CodegenMode). Override per-install
via the config block.

THROTTLE
--------
Random uniform delays between actions, sampled from config-defined ranges.
Defaults are conservative (human-paced). Adjust at config.plaud.playwright.throttle.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Page,
        Playwright,
        TimeoutError as PlaywrightTimeoutError,
    )
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception  # type: ignore


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _install_prefix() -> Path:
    """Resolve the bundle install prefix on either OS."""
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "plaud-meetings-digest"
    return Path.home() / "Library" / "Application Support" / "plaud-meetings-digest"


def profile_dir() -> Path:
    return _install_prefix() / ".playwright-profile"


def staging_dir() -> Path:
    return _install_prefix() / ".playwright-staging"


def lockfile_path() -> Path:
    return _install_prefix() / ".playwright-lock"


def ready_marker_path() -> Path:
    return _install_prefix() / ".playwright-ready"


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SELECTORS = {
    # URL the persistent session lands on once authenticated.
    "login_url": "https://web.plaud.ai/",
    "files_url": "https://web.plaud.ai/files",

    # Login-state probe: a selector that is ONLY present when authenticated.
    # Conservative default: a user-menu/avatar element. Verify via codegen.
    "logged_in_probe": "[data-testid='user-menu']",

    # Files-list page: a selector matching one row per meeting.
    "file_row": "[data-testid='file-row']",
    # Attribute on each row holding the Plaud file ID.
    "file_id_attr": "data-file-id",

    # Within a file row: title / recorded_at / duration cells.
    "file_title_in_row": "[data-testid='file-title']",
    "file_recorded_at_in_row": "[data-testid='file-recorded-at']",

    # File detail navigation — clicking a row should open the detail view.
    "file_detail_loaded_probe": "[data-testid='file-detail']",

    # Export button on file detail page.
    "export_button": "button:has-text('Export')",
    # Export-format option in the dropdown that appears after clicking Export.
    "export_format_md": "text='Markdown'",
    "export_format_docx": "text='Word'",
}

DEFAULT_THROTTLE = {
    "navigation_min_s": 8,
    "navigation_max_s": 15,
    "click_min_s": 3,
    "click_max_s": 7,
    "micro_min_s": 1,
    "micro_max_s": 3,
    "page_load_timeout_s": 30,
    "action_timeout_s": 15,
    "max_meetings_per_run": 20,
    "rate_limit_backoff_s": [300, 900, 1800],  # 5min, 15min, 30min
}

DEFAULT_BEHAVIOR = {
    "headless": True,
    "viewport_width": 1280,
    "viewport_height": 800,
    "user_agent": None,  # None → Playwright default Chromium UA (DON'T spoof)
    "preferred_export_format": "md",  # "md" or "docx"
}


# ---------------------------------------------------------------------------
# Config + state
# ---------------------------------------------------------------------------

@dataclass
class PlaywrightConfig:
    """Resolved Playwright config — merges user config over defaults."""
    selectors: dict = field(default_factory=lambda: dict(DEFAULT_SELECTORS))
    throttle: dict = field(default_factory=lambda: dict(DEFAULT_THROTTLE))
    behavior: dict = field(default_factory=lambda: dict(DEFAULT_BEHAVIOR))

    @classmethod
    def from_main_config(cls, main_config: dict) -> "PlaywrightConfig":
        plaud = main_config.get("plaud") or {}
        pw = plaud.get("playwright") or {}
        sel = dict(DEFAULT_SELECTORS)
        sel.update(pw.get("selectors") or {})
        thr = dict(DEFAULT_THROTTLE)
        thr.update(pw.get("throttle") or {})
        beh = dict(DEFAULT_BEHAVIOR)
        beh.update(pw.get("behavior") or {})
        return cls(selectors=sel, throttle=thr, behavior=beh)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PlaywrightUnavailable(Exception):
    """Playwright isn't installed. Caller should fall back to MCP."""


class SessionExpired(Exception):
    """Plaud login session expired. Caller should alert operator."""


class SelectorMissing(Exception):
    """A configured selector didn't resolve. Likely Plaud UI changed."""


class RateLimited(Exception):
    """Plaud returned 429 or detected automation. Back off."""


# ---------------------------------------------------------------------------
# Throttle helpers
# ---------------------------------------------------------------------------

async def _sleep_jitter(min_s: float, max_s: float) -> None:
    """Sleep a random duration between min_s and max_s (inclusive)."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class PlaudPlaywright:
    """
    Async context-managed Playwright client for Plaud web export.

    Single-shot per scheduled run. Spawns a persistent browser context
    pointing at the persistent profile directory, walks the meetings list,
    exports new files to the staging folder, and tears down.
    """

    def __init__(self, config: dict, *, log_fn=None):
        if not _PLAYWRIGHT_AVAILABLE:
            raise PlaywrightUnavailable(
                "playwright package not installed. Run scripts/playwright_setup.ps1 "
                "(Windows) or scripts/playwright_setup.sh (Mac) once."
            )
        self.cfg = PlaywrightConfig.from_main_config(config)
        self._log = log_fn or (lambda msg: print(msg, flush=True))
        self._pw: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._lock_acquired = False

    # ---- context manager ------------------------------------------------

    async def __aenter__(self) -> "PlaudPlaywright":
        self._acquire_lock()
        try:
            await self._launch()
        except Exception:
            self._release_lock()
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self.close()
        finally:
            self._release_lock()

    def _acquire_lock(self) -> None:
        lock = lockfile_path()
        lock.parent.mkdir(parents=True, exist_ok=True)
        if lock.exists():
            # Stale lock recovery: if PID in lock is dead, take it.
            try:
                stale = lock.read_text().strip()
                age = time.time() - lock.stat().st_mtime
                if age > 3600:  # 1h: definitely stale
                    lock.unlink(missing_ok=True)
                else:
                    raise RuntimeError(
                        f"Another Playwright run is in progress (lock held by {stale}, "
                        f"{int(age)}s old). Refusing to start concurrent run."
                    )
            except (OSError, ValueError):
                lock.unlink(missing_ok=True)
        lock.write_text(f"{os.getpid()}@{datetime.now(timezone.utc).isoformat()}")
        self._lock_acquired = True

    def _release_lock(self) -> None:
        if self._lock_acquired:
            try:
                lockfile_path().unlink(missing_ok=True)
            except OSError:
                pass
            self._lock_acquired = False

    async def _launch(self) -> None:
        profile = profile_dir()
        profile.mkdir(parents=True, exist_ok=True)
        staging_dir().mkdir(parents=True, exist_ok=True)

        self._pw = await async_playwright().start()
        self._context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=bool(self.cfg.behavior.get("headless", True)),
            viewport={
                "width": int(self.cfg.behavior.get("viewport_width", 1280)),
                "height": int(self.cfg.behavior.get("viewport_height", 800)),
            },
            accept_downloads=True,
        )

        # Default per-page timeouts.
        action_ms = int(self.cfg.throttle.get("action_timeout_s", 15) * 1000)
        nav_ms = int(self.cfg.throttle.get("page_load_timeout_s", 30) * 1000)
        for page in self._context.pages:
            page.set_default_timeout(action_ms)
            page.set_default_navigation_timeout(nav_ms)
        # Apply to future pages.
        self._context.set_default_timeout(action_ms)
        self._context.set_default_navigation_timeout(nav_ms)

    async def close(self) -> None:
        try:
            if self._context is not None:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                await self._pw.stop()
        except Exception:
            pass
        self._context = None
        self._pw = None

    # ---- page helpers ---------------------------------------------------

    async def _new_or_first_page(self) -> Page:
        assert self._context is not None
        if self._context.pages:
            return self._context.pages[0]
        return await self._context.new_page()

    async def _navigate(self, page: Page, url: str) -> None:
        await _sleep_jitter(
            self.cfg.throttle["navigation_min_s"],
            self.cfg.throttle["navigation_max_s"],
        )
        self._log(f"  navigate: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeoutError as e:
            raise SelectorMissing(f"navigation to {url} timed out: {e}") from e

    async def _click(self, page: Page, selector: str) -> None:
        await _sleep_jitter(
            self.cfg.throttle["click_min_s"],
            self.cfg.throttle["click_max_s"],
        )
        self._log(f"  click: {selector}")
        try:
            await page.click(selector)
        except PlaywrightTimeoutError as e:
            raise SelectorMissing(f"click on {selector} timed out: {e}") from e

    async def _micro_pause(self) -> None:
        await _sleep_jitter(
            self.cfg.throttle["micro_min_s"],
            self.cfg.throttle["micro_max_s"],
        )

    # ---- public methods -------------------------------------------------

    async def ensure_session(self) -> bool:
        """
        Verify Plaud login session is still valid.

        Returns True if logged in, False if session expired (caller alerts
        operator + falls back to MCP for this run).
        """
        page = await self._new_or_first_page()
        await self._navigate(page, self.cfg.selectors["login_url"])

        probe = self.cfg.selectors["logged_in_probe"]
        try:
            await page.wait_for_selector(probe, timeout=10_000)
            self._log("  ensure_session: logged in")
            return True
        except PlaywrightTimeoutError:
            self._log(f"  ensure_session: probe '{probe}' not found — session expired")
            return False

    async def list_new_meetings(
        self, *, since_file_ids: set[str], limit: int = 20
    ) -> list[dict[str, str]]:
        """
        Return up to `limit` meeting rows whose file_id is NOT in
        `since_file_ids`. Caller tracks processed file IDs via state_store.

        Each meeting dict contains:
            file_id     — Plaud's internal file ID
            title       — display title from the row
            recorded_at — ISO-8601 timestamp from the row (best-effort)
        """
        page = await self._new_or_first_page()
        await self._navigate(page, self.cfg.selectors["files_url"])
        await self._micro_pause()

        sel = self.cfg.selectors
        try:
            await page.wait_for_selector(sel["file_row"], timeout=15_000)
        except PlaywrightTimeoutError as e:
            raise SelectorMissing(
                f"file row selector '{sel['file_row']}' didn't render — "
                f"likely Plaud UI changed. Verify via codegen."
            ) from e

        rows = await page.query_selector_all(sel["file_row"])
        self._log(f"  list_new_meetings: {len(rows)} total rows visible")

        cap = min(int(self.cfg.throttle.get("max_meetings_per_run", limit)), limit)
        out: list[dict[str, str]] = []

        for r in rows:
            if len(out) >= cap:
                break
            try:
                file_id = await r.get_attribute(sel["file_id_attr"])
                if not file_id or file_id in since_file_ids:
                    continue
                title_el = await r.query_selector(sel["file_title_in_row"])
                title = (await title_el.inner_text()).strip() if title_el else ""
                rec_el = await r.query_selector(sel["file_recorded_at_in_row"])
                rec = (await rec_el.inner_text()).strip() if rec_el else ""
                out.append({"file_id": file_id, "title": title, "recorded_at": rec})
            except Exception as e:
                self._log(f"  list_new_meetings: row parse error skipped: {e}")
                continue

        self._log(f"  list_new_meetings: {len(out)} new (cap={cap})")
        return out

    async def export_meeting(self, file_id: str) -> Optional[Path]:
        """
        Navigate to a meeting's detail page, click Export, choose format,
        wait for the download, save to the staging folder. Returns the
        downloaded file path, or None on failure.
        """
        page = await self._new_or_first_page()
        sel = self.cfg.selectors
        beh = self.cfg.behavior
        fmt = beh.get("preferred_export_format", "md")
        fmt_selector = sel.get(
            "export_format_md" if fmt == "md" else "export_format_docx"
        )

        detail_url = f"{sel['files_url'].rstrip('/')}/{file_id}"
        await self._navigate(page, detail_url)

        try:
            await page.wait_for_selector(
                sel["file_detail_loaded_probe"], timeout=15_000
            )
        except PlaywrightTimeoutError as e:
            self._log(f"  export_meeting({file_id}): detail page didn't render: {e}")
            return None

        await self._micro_pause()

        try:
            async with page.expect_download() as dl_info:
                await self._click(page, sel["export_button"])
                await self._micro_pause()
                await self._click(page, fmt_selector)
            download = await dl_info.value
        except PlaywrightTimeoutError as e:
            self._log(f"  export_meeting({file_id}): export-button or download timeout: {e}")
            return None
        except Exception as e:
            self._log(f"  export_meeting({file_id}): export flow error: {e}")
            return None

        # Persist into staging with file_id prefix so downstream can correlate.
        suggested = download.suggested_filename or f"{file_id}.{fmt}"
        # Sanitize and prefix.
        safe = "".join(c for c in suggested if c.isalnum() or c in "._- ")
        out_path = staging_dir() / f"{file_id}__{safe}"
        await download.save_as(str(out_path))
        self._log(f"  export_meeting({file_id}): saved → {out_path.name}")
        return out_path


# ---------------------------------------------------------------------------
# Sync wrapper for simple callers
# ---------------------------------------------------------------------------

async def fetch_new_summaries_async(
    config: dict, *, since_file_ids: set[str], log_fn=None
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """
    Convenience: open client, list new meetings, export each. Returns
    (results, error). On error, results may be partial.

    Each result dict: {"file_id", "title", "recorded_at", "staging_path"}.
    """
    log = log_fn or (lambda m: print(m, flush=True))
    results: list[dict[str, Any]] = []
    try:
        async with PlaudPlaywright(config, log_fn=log) as client:
            if not await client.ensure_session():
                return results, "session_expired"
            new = await client.list_new_meetings(since_file_ids=since_file_ids)
            for m in new:
                p = await client.export_meeting(m["file_id"])
                if p is None:
                    log(f"  export failed for {m['file_id']}; skipping")
                    continue
                results.append({**m, "staging_path": str(p)})
        return results, None
    except PlaywrightUnavailable as e:
        return results, f"unavailable:{e}"
    except SessionExpired:
        return results, "session_expired"
    except SelectorMissing as e:
        return results, f"selector_missing:{e}"
    except RateLimited:
        return results, "rate_limited"
    except Exception as e:
        return results, f"error:{type(e).__name__}:{e}"


def fetch_new_summaries(
    config: dict, *, since_file_ids: set[str], log_fn=None
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Sync wrapper. Runs the async fetch in an event loop."""
    return asyncio.run(
        fetch_new_summaries_async(
            config, since_file_ids=since_file_ids, log_fn=log_fn
        )
    )


# ---------------------------------------------------------------------------
# CLI for verification / debugging
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Plaud Playwright client — debug/verify entrypoint"
    )
    parser.add_argument(
        "--check-session",
        action="store_true",
        help="Open browser, verify Plaud login session is alive. Exit 0/1.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List up to 20 most recent meetings on Plaud.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json",
        help="Path to skill config.json",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"ERROR: config missing at {args.config}")
        raise SystemExit(1)

    cfg = json.loads(args.config.read_text())

    if args.check_session:
        async def _check():
            async with PlaudPlaywright(cfg) as client:
                ok = await client.ensure_session()
                print("OK" if ok else "EXPIRED")
                raise SystemExit(0 if ok else 1)
        asyncio.run(_check())

    if args.list:
        async def _list():
            async with PlaudPlaywright(cfg) as client:
                if not await client.ensure_session():
                    print("Session expired. Re-run playwright_setup.ps1 -ReAuth")
                    raise SystemExit(1)
                meetings = await client.list_new_meetings(since_file_ids=set())
                for m in meetings:
                    print(f"  {m['file_id']:24} {m['recorded_at']:24} {m['title']}")
        asyncio.run(_list())
