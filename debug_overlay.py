#!/usr/bin/env python3
"""
BG Overlay — Step-by-step debug tool
Run this while Hearthstone is open (fullscreen or windowed).

  python debug_overlay.py

It runs 4 self-contained tests and prints a PASS/FAIL result for each.
Copy the entire output and share it so the bug can be pinpointed.
"""
import sys, os, subprocess, time, ctypes

SEP = "─" * 60


def header(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ── Test 1: basic Python / platform info ─────────────────────────────────────
header("TEST 1 — Environment")
print(f"  Python      : {sys.version}")
print(f"  Platform    : {sys.platform}")
import platform
print(f"  macOS ver   : {platform.mac_ver()[0]}")

try:
    import PyQt6.QtCore as _q
    print(f"  PyQt6       : {_q.PYQT_VERSION_STR}  Qt {_q.QT_VERSION_STR}")
except Exception as e:
    print(f"  PyQt6       : MISSING — {e}")
    print("  Install:    pip install PyQt6")
    sys.exit(1)


# ── Test 2: NSWindow setup via libobjc ───────────────────────────────────────
header("TEST 2 — libobjc / NSWindow level")

def test_libobjc():
    try:
        lib = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        lib.sel_registerName.restype  = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        print("  libobjc.A.dylib  : LOADED ✓")
        # Verify sel_registerName works
        sel = lib.sel_registerName(b"window")
        print(f"  sel 'window'     : 0x{sel:x}  ({'OK' if sel else 'NULL — BAD'})")
        return True
    except Exception as e:
        print(f"  libobjc          : FAILED — {e}")
        return False

test_libobjc()


# ── Test 3: mss screen size ──────────────────────────────────────────────────
header("TEST 3 — Screen detection (mss)")
try:
    import mss
    with mss.mss() as sct:
        m = sct.monitors[1]
        print(f"  Primary screen   : {m['width']}×{m['height']} at ({m['left']},{m['top']})")
        print(f"  All monitors     : {len(sct.monitors)-1}")
    print("  mss              : OK ✓")
except Exception as e:
    print(f"  mss              : FAILED — {e}")
    print("  Install:    pip install mss")


# ── Test 4: visible overlay window ───────────────────────────────────────────
header("TEST 4 — PyQt6 overlay window (10-second visual test)")
print("  A BRIGHT RED WINDOW should appear on your screen.")
print("  If you see it: the Qt window layer works.")
print("  If you do NOT see it: the window is hidden behind the game.\n")

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore    import Qt, QTimer, QRectF
from PyQt6.QtGui     import QPainter, QColor, QFont

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._countdown = 10

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Bright semi-transparent red background so it's unmissable
        p.setBrush(QColor(220, 30, 30, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(20, 20, self.width()-40, self.height()-40), 20, 20)

        p.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   f"BG OVERLAY TEST\n"
                   f"Can you see this?\n"
                   f"Closing in {self._countdown}s")
        p.end()

    def tick(self):
        self._countdown -= 1
        self.update()
        if self._countdown <= 0:
            self._apply_nswindow_level()
            QTimer.singleShot(3000, app.quit)

    def _apply_nswindow_level(self):
        """Apply NSWindow level after the initial window is visible."""
        try:
            lib = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
            lib.sel_registerName.restype  = ctypes.c_void_p
            lib.sel_registerName.argtypes = [ctypes.c_char_p]

            def SEL(n): return lib.sel_registerName(n.encode())

            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            ns_window = lib.objc_msgSend(int(self.winId()), SEL("window"))
            print(f"\n  winId()          : 0x{int(self.winId()):x}")
            print(f"  NSWindow ptr     : {'0x{:x}'.format(ns_window) if ns_window else 'NULL ← BAD'}")

            if not ns_window:
                print("  NSWindow         : FAILED — window handle is NULL")
                return

            # Query current level before changing
            lib.objc_msgSend.restype  = ctypes.c_long
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            current_level = lib.objc_msgSend(ns_window, SEL("level"))
            print(f"  Current level    : {current_level}")

            # Set to NSStatusWindowLevel = 25
            lib.objc_msgSend.restype  = None
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
            lib.objc_msgSend(ns_window, SEL("setLevel:"), 25)

            # Verify level was set
            lib.objc_msgSend.restype  = ctypes.c_long
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            new_level = lib.objc_msgSend(ns_window, SEL("level"))
            print(f"  Level after set  : {new_level}  ({'OK ✓' if new_level == 25 else 'UNCHANGED ← BAD'})")

            # Set collection behavior
            lib.objc_msgSend.restype  = None
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            lib.objc_msgSend(ns_window, SEL("setCollectionBehavior:"), (1 << 2) | (1 << 7))
            print("  CollectionBehav  : set ✓")

            # Click-through
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
            lib.objc_msgSend(ns_window, SEL("setIgnoresMouseEvents:"), True)
            print("  IgnoresMouse     : set ✓")

        except Exception as e:
            print(f"  NSWindow setup   : EXCEPTION — {e}")

app = QApplication(sys.argv)
try:
    import mss
    with mss.mss() as sct:
        m = sct.monitors[1]
        sw, sh = m["width"], m["height"]
except Exception:
    screen = app.primaryScreen()
    g = screen.geometry()
    sw, sh = g.width(), g.height()

win = TestWindow()
win.setGeometry(sw//4, sh//4, sw//2, sh//2)   # centre of screen
win.show()
win.raise_()

# Apply NSWindow level after 500ms (window must be shown first)
QTimer.singleShot(500, win._apply_nswindow_level)

timer = QTimer()
timer.timeout.connect(win.tick)
timer.start(1000)

print(f"  Window size      : {sw//2}×{sh//2} centred on {sw}×{sh} screen")
print("  Waiting 10 seconds …")
app.exec()

header("SUMMARY — paste everything above this line in your bug report")
