"""
Cross-platform Hearthstone window detection.
Returns (x, y, width, height) of the game window.

macOS strategy (in order):
  1. Quartz CGWindowList  — works for Metal / fullscreen apps
  2. pgrep check + screen size — if HS is running but has no accessible window
     (the normal case for fullscreen Hearthstone), cover the whole primary screen

Windows strategy (in order):
  1. Win32 EnumWindows
  2. tasklist check + screen size
"""
from __future__ import annotations
import subprocess
import sys
import logging
from typing import Optional

log = logging.getLogger(__name__)


def find_hearthstone_window() -> Optional[tuple[int, int, int, int]]:
    """Return (x, y, w, h) or None if Hearthstone is not running."""
    if sys.platform == "win32":
        return _find_windows()
    elif sys.platform == "darwin":
        return _find_macos()
    return _screen_size()


# ── macOS ─────────────────────────────────────────────────────────────────────

def _find_macos() -> Optional[tuple[int, int, int, int]]:
    # Strategy 1: Quartz (works for any window level, including fullscreen Metal)
    result = _quartz_find()
    if result:
        return result

    # Strategy 2: if the process is alive, cover the whole screen.
    # Hearthstone's fullscreen Metal window is NOT accessible via System Events
    # or any Accessibility API — screen coverage is the correct approach.
    if _process_running_mac():
        log.info("Hearthstone is running fullscreen — overlay will cover primary screen")
        return _screen_size()

    return None


def _quartz_find() -> Optional[tuple[int, int, int, int]]:
    """
    Read CGWindowList via ctypes — no pyobjc required.
    Falls back silently; _screen_size() covers the fullscreen case.
    """
    try:
        import ctypes, ctypes.util
        cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))

        # CGWindowListCopyWindowInfo(option, relativeToWindow) -> CFArrayRef
        cg.CGWindowListCopyWindowInfo.restype  = ctypes.c_void_p
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        # kCGWindowListOptionOnScreenOnly = 1, kCGNullWindowID = 0
        arr = cg.CGWindowListCopyWindowInfo(1, 0)
        if not arr:
            return None

        # Use PyObjC if present for easy dict iteration; else skip
        try:
            import objc                        # type: ignore[import]
            ns_arr = objc.objc_object(c_void_p=arr)
            for info in ns_arr:
                owner = info.get("kCGWindowOwnerName") or ""
                if "Hearthstone" not in owner:
                    continue
                b = info.get("kCGWindowBounds")
                if not b:
                    continue
                x, y, w, h = int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"])
                if w > 100 and h > 100:
                    log.info("CoreGraphics: HS window %dx%d at (%d,%d)", w, h, x, y)
                    return (x, y, w, h)
        except ImportError:
            pass   # pyobjc not available; CoreGraphics array can't be iterated
    except Exception:
        pass
    return None


def _process_running_mac() -> bool:
    """Return True when a process named exactly 'Hearthstone' is alive."""
    try:
        out = subprocess.check_output(
            ["pgrep", "-x", "Hearthstone"],
            stderr=subprocess.DEVNULL, timeout=3,
        )
        return bool(out.strip())
    except Exception:
        return False


# ── Windows ───────────────────────────────────────────────────────────────────

def _find_windows() -> Optional[tuple[int, int, int, int]]:
    result = _win32_find()
    if result:
        return result
    if _process_running_win():
        log.info("Hearthstone is running — overlay will cover primary screen")
        return _screen_size()
    return None


def _win32_find() -> Optional[tuple[int, int, int, int]]:
    try:
        import ctypes
        import ctypes.wintypes as wt

        found: list[tuple[int, int, int, int]] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def _cb(hwnd, _):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
            if "Hearthstone" not in buf.value:
                return True
            r = wt.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w > 100 and h > 100:
                found.append((r.left, r.top, w, h))
            return True

        ctypes.windll.user32.EnumWindows(_cb, 0)
        if found:
            log.info("Win32: HS window %s", found[0])
            return found[0]
    except Exception as e:
        log.debug("Win32 EnumWindows failed: %s", e)
    return None


def _process_running_win() -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Hearthstone.exe", "/NH"],
            stderr=subprocess.DEVNULL, timeout=5, text=True,
        )
        return "Hearthstone.exe" in out
    except Exception:
        return False


# ── Shared: get primary screen dimensions ────────────────────────────────────

def _screen_size() -> Optional[tuple[int, int, int, int]]:
    """Return the primary monitor's geometry using mss, then Qt as fallback."""
    # mss works headless and is already in requirements.txt
    try:
        import mss
        with mss.mss() as sct:
            m = sct.monitors[1]          # index 1 = primary monitor
            return (m["left"], m["top"], m["width"], m["height"])
    except Exception:
        pass

    # Qt fallback (only works after QApplication is created)
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

    log.error("Cannot determine screen size — overlay disabled. "
              "Install mss:  pip install mss")
    return None
