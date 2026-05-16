"""
Cross-platform Hearthstone window detection.
Returns (x, y, width, height) of the game window, or None if not found.
"""
from __future__ import annotations
import sys
import logging
from typing import Optional

log = logging.getLogger(__name__)

HS_TITLE_PATTERNS = ["Hearthstone", "爐石戰記", "炉石传说"]


def find_hearthstone_window() -> Optional[tuple[int, int, int, int]]:
    """Return (x, y, w, h) or None."""
    if sys.platform == "win32":
        return _find_windows()
    elif sys.platform == "darwin":
        return _find_macos()
    else:
        return _find_pygetwindow()


def _find_windows() -> Optional[tuple[int, int, int, int]]:
    try:
        import ctypes
        import ctypes.wintypes

        EnumWindows      = ctypes.windll.user32.EnumWindows
        GetWindowTextW   = ctypes.windll.user32.GetWindowTextW
        GetWindowRect    = ctypes.windll.user32.GetWindowRect
        IsWindowVisible  = ctypes.windll.user32.IsWindowVisible

        result = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def callback(hwnd, _lp):
            if not IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(256)
            GetWindowTextW(hwnd, buf, 256)
            title = buf.value
            if any(p in title for p in HS_TITLE_PATTERNS):
                rect = ctypes.wintypes.RECT()
                GetWindowRect(hwnd, ctypes.byref(rect))
                result.append((rect.left, rect.top,
                                rect.right - rect.left,
                                rect.bottom - rect.top))
            return True

        EnumWindows(callback, 0)
        return result[0] if result else None

    except Exception as e:
        log.warning("Windows window finder failed: %s", e)
        return _find_pygetwindow()


def _find_macos() -> Optional[tuple[int, int, int, int]]:
    try:
        import subprocess, json
        # Use AppleScript to get window bounds
        script = """
        tell application "System Events"
          set hs to first process whose name contains "Hearthstone"
          set w to first window of hs
          set {ox, oy} to position of w
          set {ow, oh} to size of w
          return ox & "," & oy & "," & ow & "," & oh
        end tell
        """
        out = subprocess.check_output(["osascript", "-e", script], text=True).strip()
        parts = [int(v.strip()) for v in out.split(",")]
        if len(parts) == 4:
            return tuple(parts)  # type: ignore
    except Exception as e:
        log.warning("macOS window finder failed: %s", e)
    return _find_pygetwindow()


def _find_pygetwindow() -> Optional[tuple[int, int, int, int]]:
    try:
        import pygetwindow as gw
        for pattern in HS_TITLE_PATTERNS:
            wins = gw.getWindowsWithTitle(pattern)
            if wins:
                w = wins[0]
                return (w.left, w.top, w.width, w.height)
    except Exception as e:
        log.warning("pygetwindow failed: %s", e)
    return None
