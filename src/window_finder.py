"""
Cross-platform Hearthstone window detection.
Returns (x, y, width, height) of the game window.

Strategy order (macOS):
  1. Quartz CGWindowList  — works for any window including Metal/fullscreen
  2. AppleScript bounds   — works for windowed mode
  3. Primary screen size  — safe fallback (overlay covers whole screen)

Strategy order (Windows):
  1. Win32 EnumWindows
  2. Primary screen fallback
"""
from __future__ import annotations
import sys
import logging
from typing import Optional

log = logging.getLogger(__name__)

HS_PROCESS_NAMES = ["Hearthstone"]
HS_TITLE_PATTERNS = ["Hearthstone", "爐石戰記", "炉石传说"]


def find_hearthstone_window() -> Optional[tuple[int, int, int, int]]:
    """Return (x, y, w, h) or None if the game is not running."""
    if sys.platform == "win32":
        return _find_windows()
    elif sys.platform == "darwin":
        return _find_macos()
    return _screen_fallback()


# ── macOS ─────────────────────────────────────────────────────────────────────

def _find_macos() -> Optional[tuple[int, int, int, int]]:
    result = _quartz_find() or _applescript_find()
    if result:
        return result
    # If HS is running but window isn't reachable (fullscreen Metal), cover screen
    if _hs_process_running():
        log.info("Hearthstone running in fullscreen — using full-screen overlay")
        return _screen_fallback()
    return None


def _quartz_find() -> Optional[tuple[int, int, int, int]]:
    """Use Quartz CGWindowList to find the Hearthstone window."""
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )
        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )
        if not windows:
            return None
        for win in windows:
            owner = win.get("kCGWindowOwnerName", "")
            name  = win.get("kCGWindowName", "") or ""
            if "Hearthstone" not in owner and not any(p in name for p in HS_TITLE_PATTERNS):
                continue
            bounds = win.get("kCGWindowBounds")
            if not bounds:
                continue
            x = int(bounds.get("X", 0))
            y = int(bounds.get("Y", 0))
            w = int(bounds.get("Width", 0))
            h = int(bounds.get("Height", 0))
            if w > 100 and h > 100:
                log.info("Found HS via Quartz: %dx%d at (%d,%d)", w, h, x, y)
                return (x, y, w, h)
    except Exception as e:
        log.debug("Quartz window finder skipped: %s", e)
    return None


def _applescript_find() -> Optional[tuple[int, int, int, int]]:
    """
    AppleScript fallback — works for windowed (non-fullscreen) Hearthstone.
    Uses `position` and `size` which return separate lists; we concatenate them.
    """
    import subprocess
    # Ask for position and size as separate statements so we don't rely on
    # string concatenation (which fails with AppleScript integer coercion).
    script = r"""
tell application "System Events"
    set procs to every process whose name contains "Hearthstone"
    if (count of procs) = 0 then return ""
    set hs to item 1 of procs
    if (count of windows of hs) = 0 then return ""
    set w to window 1 of hs
    set pos  to position of w
    set sz   to size of w
    set ox to item 1 of pos
    set oy to item 2 of pos
    set ow to item 1 of sz
    set oh to item 2 of sz
    return (ox as string) & "," & (oy as string) & "," & (ow as string) & "," & (oh as string)
end tell
"""
    try:
        out = subprocess.check_output(
            ["osascript", "-e", script],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
        if not out:
            return None
        parts = [int(v.strip()) for v in out.split(",") if v.strip()]
        if len(parts) == 4 and parts[2] > 100 and parts[3] > 100:
            log.info("Found HS via AppleScript: %dx%d at (%d,%d)",
                     parts[2], parts[3], parts[0], parts[1])
            return (parts[0], parts[1], parts[2], parts[3])
    except Exception as e:
        log.debug("AppleScript window finder skipped: %s", e)
    return None


def _hs_process_running() -> bool:
    """Check whether a Hearthstone process is alive (macOS)."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["pgrep", "-x", "Hearthstone"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return bool(out)
    except Exception:
        return False


# ── Windows ───────────────────────────────────────────────────────────────────

def _find_windows() -> Optional[tuple[int, int, int, int]]:
    try:
        import ctypes, ctypes.wintypes

        EnumWindows     = ctypes.windll.user32.EnumWindows
        GetWindowTextW  = ctypes.windll.user32.GetWindowTextW
        GetWindowRect   = ctypes.windll.user32.GetWindowRect
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible

        result: list[tuple[int,int,int,int]] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def _cb(hwnd, _lp):
            if not IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(256)
            GetWindowTextW(hwnd, buf, 256)
            if any(p in buf.value for p in HS_TITLE_PATTERNS):
                r = ctypes.wintypes.RECT()
                GetWindowRect(hwnd, ctypes.byref(r))
                result.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return True

        EnumWindows(_cb, 0)
        if result:
            log.info("Found HS via Win32: %s", result[0])
            return result[0]
    except Exception as e:
        log.warning("Win32 window finder failed: %s", e)

    # Fullscreen fallback
    if _hs_running_windows():
        log.info("Hearthstone running — using full-screen overlay")
        return _screen_fallback()
    return None


def _hs_running_windows() -> bool:
    try:
        import subprocess
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Hearthstone.exe", "/NH"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return "Hearthstone.exe" in out
    except Exception:
        return False


# ── Shared fallback ───────────────────────────────────────────────────────────

def _screen_fallback() -> Optional[tuple[int, int, int, int]]:
    """Cover the entire primary monitor — safe for fullscreen games."""
    try:
        import mss
        with mss.mss() as sct:
            m = sct.monitors[1]   # monitor 1 = primary
            return (m["left"], m["top"], m["width"], m["height"])
    except Exception:
        pass
    # Last resort: ask Qt
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                g = screen.geometry()
                return (g.x(), g.y(), g.width(), g.height())
    except Exception:
        pass
    log.warning("Could not determine screen size; overlay disabled")
    return None
