"""
widget.py — pywebview window + JS API bridge for the Plaud tray widget.

Renders widget.html in a 400×560 borderless window. Exposes a small JS API
the page calls to:
  - refresh()             → re-scan OneDrive docs, return items + stats
  - mark_done(id, done)   → persist toggle, return updated items + stats
  - open_source(path)     → open a .docx in the OS default app
  - open_onedrive()       → open the "Plaud Meetings" folder

The window is hidden until the tray icon is clicked. Closing the window
(X) hides it rather than quitting; only the tray menu's Quit kills the
process.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import webview
except ImportError:
    raise SystemExit("pywebview not installed. Run: python3 -m pip install pywebview")

from . import parser, state
from .config import load_config, resolve_onedrive_base


HERE = Path(__file__).resolve().parent
WIDGET_HTML = HERE / "widget.html"
LOGO_PNG = HERE / "assets" / "kingsway-logo.png"


def _logo_data_uri() -> str:
    if not LOGO_PNG.exists():
        return ""
    encoded = base64.b64encode(LOGO_PNG.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_html() -> str:
    raw = WIDGET_HTML.read_text(encoding="utf-8")
    return raw.replace("{{KINGSWAY_LOGO_DATA_URI}}", _logo_data_uri())


def _open_path_in_os(path: str) -> None:
    """Open a file or folder in the OS default app."""
    if not path:
        return
    p = Path(path)
    if not p.exists():
        return
    if sys.platform == "win32":
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(p)], check=False)
    else:
        subprocess.run(["xdg-open", str(p)], check=False)


class Api:
    """Methods exposed to widget.html via pywebview's js_api."""

    def __init__(self) -> None:
        self._config = load_config()
        self._onedrive_base = resolve_onedrive_base(self._config)

    def _items_and_stats(self) -> dict[str, Any]:
        # Clear out items that were ratified by Friday's rollup. Cheap,
        # idempotent, lets the Done tab self-empty after the rollup fires.
        state.clear_done_after_rollup()
        if not self._onedrive_base:
            return {"items": [], "stats": state.stats([])}
        raw = parser.collect_open_items(self._config, self._onedrive_base)
        items = state.annotate(raw)
        return {"items": items, "stats": state.stats(items)}

    def refresh(self) -> dict[str, Any]:
        # Reload config in case it was edited between scans
        self._config = load_config()
        self._onedrive_base = resolve_onedrive_base(self._config)
        return self._items_and_stats()

    def mark_done(self, item_id: str, done: bool,
                  text: str = "", bucket: str = "", source_meeting: str = "") -> dict[str, Any]:
        # text/bucket/source_meeting carry through so the rollup bridge
        # can correlate this closure back to a state_store item_id.
        state.set_done(item_id, bool(done), text=text, bucket=bucket,
                       source_meeting=source_meeting)
        result = self._items_and_stats()
        # Repaint the tray badge so the count drops immediately, not on
        # next watchdog event. Late-import to avoid a circular dep between
        # widget and tray modules.
        try:
            from . import tray as tray_mod
            tray_mod.refresh_badge()
        except Exception:
            pass
        return result

    def open_source(self, path: str) -> bool:
        _open_path_in_os(path)
        return True

    def open_onedrive(self) -> bool:
        if not self._onedrive_base:
            return False
        plaud_root = self._onedrive_base / "Plaud Meetings"
        target = plaud_root if plaud_root.exists() else self._onedrive_base
        _open_path_in_os(str(target))
        return True

    def open_count(self) -> int:
        """Tray-icon helper: how many open items right now, no UI work."""
        try:
            return int(self._items_and_stats().get("stats", {}).get("open", 0))
        except Exception:
            return 0


_window = None
_api = None


def get_api() -> Api:
    global _api
    if _api is None:
        _api = Api()
    return _api


def create_window() -> Any:
    """Create the pywebview window (hidden initially). Returns the Window handle."""
    global _window
    if _window is not None:
        return _window
    api = get_api()
    _window = webview.create_window(
        title="Plaud — This week",
        html=_render_html(),
        js_api=api,
        width=400,
        height=560,
        resizable=False,
        frameless=False,
        easy_drag=False,
        hidden=True,
        on_top=True,
    )
    # Hide instead of destroy when the X is pressed.
    _window.events.closing += _on_closing
    return _window


def _on_closing() -> bool:
    """Returning False cancels the close — we hide instead."""
    if _window is not None:
        _window.hide()
    return False


def show() -> None:
    """Reveal the window (called by tray click)."""
    if _window is None:
        return
    _window.show()
    # Force a refresh via JS so the list reflects any docs that landed
    # while the window was hidden.
    try:
        _window.evaluate_js("if (window.pywebview && window.pywebview.api) { pull(); }")
    except Exception:
        pass


def hide() -> None:
    if _window is not None:
        _window.hide()


def notify_change() -> None:
    """Called from the file watcher — re-render the list."""
    if _window is None:
        return
    try:
        _window.evaluate_js("if (window.pywebview && window.pywebview.api) { pull(); }")
    except Exception:
        pass
