"""
config.py — Thin loader bridging the tray widget to the existing
plaud-meetings-digest installation.

Reuses the same config.json that docx_writer.py and digest-runner.py read,
and reuses onedrive_resolve.py for OneDrive base discovery. No duplication
of platform-specific path logic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Walk up: scripts/tray/config.py → scripts/ is the parent so we can import sibling modules
_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import onedrive_resolve  # noqa: E402 — import after sys.path adjustment


CONFIG_PATH = Path.home() / ".claude" / "skills" / "meetings-digest" / "config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_onedrive_base(config: dict | None = None) -> Path | None:
    """Return the OneDrive root path. Prefer the operator-configured value;
    fall back to platform discovery."""
    config = config or load_config()
    cfg_path = (config.get("destination") or {}).get("onedrive_folder")
    if cfg_path:
        p = Path(cfg_path).expanduser()
        if p.exists():
            # config stores the Plaud Meetings folder; the tray expects the
            # OneDrive root. Normalize: if it ends in "Plaud Meetings", drop it.
            if p.name == "Plaud Meetings":
                return p.parent
            return p
    # Fall back to platform discovery
    cands = onedrive_resolve.windows_candidates() if sys.platform == "win32" else onedrive_resolve.mac_candidates()
    for c in cands:
        if c.exists():
            return c
    return None
