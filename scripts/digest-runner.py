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

    # ----------------------------------------------------------------------
    # v2.5.0 — Playwright pre-fetch (opt-in via config.plaud.method).
    # Only fires for meetings-digest source runs (lunch/eod), never for
    # weekly-rollup (rollup synthesizes from already-staged content).
    # ----------------------------------------------------------------------
    plaud_method = (config.get("plaud") or {}).get("method", "mcp_only")
    runs_digest = "meetings-digest" in skills
    if plaud_method != "mcp_only" and runs_digest:
        runner_script = Path(__file__).resolve().parent / "plaud_playwright_runner.py"
        if runner_script.exists():
            log(f"--- plaud_playwright_runner (method={plaud_method}, source={args.source}) ---")
            try:
                pw_result = subprocess.run(
                    [sys.executable, str(runner_script),
                     "--source", args.source,
                     "--config", str(CONFIG_PATH)],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10-min ceiling for Playwright fetch
                    env={**os.environ, "TERM": "dumb"},
                )
                if pw_result.stdout:
                    log(pw_result.stdout[-3000:])
                if pw_result.stderr:
                    log(f"playwright stderr: {pw_result.stderr[-1500:]}")
                # Exit-code map (see plaud_playwright_runner.py):
                #   0=ok, 2=disabled, 3=unavailable, 4=session_expired,
                #   5=selector_missing, 6=rate_limited, 9=error
                if pw_result.returncode == 0:
                    log("playwright_runner: ok (staging populated)")
                elif pw_result.returncode == 2:
                    log("playwright_runner: disabled (mcp_only)")
                elif pw_result.returncode == 3:
                    log("playwright_runner: unavailable — Claude/MCP will handle this run")
                elif pw_result.returncode == 4:
                    log("playwright_runner: SESSION EXPIRED — run playwright_setup.ps1 -ReAuth")
                elif pw_result.returncode == 5:
                    log("playwright_runner: SELECTOR MISMATCH — Plaud UI may have changed; re-codegen")
                elif pw_result.returncode == 6:
                    log("playwright_runner: rate-limited — falling back to MCP for this run")
                else:
                    log(f"playwright_runner: unexpected exit {pw_result.returncode} — falling back to MCP")
            except subprocess.TimeoutExpired:
                log("playwright_runner: TIMED OUT after 10 minutes — falling back to MCP for this run")
            except Exception as e:
                log(f"playwright_runner: invocation failed: {e} — falling back to MCP")
        else:
            log(f"plaud.method={plaud_method} but {runner_script.name} missing on disk; skipping")

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

    # Model pinning (v2.3.1+). Each skill gets a model + a fallback. Defaults
    # split by workload weight: per-meeting routing/title work is light (Sonnet
    # is plenty); weekly rollup is heavy synthesis for a pharma-grade exec
    # deliverable (Opus). Both fall back to Sonnet if the primary rate-limits.
    # Operators override per-skill via config.claude_models.<skill>.
    DEFAULT_MODELS = {
        "meetings-digest": {"model": "claude-sonnet-4-6", "fallback": "claude-sonnet-4-6"},
        "weekly-rollup":   {"model": "claude-opus-4-7",   "fallback": "claude-sonnet-4-6"},
    }
    config_models = config.get("claude_models", {}) or {}

    # Run each skill in one-shot mode. --dangerously-skip-permissions
    # auto-approves all tool calls in this scheduled (no-human) context.
    for skill in skills:
        skill_models = config_models.get(skill, DEFAULT_MODELS.get(skill, {}))
        model = skill_models.get("model", DEFAULT_MODELS.get(skill, {}).get("model"))
        fallback = skill_models.get("fallback", DEFAULT_MODELS.get(skill, {}).get("fallback"))

        cmd = [
            claude,
            "-p", f"/{skill}",
            "--dangerously-skip-permissions",
        ]
        if model:
            cmd.extend(["--model", model])
        if fallback and fallback != model:
            cmd.extend(["--fallback-model", fallback])
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
