#!/usr/bin/env python3
"""
BG Overlay — Level Escalation Test
Cycles through progressively higher window levels every 4 seconds.
Run this WHILE HEARTHSTONE IS OPEN IN FULLSCREEN and watch carefully.

For each level you'll see the bar colour and the level number change.
When the red bar SUDDENLY appears in front of Hearthstone, that level wins.
The first 30 lines of output also probe macOS for the actual shield-level value.

  python debug_overlay.py
"""
import sys, ctypes, ctypes.util, platform

print("─" * 64)
print(f"  Python : {sys.version.split()[0]}")
print(f"  macOS  : {platform.mac_ver()[0]}")
print("─" * 64)

try:
    cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics") or
                     "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cg.CGShieldingWindowLevel.restype = ctypes.c_int32
    shield = cg.CGShieldingWindowLevel()
    print(f"  CGShieldingWindowLevel = {shield}")
except Exception as e:
    shield = 2147483630
    print(f"  CGShieldingWindowLevel unavailable ({e}); fallback = {shield}")

# Sequence of levels to test, lowest → highest
LEVELS = [
    (25,         "NSStatusWindowLevel"),
    (1000,       "NSScreenSaverWindowLevel"),
    (100000,     "Custom high"),
    (shield - 1, "CGShieldingWindowLevel - 1  ← HIGHEST available"),
    (shield,     "CGShieldingWindowLevel"),
]

print(f"\nWill test {len(LEVELS)} levels, 4 seconds each.")
print("Watch the screen — when the red bar appears in front of Hearthstone,")
print("read the level number on the bar and report it back.\n")

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore    import Qt, QTimer
from PyQt6.QtGui     import QPainter, QColor, QFont

libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
libobjc.sel_registerName.restype  = ctypes.c_void_p
libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
def SEL(n): return libobjc.sel_registerName(n.encode())

def set_level(win, level: int):
    """Set NSWindow level + correct collection behaviour + click-through."""
    libobjc.objc_msgSend.restype  = ctypes.c_void_p
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ns_window = libobjc.objc_msgSend(int(win.winId()), SEL("window"))
    if not ns_window:
        return False

    libobjc.objc_msgSend.restype  = None
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
    libobjc.objc_msgSend(ns_window, SEL("setLevel:"), level)

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    libobjc.objc_msgSend(ns_window, SEL("setCollectionBehavior:"),
                         (1 << 0) | (1 << 8))   # CanJoinAllSpaces | FullScreenAuxiliary

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
    libobjc.objc_msgSend(ns_window, SEL("setIgnoresMouseEvents:"), True)

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libobjc.objc_msgSend(ns_window, SEL("orderFrontRegardless"))
    return True


class TestBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._level = 0
        self._label = "(starting…)"

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Vivid red bar across the screen
        p.fillRect(self.rect(), QColor(220, 30, 30, 230))
        p.setFont(QFont("Arial", 30, QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   f"LEVEL = {self._level}\n{self._label}\nIf you see this → THIS LEVEL WORKS")
        p.end()


app = QApplication(sys.argv)
screen = app.primaryScreen().geometry()
sw, sh = screen.width(), screen.height()

bar = TestBar()
# Wide bar across centre of screen — easy to spot
bar.setGeometry(0, sh//2 - 80, sw, 160)
bar.show()
bar.raise_()

# Cycle through every level
state = {"i": 0}
def next_level():
    if state["i"] >= len(LEVELS):
        print("\nAll levels tested.")
        print("→ Report back the HIGHEST level number you saw on the red bar")
        print("  (i.e. the last one that appeared in front of Hearthstone).")
        app.quit()
        return
    lvl, label = LEVELS[state["i"]]
    bar._level = lvl
    bar._label = label
    bar.update()
    ok = set_level(bar, lvl)
    print(f"  [t={state['i']*4:>2}s]  level={lvl:>12}  {label}  setup={'✓' if ok else '✗'}")
    state["i"] += 1

next_level()
timer = QTimer()
timer.timeout.connect(next_level)
timer.start(4000)

app.exec()
