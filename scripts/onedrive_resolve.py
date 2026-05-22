"""
onedrive_resolve.py — Locate the user's OneDrive sync folder on Windows or Mac.

Strategy:
  Windows:
    1. Read %OneDrive% / %OneDriveCommercial% / %OneDriveConsumer% env vars.
    2. Fall back to common defaults under %USERPROFILE% (e.g., 'OneDrive',
       'OneDrive - <Tenant>').
    3. Read registry hint if available.
  Mac:
    1. Read $OneDrive env var (rare but possible).
    2. Fall back to ~/Library/CloudStorage/OneDrive*.
    3. Fall back to ~/OneDrive (older Mac OneDrive client).

Used by:
  - install.ps1 / install.sh during setup to confirm OneDrive is present
  - the meetings-digest skill at runtime to resolve the output base folder

Usage from CLI:
    python3 onedrive_resolve.py                      # print best candidate
    python3 onedrive_resolve.py --all                # list every candidate found
    python3 onedrive_resolve.py --check "<path>"     # verify a specific path
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def windows_candidates() -> list[Path]:
    cands: list[Path] = []
    seen: set[str] = set()

    # 1. Environment variables (most reliable on Win)
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        val = os.environ.get(var)
        if val:
            p = Path(val).expanduser().resolve()
            key = str(p).lower()
            if key not in seen:
                seen.add(key)
                cands.append(p)

    # 2. %USERPROFILE% defaults
    profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    for name in ("OneDrive", "OneDrive - Personal"):
        p = profile / name
        key = str(p).lower()
        if p.exists() and key not in seen:
            seen.add(key)
            cands.append(p)

    # 2b. Glob for "OneDrive - <Tenant>" patterns
    if profile.exists():
        try:
            for child in profile.iterdir():
                if child.is_dir() and child.name.startswith("OneDrive"):
                    key = str(child).lower()
                    if key not in seen:
                        seen.add(key)
                        cands.append(child.resolve())
        except OSError:
            pass

    return cands


def mac_candidates() -> list[Path]:
    cands: list[Path] = []
    seen: set[str] = set()

    # 1. Env var (rare on Mac but check)
    val = os.environ.get("OneDrive")
    if val:
        p = Path(val).expanduser().resolve()
        if str(p).lower() not in seen:
            seen.add(str(p).lower())
            cands.append(p)

    # 2. ~/Library/CloudStorage/OneDrive* (modern Mac OneDrive client)
    cloud = Path.home() / "Library" / "CloudStorage"
    if cloud.exists():
        try:
            for child in cloud.iterdir():
                if child.is_dir() and child.name.startswith("OneDrive"):
                    key = str(child).lower()
                    if key not in seen:
                        seen.add(key)
                        cands.append(child.resolve())
        except OSError:
            pass

    # 3. ~/OneDrive (older Mac client)
    legacy = Path.home() / "OneDrive"
    if legacy.exists() and str(legacy).lower() not in seen:
        seen.add(str(legacy).lower())
        cands.append(legacy.resolve())

    return cands


def detect_candidates() -> list[Path]:
    if sys.platform.startswith("win"):
        return windows_candidates()
    if sys.platform == "darwin":
        return mac_candidates()
    return []


def best_candidate() -> Path | None:
    cands = detect_candidates()
    # Prefer ones that exist as a directory + are writable
    for p in cands:
        if p.is_dir() and os.access(p, os.W_OK):
            return p
    # Fall back to first candidate (may not yet exist; installer can create)
    return cands[0] if cands else None


def check_path(path: str) -> dict:
    p = Path(path).expanduser()
    return {
        "path": str(p),
        "exists": p.exists(),
        "is_dir": p.is_dir() if p.exists() else False,
        "writable": p.exists() and os.access(p, os.W_OK),
        "looks_like_onedrive": "OneDrive" in p.name or any("OneDrive" in part for part in p.parts),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="List every candidate found, JSON")
    parser.add_argument("--check", help="Verify a specific path is a usable OneDrive folder")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.check:
        result = check_path(args.check)
        print(json.dumps(result, indent=2))
        return 0 if result["writable"] else 1

    if args.all:
        cands = detect_candidates()
        out = []
        for p in cands:
            out.append({
                "path": str(p),
                "exists": p.exists(),
                "is_dir": p.is_dir() if p.exists() else False,
                "writable": p.exists() and os.access(p, os.W_OK),
            })
        print(json.dumps(out, indent=2))
        return 0

    p = best_candidate()
    if not p:
        sys.stderr.write("No OneDrive folder detected. Install OneDrive + sign in first.\n")
        return 1
    if args.json:
        print(json.dumps({"path": str(p), "exists": p.exists()}))
    else:
        print(str(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
