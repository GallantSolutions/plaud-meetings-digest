#!/usr/bin/env python3
"""
plaud_playwright_runner.py — pre-Claude-Code Plaud fetch entrypoint.

Runs BEFORE digest-runner.py invokes Claude Code. Uses plaud_playwright to:
  1. Open a Playwright session with the persistent profile
  2. Identify new meetings (file IDs not in state_store)
  3. Export each as Plaud's rich Summary (.md preferred, .docx fallback)
  4. Drop downloaded files into .playwright-staging/
  5. Write a manifest the meetings-digest skill consumes

The skill then reads .playwright-staging/ files instead of calling MCP
get_note(). If this runner fails OR the staging folder is empty, the skill
falls back to MCP for the remaining meetings (Ben always gets a document;
sometimes it's the shallower one).

EXIT CODES
----------
    0 — runner completed; some or all new meetings staged
    1 — config error
    2 — disabled via config (plaud.method == "mcp_only"); not an error
    3 — Playwright unavailable (not installed); falls through cleanly
    4 — session expired; operator should re-auth via playwright_setup
    5 — selector mismatch; operator should re-codegen + update config
    6 — rate limited; back off
    9 — unrecognized error; check logs

Invoked by digest-runner.py before Claude Code; can also be run manually
for verification:

    python3 scripts/plaud_playwright_runner.py --source manual --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Make sibling modules importable when invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONFIG_PATH = Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json"


def _install_prefix() -> Path:
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "plaud-meetings-digest"
    return Path.home() / "Library" / "Application Support" / "plaud-meetings-digest"


LOG_DIR = (
    _install_prefix() / "logs"
    if platform.system() == "Windows"
    else Path.home() / "Library" / "Logs"
)
LOG_PATH = LOG_DIR / "plaud-playwright.log"
STAGING_DIR = _install_prefix() / ".playwright-staging"
MANIFEST_PATH = STAGING_DIR / "_manifest.json"


def log(msg: str, *, verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n"
    with LOG_PATH.open("a") as f:
        f.write(line)
    if verbose:
        print(line, end="")


def _heartbeat(url_base: str | None, check_uuid: str | None, suffix: str) -> None:
    """Best-effort Healthchecks ping. Never raises."""
    if not (url_base and check_uuid):
        return
    url = f"{url_base.rstrip('/')}/{check_uuid}/{suffix}"
    try:
        urllib.request.urlopen(url, timeout=10).read()
    except (urllib.error.URLError, OSError):
        pass


def _read_processed_file_ids(config: dict) -> set[str]:
    """
    Best-effort: read action-items.jsonl and harvest source_file_ids
    we've already processed. The runner skips meetings we've seen.
    """
    state_path = _install_prefix() / "state" / "action-items.jsonl"
    if not state_path.exists():
        return set()
    ids: set[str] = set()
    try:
        for raw in state_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                fid = row.get("source_file_id") or row.get("file_id")
                if fid:
                    ids.add(str(fid))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return ids


def _clear_staging(verbose: bool) -> None:
    """Empty .playwright-staging/ before a run so we don't reprocess stale files."""
    if not STAGING_DIR.exists():
        return
    removed = 0
    for p in STAGING_DIR.iterdir():
        try:
            if p.is_file():
                p.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        log(f"cleared {removed} stale files from staging", verbose=verbose)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="manual",
                        help="Run-source label for logs (lunch | eod | manual)")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH,
                        help="Path to skill config.json")
    parser.add_argument("--verbose", action="store_true",
                        help="Echo log lines to stdout")
    args = parser.parse_args()

    log(f"=== plaud_playwright_runner.py starting (source={args.source}) ===",
        verbose=args.verbose)

    if not args.config.exists():
        log(f"ERROR: config missing at {args.config}", verbose=args.verbose)
        return 1

    try:
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        log(f"ERROR: config JSON invalid: {e}", verbose=args.verbose)
        return 1

    plaud_cfg = config.get("plaud") or {}
    method = plaud_cfg.get("method", "mcp_only")

    if method == "mcp_only":
        log(f"method=mcp_only → Playwright runner disabled (intentional)",
            verbose=args.verbose)
        return 2

    # Heartbeat surface (optional).
    hb_cfg = config.get("gallant_heartbeat") or {}
    hb_url = hb_cfg.get("ping_base_url") if hb_cfg.get("enabled") else None
    # Reuse the lunch/eod check by source label; manual runs don't ping.
    hb_uuid = None
    if hb_url and args.source in {"lunch", "eod"}:
        hb_uuid = (hb_cfg.get("checks") or {}).get(args.source)

    _heartbeat(hb_url, hb_uuid, "start")

    # Lazy-import so a missing playwright package doesn't crash the module.
    try:
        from plaud_playwright import fetch_new_summaries, PlaywrightUnavailable
    except ImportError as e:
        log(f"PLAYWRIGHT UNAVAILABLE: {e}", verbose=args.verbose)
        _heartbeat(hb_url, hb_uuid, "3")
        return 3

    _clear_staging(args.verbose)

    processed = _read_processed_file_ids(config)
    log(f"processed file IDs in state: {len(processed)}", verbose=args.verbose)

    try:
        results, err = fetch_new_summaries(
            config,
            since_file_ids=processed,
            log_fn=lambda m: log(m, verbose=args.verbose),
        )
    except PlaywrightUnavailable:
        log("PLAYWRIGHT UNAVAILABLE (raised)", verbose=args.verbose)
        _heartbeat(hb_url, hb_uuid, "3")
        return 3

    # Write manifest regardless — the skill reads it to know what staged.
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": args.source,
        "method": method,
        "results": results,
        "error": err,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    log(f"manifest written: {len(results)} staged, error={err!r}",
        verbose=args.verbose)

    if err is None:
        _heartbeat(hb_url, hb_uuid, "0")
        log("=== plaud_playwright_runner.py complete (ok) ===", verbose=args.verbose)
        return 0

    # Map error categories to exit codes for the parent runner.
    if err == "session_expired":
        _heartbeat(hb_url, hb_uuid, "4")
        log("=== runner exiting: session expired ===", verbose=args.verbose)
        return 4
    if err.startswith("selector_missing"):
        _heartbeat(hb_url, hb_uuid, "5")
        log("=== runner exiting: selector mismatch ===", verbose=args.verbose)
        return 5
    if err == "rate_limited":
        _heartbeat(hb_url, hb_uuid, "6")
        log("=== runner exiting: rate limited ===", verbose=args.verbose)
        return 6

    _heartbeat(hb_url, hb_uuid, "9")
    log("=== runner exiting: unrecognized error ===", verbose=args.verbose)
    return 9


if __name__ == "__main__":
    sys.exit(main())
