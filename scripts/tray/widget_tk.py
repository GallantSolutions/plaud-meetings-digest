"""
widget_tk.py — Native Tkinter widget for the Plaud tray on Windows.

Replaces widget.py's pywebview UI on Windows where pywebview's WebView2 COM
initialization on the main thread blocks pystray's Shell_NotifyIcon
registration. Tkinter ships with Python, doesn't fight pystray, and renders
native widgets.

Same Api surface (refresh / mark_done / open_source / open_onedrive) — the
Api class is reused verbatim from widget.py. Only the rendering changes.

Threading:
  - Tk mainloop runs on the main thread (where _root.mainloop() is called)
  - Pystray runs as a daemon thread (its run() is blocking but doesn't fight Tk)
  - Cross-thread Tk operations are routed via _root.after(0, ...) — Tk widget
    operations are not thread-safe and must execute on the Tk thread.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .widget import Api, _open_path_in_os  # reuse Api + helpers


# Brand tokens
KW_BLUE = "#224088"
KW_GOLD = "#e5ac23"
BUCKET_LABELS = {
    "KP": "Kingsway Pharma",
    "CM": "Committee",
    "CH": "Church",
    "PE": "Personal",
    "OT": "Other",
}


_root: tk.Tk | None = None
_window: tk.Toplevel | None = None
_scroll_frame: ttk.Frame | None = None
_api: Api | None = None


def get_api() -> Api:
    global _api
    if _api is None:
        _api = Api()
    return _api


def create_window() -> None:
    """Create the hidden Tk root + widget Toplevel. Idempotent."""
    global _root, _window, _scroll_frame
    if _window is not None:
        return

    _root = tk.Tk()
    _root.withdraw()  # hide root, only Toplevel is shown

    _window = tk.Toplevel(_root)
    _window.title("Plaud - This week")
    _window.geometry("440x600+200+200")
    _window.minsize(400, 400)
    _window.protocol("WM_DELETE_WINDOW", hide)
    _window.withdraw()  # hidden until tray click reveals it

    # Header bar
    header = tk.Frame(_window, bg=KW_BLUE, height=44)
    header.pack(fill=tk.X, side=tk.TOP)
    header.pack_propagate(False)
    tk.Label(
        header, text="Plaud - This week",
        bg=KW_BLUE, fg="white",
        font=("Segoe UI", 12, "bold"),
    ).pack(side=tk.LEFT, padx=12, pady=10)
    tk.Button(
        header, text="Open OneDrive",
        command=_on_open_onedrive,
        bg="white", relief="flat", cursor="hand2",
    ).pack(side=tk.RIGHT, padx=4, pady=8)
    tk.Button(
        header, text="Refresh",
        command=lambda: _refresh(),
        bg="white", relief="flat", cursor="hand2",
    ).pack(side=tk.RIGHT, padx=4, pady=8)

    # Scrollable content area
    body = tk.Frame(_window)
    body.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(body, highlightthickness=0, bg="white")
    scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    _scroll_frame = ttk.Frame(canvas)

    _scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas_window_id = canvas.create_window((0, 0), window=_scroll_frame, anchor="nw")
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(canvas_window_id, width=e.width)
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Mouse wheel scroll support
    def _on_mousewheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    _refresh()


def _refresh() -> None:
    """Reload items and rebuild the list. Must run on Tk thread."""
    if _window is None or _scroll_frame is None:
        return
    try:
        data = get_api().refresh()
    except Exception as e:
        _show_error(f"Refresh failed: {e}")
        return

    # Clear existing children
    for child in _scroll_frame.winfo_children():
        child.destroy()

    items = data.get("items", [])
    if not items:
        tk.Label(
            _scroll_frame, text="No open action items.",
            fg="gray", font=("Segoe UI", 10),
            pady=24, bg="white",
        ).pack()
        return

    # Group by bucket, preserve order
    by_bucket: dict[str, list] = {}
    for item in items:
        bucket = item.get("bucket", "OT")
        by_bucket.setdefault(bucket, []).append(item)

    for bucket in ("KP", "CM", "CH", "PE", "OT"):
        if bucket not in by_bucket:
            continue
        # Section header
        section_header = tk.Label(
            _scroll_frame, text=BUCKET_LABELS.get(bucket, bucket),
            font=("Segoe UI", 10, "bold"), fg=KW_BLUE, bg="white",
            anchor="w", padx=12, pady=(10, 4),
        )
        section_header.pack(fill=tk.X)
        for item in by_bucket[bucket]:
            _render_item(_scroll_frame, item)


def _render_item(parent, item: dict) -> None:
    """Render a single action item as a checkbox row."""
    row = tk.Frame(parent, bg="white")
    row.pack(fill=tk.X, padx=10, pady=2)

    item_id = item.get("id", "")
    item_text = item.get("text", "")
    item_bucket = item.get("bucket", "")
    item_source = item.get("source_meeting", "")
    item_done = bool(item.get("done", False))

    done_var = tk.BooleanVar(value=item_done)

    def on_toggle():
        try:
            get_api().mark_done(
                item_id, done_var.get(),
                text=item_text, bucket=item_bucket,
                source_meeting=item_source,
            )
        except Exception as e:
            _show_error(f"Mark-done failed: {e}")

    cb = tk.Checkbutton(
        row, variable=done_var, command=on_toggle,
        bg="white", activebackground="white",
        anchor="n",
    )
    cb.pack(side=tk.LEFT, anchor="n", pady=(2, 0))

    text_col = tk.Frame(row, bg="white")
    text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

    text_label = tk.Label(
        text_col, text=item_text,
        wraplength=340, justify="left", anchor="w",
        bg="white", font=("Segoe UI", 9),
    )
    text_label.pack(anchor="w", fill=tk.X)

    if item_source:
        src_label = tk.Label(
            text_col, text=f"from: {item_source}",
            fg="gray", anchor="w",
            bg="white", font=("Segoe UI", 8),
        )
        src_label.pack(anchor="w", fill=tk.X)


def _show_error(msg: str) -> None:
    if _scroll_frame is None:
        return
    tk.Label(
        _scroll_frame, text=msg,
        fg="red", bg="white", padx=12, pady=8,
    ).pack(fill=tk.X)


def _on_open_onedrive() -> None:
    try:
        get_api().open_onedrive()
    except Exception:
        pass


def show() -> None:
    """Reveal the window. Safe to call from any thread (routes to Tk via after)."""
    if _root is None or _window is None:
        return
    def _do_show():
        _refresh()
        _window.deiconify()
        _window.lift()
        _window.focus_force()
    try:
        _root.after(0, _do_show)
    except Exception:
        pass


def hide() -> None:
    if _window is not None:
        _window.withdraw()


def notify_change() -> None:
    """Called from watcher (non-Tk thread). Refresh via after()."""
    if _root is None:
        return
    try:
        _root.after(0, _refresh)
    except Exception:
        pass


def run_mainloop() -> None:
    """Block on the Tk event loop. Call from the main thread."""
    if _root is None:
        create_window()
    if _root is not None:
        _root.mainloop()
