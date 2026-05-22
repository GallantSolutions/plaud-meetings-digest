#!/usr/bin/env python3
"""
digest-runner.py — Headless entrypoint for scheduled (launchd) runs.

Invokes Claude Code in one-shot mode with the configured skill, logs output,
and exits. Used by the lunch / EOD / Monday-rollup launchd jobs; can also be
run manually:

    python3 ~/.claude/skills/meetings-digest/scripts/digest-runner.py \\
        --skill meetings-digest --source manual

Exit codes:
    0 — skill ran to completion successfully
    1 — config error / skill name invalid
    2 — Claude Code invocation failed
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import platform

CONFIG_PATH = Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json"

if platform.system() == "Windows":
    _local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    LOG_DIR = Path(_local_appdata) / "plaud-meetings-digest" / "logs"
else:
    LOG_DIR = Path.home() / "Library" / "Logs"
LOG_PATH = LOG_DIR / "plaud-meetings-digest.log"

ALLOWED_SKILLS = {"meetings-digest", "weekly-rollup"}


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n"
    with LOG_PATH.open("a") as f:
        f.write(line)
    print(line, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill",
        default=None,
        help="Single skill to invoke (legacy flag — prefer --skills). One of: meetings-digest, weekly-rollup",
    )
    parser.add_argument(
        "--skills",
        nargs="+",
        default=None,
        help="One or more skills to invoke IN SEQUENCE. e.g.: --skills meetings-digest weekly-rollup",
    )
    parser.add_argument(
        "--source",
        default="manual",
        help="Run-source label for logs (friday-rollup | manual | ad-hoc)",
    )
    args = parser.parse_args()

    if args.skills:
        skills = args.skills
    elif args.skill:
        skills = [args.skill]
    else:
        skills = ["meetings-digest"]

    for s in skills:
        if s not in ALLOWED_SKILLS:
            log(f"ERROR: unknown skill '{s}'. Allowed: {sorted(ALLOWED_SKILLS)}")
            return 1

    log(f"=== digest-runner.py starting (skills={skills}, source={args.source}) ===")

    if not CONFIG_PATH.exists():
        log(f"ERROR: config missing at {CONFIG_PATH}. Run install.sh.")
        return 1

    try:
        config = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as e:
        log(f"ERROR: config JSON invalid: {e}")
        return 1

    log(f"Destination: {config.get('destination', {}).get('type', 'unknown')}")

    claude = shutil.which("claude")
    if not claude:
        # Common install paths if `which` didn't find it.
        # Includes both Mac (Homebrew) and Windows (LocalAppData) locations.
        candidates = [
            "/opt/homebrew/bin/claude",
            "/usr/local/bin/claude",
            str(Path.home() / ".local" / "bin" / "claude"),
            # Windows
            str(Path.home() / "AppData" / "Local" / "Anthropic" / "claude-code" / "claude.exe"),
            str(Path.home() / "AppData" / "Local" / "Programs" / "claude-code" / "claude.exe"),
            "C:/Program Files/Anthropic/Claude/claude.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                claude = c
                break

    if not claude:
        log("ERROR: claude CLI not found on PATH. Run install.sh (Mac) or install.ps1 (Windows).")
        return 2

    log(f"Using claude at: {claude}")

    # Run each skill in one-shot mode. --dangerously-skip-permissions
    # auto-approves all tool calls in this scheduled (no-human) context.
    for skill in skills:
        cmd = [
            claude,
            "-p", f"/{skill}",
            "--dangerously-skip-permissions",
        ]
        log(f"Invoking: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,  # 15-min ceiling per skill
                env={**os.environ, "TERM": "dumb"},
            )
        except subprocess.TimeoutExpired:
            log(f"ERROR: claude /{skill} timed out after 15 minutes")
            return 2
        except Exception as e:
            log(f"ERROR: claude /{skill} invocation failed: {e}")
            return 2

        if result.stdout:
            log(f"--- /{skill} stdout ---")
            log(result.stdout[-4000:])
        if result.stderr:
            log(f"--- /{skill} stderr ---")
            log(result.stderr[-2000:])

        if result.returncode != 0:
            log(f"ERROR: claude /{skill} exited with code {result.returncode}; aborting chain")
            return 2

        log(f"--- /{skill} complete ---")

    log(f"=== digest-runner.py complete (skills={skills}) ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
