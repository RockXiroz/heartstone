#!/usr/bin/env python3
"""
Z-order survival test.

Puts one bar at CGShieldingWindowLevel and leaves it for 30 seconds.
Click on Hearthstone (windowed) to give it focus, and watch whether the
bar stays on top.

If the bar stays visible → main overlay needs to use this level too.
If the bar gets covered → no NSWindow level beats Hearthstone, and we
                          need a different approach entirely.

  python debug_zorder.py
"""
import sys, ctypes, ctypes.util

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont

cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
cg.CGShieldingWindowLevel.restype = ctypes.c_int32
SHIELD = cg.CGShieldingWindowLevel()
print(f"CGShieldingWindowLevel = {SHIELD}")

libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
libobjc.sel_registerName.restype  = ctypes.c_void_p
libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
def SEL(n): return libobjc.sel_registerName(n.encode())


def apply_level(win, level):
    libobjc.objc_msgSend.restype  = ctypes.c_void_p
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    nsw = libobjc.objc_msgSend(int(win.winId()), SEL("window"))
    if not nsw:
        print("  ✗ NSWindow NULL")
        return

    libobjc.objc_msgSend.restype  = None
    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
    libobjc.objc_msgSend(nsw, SEL("setLevel:"), level)

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    # CanJoinAllSpaces | FullScreenAuxiliary | Stationary | IgnoresCycle
    behaviour = (1 << 0) | (1 << 8) | (1 << 4) | (1 << 6)
    libobjc.objc_msgSend(nsw, SEL("setCollectionBehavior:"), behaviour)

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
    libobjc.objc_msgSend(nsw, SEL("setIgnoresMouseEvents:"), True)

    libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    libobjc.objc_msgSend(nsw, SEL("orderFrontRegardless"))


class Bar(QWidget):
    def __init__(self, level, label):
        super().__init__()
        self._level = level
        self._label = label
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


app = QApplication(sys.argv)
geom = app.primaryScreen().geometry()
sw, sh = geom.width(), geom.height()

bar = Bar(SHIELD, "CGShieldingWindowLevel")
bar.setGeometry(sw // 2 - 300, sh // 2 - 80, 600, 160)
bar.show()
bar.raise_()
QTimer.singleShot(100, lambda: apply_level(bar, SHIELD))

# Re-assert level every second in case macOS demotes it on focus change
def reassert():
    apply_level(bar, SHIELD)
timer = QTimer()
timer.timeout.connect(reassert)
timer.start(1000)

# Auto-quit after 30s
QTimer.singleShot(30000, app.quit)

print("\n→ For the next 30 seconds: click on Hearthstone (windowed).")
print("  Does the red bar stay visible on top, or get covered?")
print()
app.exec()
