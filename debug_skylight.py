#!/usr/bin/env python3
"""
SkyLight private-API window level test.

Uses CGSSetWindowLevel from the private SkyLight framework to push the
overlay ABOVE CGShieldingWindowLevel. This is what Bartender, Magnet, and
similar apps use to outrank fullscreen games.

Cycles through:
  shield + 1
  shield + 10
  shield + 1000
  INT32_MAX (2147483647)

Each level holds for 6 seconds. Click Hearthstone during each step and
report which (if any) levels stay visible on top.

  python debug_skylight.py
"""
import sys, ctypes, ctypes.util

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont

# ── CoreGraphics: get shield level ───────────────────────────────────────────
cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
cg.CGShieldingWindowLevel.restype = ctypes.c_int32
SHIELD = cg.CGShieldingWindowLevel()
print(f"CGShieldingWindowLevel = {SHIELD}")

# ── SkyLight private framework ───────────────────────────────────────────────
SKYLIGHT_PATH = "/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight"
try:
    sl = ctypes.CDLL(SKYLIGHT_PATH)
    sl.SLSMainConnectionID.restype = ctypes.c_int
    sl.SLSSetWindowLevel.restype   = ctypes.c_int
    sl.SLSSetWindowLevel.argtypes  = [ctypes.c_int, ctypes.c_uint32, ctypes.c_int]
    CID = sl.SLSMainConnectionID()
    print(f"SkyLight connection ID = {CID}")
    set_window_level = sl.SLSSetWindowLevel
except (OSError, AttributeError) as e:
    # Fall back to older CGS names (pre-macOS 11)
    print(f"SkyLight not found / no SLS prefix ({e}); trying CGS names")
    sl = ctypes.CDLL(SKYLIGHT_PATH)
    sl._CGSDefaultConnection.restype = ctypes.c_int
    sl.CGSSetWindowLevel.restype   = ctypes.c_int
    sl.CGSSetWindowLevel.argtypes  = [ctypes.c_int, ctypes.c_uint32, ctypes.c_int]
    CID = sl._CGSDefaultConnection()
    print(f"CGS connection ID = {CID}")
    set_window_level = sl.CGSSetWindowLevel

# ── libobjc: get NSWindow's windowNumber → CGSWindowID ───────────────────────
libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
libobjc.sel_registerName.restype  = ctypes.c_void_p
libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
def SEL(n): return libobjc.sel_registerName(n.encode())


def get_window_id(qwidget) -> int:
    """Qt winId() → NSView* → .window → .windowNumber  (CGSWindowID)."""
    libobjc.objc_msgSend.restype  = ctypes.c_void_p
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    nsw = libobjc.objc_msgSend(int(qwidget.winId()), SEL("window"))
    if not nsw:
        return 0
    libobjc.objc_msgSend.restype  = ctypes.c_long
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    return libobjc.objc_msgSend(nsw, SEL("windowNumber"))


def apply_collection_behaviour(qwidget):
    libobjc.objc_msgSend.restype  = ctypes.c_void_p
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    nsw = libobjc.objc_msgSend(int(qwidget.winId()), SEL("window"))

    libobjc.objc_msgSend.restype  = None
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    # CanJoinAllSpaces | FullScreenAuxiliary | Stationary | IgnoresCycle
    libobjc.objc_msgSend(nsw, SEL("setCollectionBehavior:"),
                         (1 << 0) | (1 << 8) | (1 << 4) | (1 << 6))

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
    libobjc.objc_msgSend(nsw, SEL("setIgnoresMouseEvents:"), True)

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libobjc.objc_msgSend(nsw, SEL("orderFrontRegardless"))


LEVELS = [
    (SHIELD + 1,     "shield + 1"),
    (SHIELD + 10,    "shield + 10"),
    (SHIELD + 1000,  "shield + 1000"),
    (2147483647,     "INT32_MAX"),
]


class Bar(QWidget):
    def __init__(self):
        super().__init__()
        self._level = 0
        self._label = ""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(220, 30, 30, 230))
        p.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   f"LEVEL {self._level}\n{self._label}\n"
                   f"Click Hearthstone — does this stay on top?")
        p.end()


app  = QApplication(sys.argv)
geom = app.primaryScreen().geometry()
sw, sh = geom.width(), geom.height()

bar = Bar()
bar.setGeometry(sw // 2 - 350, sh // 2 - 90, 700, 180)
bar.show()
bar.raise_()
apply_collection_behaviour(bar)

WID = get_window_id(bar)
print(f"Window ID (windowNumber) = {WID}")
print()

state = {"i": 0}

def reassert():
    """Re-apply current level — macOS may demote on focus change."""
    if state["i"] == 0 or state["i"] > len(LEVELS):
        return
    lvl, _ = LEVELS[state["i"] - 1]
    set_window_level(CID, WID, lvl)

def next_step():
    if state["i"] >= len(LEVELS):
        print("\nDone. Report which step(s) (1-4) stayed on top of Hearthstone.")
        app.quit()
        return
    lvl, label = LEVELS[state["i"]]
    bar._level = lvl
    bar._label = label
    bar.update()
    rc = set_window_level(CID, WID, lvl)
    print(f"  step {state['i']+1}: level={lvl:>12}  ({label})  SLS rc={rc}")
    state["i"] += 1

next_step()
step_timer = QTimer(); step_timer.timeout.connect(next_step); step_timer.start(6000)
keep_timer = QTimer(); keep_timer.timeout.connect(reassert);  keep_timer.start(500)

app.exec()
