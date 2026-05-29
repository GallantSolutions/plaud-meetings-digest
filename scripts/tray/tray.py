"""
tray.py — System-tray entry point for the Plaud tray widget.

Runs as a long-lived background process:
  - Pystray icon in the Windows system tray (or Mac menu bar)
  - Left-click toggles the widget window
  - Right-click menu: Refresh now / Open OneDrive folder / Quit
  - Background watchdog observer watches the OneDrive "Plaud Meetings"
    folder; on any .docx add/modify, the widget refreshes automatically.

Designed to run via pythonw.exe on Windows (no console window). On Mac
it's used for development only — start with `python3 -m scripts.tray.tray`.

The widget window is hidden until the user clicks the tray icon. State
auto-resets every Monday (new ISO week) — see state.py.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

# Run as a package so relative imports work even when invoked as a script
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "scripts.tray"

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("pystray + Pillow not installed. Run: python3 -m pip install pystray Pillow")

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    raise SystemExit("watchdog not installed. Run: python3 -m pip install watchdog")

if sys.platform == "win32":
    # Windows: Tk widget (pywebview + pystray can't share the main thread
    # on Windows — WebView2 COM init blocks Shell_NotifyIcon registration).
    from . import widget_tk as widget_mod  # type: ignore[no-redef]
else:
    # macOS / Linux: pywebview widget renders the HTML UI fine.
    import webview  # noqa: F401  (re-imported below for mainloop access)
    from . import widget as widget_mod  # type: ignore[no-redef]

from .config import load_config, resolve_onedrive_base


HERE = Path(__file__).resolve().parent
LOGO_PNG = HERE / "assets" / "kingsway-logo.png"

# Brand tokens — must match widget.html
KW_BLUE = "#224088"
KW_GOLD = "#e5ac23"
# Brand red from --alert. White-on-#b73838 is ~5.4:1 — comfortably AA at
# any text size. Red is the universal "needs attention" signal; reads cleanly
# on the dark navy of the logo and against any Windows taskbar theme.
BADGE_PILL_COLOR = "#b73838"
BADGE_TEXT_COLOR = "#ffffff"

# Native asset size — render high then let Windows downscale to the
# 16/20/24/32px the tray actually paints. Higher native means super-sampled
# anti-aliasing on the digit, no jaggies at any DPI. 256 is the standard
# Windows .ico high-res slot.
ICON_NATIVE_PX = 256


# ── File watcher ────────────────────────────────────────────────────────

def _refresh_with_badge() -> None:
    """Coalesced refresh: re-render the widget AND re-paint the tray badge.
    Used by the watchdog debouncer and by mark_done callbacks."""
    widget_mod.notify_change()
    refresh_badge()


class DocxChangeHandler(FileSystemEventHandler):
    """Trigger a widget refresh whenever a .docx is added/modified.
    Debounces bursts (OneDrive sync rewrites the same file multiple times)
    by coalescing events within a 750ms window."""

    def __init__(self) -> None:
        super().__init__()
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _coalesce(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(0.75, _refresh_with_badge)
            self._timer.daemon = True
            self._timer.start()

    def on_any_event(self, event) -> None:
        if event.is_directory:
            return
        path = (getattr(event, "src_path", "") or "").lower()
        if not path.endswith(".docx"):
            return
        # Skip Office's lock files
        if "/~$" in path or "\\~$" in path:
            return
        self._coalesce()


def start_watcher(onedrive_base: Path | None) -> Observer | None:
    if onedrive_base is None:
        return None
    plaud_root = onedrive_base / "Plaud Meetings"
    if not plaud_root.exists():
        return None
    observer = Observer()
    observer.schedule(DocxChangeHandler(), str(plaud_root), recursive=True)
    observer.daemon = True
    observer.start()
    return observer


# ── Tray icon ───────────────────────────────────────────────────────────

def _load_base_icon() -> Image.Image:
    """Load the base logo at ICON_NATIVE_PX so badge text can be rendered
    at a generous font size and stay crisp when Windows downscales to the
    16/20/24/32 the tray actually paints."""
    if LOGO_PNG.exists():
        img = Image.open(str(LOGO_PNG)).convert("RGBA")
        if img.size != (ICON_NATIVE_PX, ICON_NATIVE_PX):
            img = img.resize((ICON_NATIVE_PX, ICON_NATIVE_PX), Image.LANCZOS)
        return img
    # Fallback: solid royal-blue square
    return Image.new("RGBA", (ICON_NATIVE_PX, ICON_NATIVE_PX), KW_BLUE)


def _badge_font(size: int) -> ImageFont.ImageFont:
    """Try a few common system font paths; fall back to PIL's default.
    Default font is bitmap and ignores `size`, so for crisp digits we
    really want a TTF. These paths cover Windows + Mac defaults."""
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",          # Segoe UI Bold (Windows)
        "C:/Windows/Fonts/arialbd.ttf",           # Arial Bold (Windows fallback)
        "/System/Library/Fonts/SFNS.ttf",         # San Francisco (modern macOS)
        "/System/Library/Fonts/Helvetica.ttc",    # macOS fallback
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


_SUPERSAMPLE = 3  # Render badge layer at 3× target dims, downscale with
                  # LANCZOS for ultra-clean anti-aliasing on pill + glyphs.


def _render_icon_with_badge(base: Image.Image, count: int) -> Image.Image:
    """Composite a red pill onto the top-right of the base icon showing
    the open count. Super-samples the badge layer 3× and downscales with
    LANCZOS so both the pill arc and the digit edges are smooth at any
    display size. Returns the base unmodified when count<=0."""
    if count <= 0:
        return base
    img = base.copy()

    text = str(count) if count < 100 else "99+"
    # Font sizes proportional to ICON_NATIVE_PX=256, then multiplied by
    # SUPERSAMPLE for the high-res render pass.
    single_digit_pt = ICON_NATIVE_PX * 21 // 64   # ~84pt at 256
    multi_digit_pt  = ICON_NATIVE_PX * 18 // 64   # ~72pt at 256
    base_font_pt = single_digit_pt if len(text) == 1 else multi_digit_pt
    font = _badge_font(base_font_pt * _SUPERSAMPLE)

    # Measure text on a throwaway draw context at the super-sampled size
    measure_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    measure_draw = ImageDraw.Draw(measure_img)
    try:
        bbox = measure_draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_ox, text_oy = -bbox[0], -bbox[1]
    except AttributeError:
        text_w, text_h = measure_draw.textsize(text, font=font)
        text_ox = text_oy = 0

    pad_x_base = (ICON_NATIVE_PX * 8 // 64) if len(text) > 1 else (ICON_NATIVE_PX * 4 // 64)
    min_dim_base = ICON_NATIVE_PX * 24 // 64
    pill_h_pad_base = ICON_NATIVE_PX * 6 // 64

    pad_x = pad_x_base * _SUPERSAMPLE
    min_dim = min_dim_base * _SUPERSAMPLE
    pill_h_pad = pill_h_pad_base * _SUPERSAMPLE

    pill_w = max(text_w + pad_x * 2, min_dim)
    pill_h = max(text_h + pill_h_pad, min_dim)

    # Render pill + text into a super-sampled transparent layer
    layer = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(
        (0, 0, pill_w - 1, pill_h - 1),
        radius=pill_h // 2, fill=BADGE_PILL_COLOR,
    )
    glyph_x = (pill_w - text_w) // 2 + text_ox
    glyph_y = (pill_h - text_h) // 2 + text_oy
    layer_draw.text((glyph_x, glyph_y), text, fill=BADGE_TEXT_COLOR, font=font)

    # Downsample to target resolution — super-sampled anti-aliasing
    target_w = pill_w // _SUPERSAMPLE
    target_h = pill_h // _SUPERSAMPLE
    layer = layer.resize((target_w, target_h), Image.LANCZOS)

    # Composite onto the base icon, top-right with a small edge inset
    edge = ICON_NATIVE_PX // 64
    paste_x = img.size[0] - target_w - edge
    paste_y = edge
    img.alpha_composite(layer, (paste_x, paste_y))
    return img


_icon: pystray.Icon | None = None
_base_icon: Image.Image | None = None


def refresh_badge() -> None:
    """Re-query the open count + re-render the tray icon with the badge.
    Safe to call from any thread; no-op until _icon is built."""
    if _icon is None or _base_icon is None:
        return
    try:
        count = widget_mod.get_api().open_count()
    except Exception:
        count = 0
    try:
        _icon.icon = _render_icon_with_badge(_base_icon, count)
        # Tooltip text is the universal fallback — works even if the
        # composited image fails to render on some Windows themes.
        if count <= 0:
            _icon.title = "Plaud — all clear"
        elif count == 1:
            _icon.title = "Plaud — 1 open item"
        else:
            _icon.title = f"Plaud — {count} open items"
    except Exception:
        pass


def _on_left_click(icon: pystray.Icon, item) -> None:
    """Toggle the widget window."""
    widget_mod.show()


def _on_refresh(icon: pystray.Icon, item) -> None:
    _refresh_with_badge()


def _on_open_folder(icon: pystray.Icon, item) -> None:
    widget_mod.get_api().open_onedrive()


def _on_quit(icon: pystray.Icon, item) -> None:
    icon.stop()
    # The UI mainloop (webview.start or Tk.mainloop) blocks the main thread.
    # Killing the icon thread doesn't stop it — we need to stop the mainloop.
    try:
        if sys.platform == "win32":
            # Tk: schedule root.quit() on the Tk thread
            if getattr(widget_mod, "_root", None) is not None:
                widget_mod._root.after(0, widget_mod._root.quit)
        else:
            # pywebview: destroy the window
            if getattr(widget_mod, "_window", None) is not None:
                widget_mod._window.destroy()
    except Exception:
        pass
    sys.exit(0)


def build_tray_icon() -> pystray.Icon:
    global _base_icon
    _base_icon = _load_base_icon()
    menu = pystray.Menu(
        pystray.MenuItem("Open", _on_left_click, default=True, visible=False),
        pystray.MenuItem("Refresh now", _on_refresh),
        pystray.MenuItem("Open OneDrive folder", _on_open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _on_quit),
    )
    return pystray.Icon("plaud-tray", _base_icon, "Plaud — This week", menu)


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    onedrive_base = resolve_onedrive_base(config)

    # Watcher (background thread)
    start_watcher(onedrive_base)

    # Build the tray icon up front
    global _icon
    _icon = build_tray_icon()

    # Create the widget window (hidden initially — tray click reveals it)
    widget_mod.create_window()

    if sys.platform == "win32":
        # Windows: Tk widget. Tkinter mainloop on main thread, pystray on
        # daemon. (Pywebview is not used on Windows — its WebView2 COM init
        # blocks pystray's Shell_NotifyIcon registration on the main thread,
        # and pywebview refuses to run on a non-main thread.)
        def tray_thread() -> None:
            try:
                _icon.run(setup=lambda _icn: refresh_badge())
            except Exception:
                pass
        t = threading.Thread(target=tray_thread, name="tray", daemon=True)
        t.start()
        widget_mod.run_mainloop()  # blocks main thread (Tk mainloop)
    else:
        # macOS / Linux: pywebview widget. webview.start() on main thread,
        # pystray as daemon.
        def tray_thread() -> None:
            try:
                _icon.run(setup=lambda _icn: refresh_badge())
            except Exception:
                pass
        t = threading.Thread(target=tray_thread, name="tray", daemon=True)
        t.start()
        import webview as _webview
        _webview.start()  # blocks main thread


if __name__ == "__main__":
    main()
