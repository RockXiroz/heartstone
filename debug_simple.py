#!/usr/bin/env python3
"""
Minimal overlay visibility test for macOS 26.

Tests in order:
  1. Plain opaque QWidget (no transparency, no NSWindow tricks)
  2. Same but with WA_TranslucentBackground
  3. Same + NSWindow level bump via ctypes

Run with Hearthstone in WINDOWED mode (not fullscreen).
Each step lasts 5 seconds. If step 1 is invisible, the problem is Qt
geometry / permissions — NOT the level or transparency.

  python debug_simple.py
"""
import sys, ctypes, ctypes.util, platform, time
print("─" * 60)
print(f"Python  : {sys.version.split()[0]}")
print(f"macOS   : {platform.mac_ver()[0]}")

from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QScreen

app = QApplication(sys.argv)

# ── Report screen info ────────────────────────────────────────────────────────
screen = app.primaryScreen()
geom   = screen.geometry()          # logical pixels
native = screen.size()              # same as geometry().size()
dpr    = screen.devicePixelRatio()  # 2.0 on Retina
print(f"Screen  : logical {geom.width()}×{geom.height()}  "
      f"dpr={dpr}  physical≈{int(geom.width()*dpr)}×{int(geom.height()*dpr)}")
print("─" * 60)

# Target: a 400×120 bar centred on screen
sw, sh = geom.width(), geom.height()
wx = sw // 2 - 200
wy = sh // 2 - 60
print(f"Window target pos : ({wx}, {wy})  size: 400×120")
print()

# ── Helper: apply NSWindow level ─────────────────────────────────────────────
def _apply_nslevel(win, level: int) -> bool:
    try:
        libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")

        libobjc.sel_registerName.restype  = ctypes.c_void_p
        libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
        def SEL(n): return libobjc.sel_registerName(n.encode())

        # winId() → NSView* → .window() → NSWindow*
        libobjc.objc_msgSend.restype  = ctypes.c_void_p
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ns_view   = int(win.winId())
        ns_window = libobjc.objc_msgSend(ns_view, SEL("window"))
        if not ns_window:
            print("  ✗ NSWindow ptr is NULL")
            return False

        # setLevel:
        libobjc.objc_msgSend.restype  = None
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        libobjc.objc_msgSend(ns_window, SEL("setLevel:"), level)

        # setCollectionBehavior: CanJoinAllSpaces | FullScreenAuxiliary
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        libobjc.objc_msgSend(ns_window, SEL("setCollectionBehavior:"), (1 << 0) | (1 << 8))

        # setIgnoresMouseEvents:
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        libobjc.objc_msgSend(ns_window, SEL("setIgnoresMouseEvents:"), True)

        # orderFrontRegardless
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        libobjc.objc_msgSend(ns_window, SEL("orderFrontRegardless"))

        print(f"  ✓ NSWindow {ns_window:#x}  level→{level}")
        return True
    except Exception as e:
        print(f"  ✗ NSWindow setup failed: {e}")
        return False


TESTS = [
    ("STEP 1: Opaque, no NSWindow tricks",    False, False),
    ("STEP 2: Transparent, no NSWindow tricks", True, False),
    ("STEP 3: Transparent + NSWindow level 1000", True, True),
]

state = {"i": 0, "win": None}

def next_step():
    if state["win"]:
        state["win"].close()
        state["win"] = None

    if state["i"] >= len(TESTS):
        print("\nAll steps done.")
        print("→ Report which steps (1/2/3) showed a visible coloured bar.")
        app.quit()
        return

    label, transparent, nslevel = TESTS[state["i"]]
    print(f"\n{label}")

    w = QWidget()
    flags = (Qt.WindowType.FramelessWindowHint
             | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.Tool)
    w.setWindowFlags(flags)

    if transparent:
        w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    # Solid colour if opaque; semi-transparent if not
    colour = ["#e01e1e", "#1e90e0", "#1ee068"][state["i"]]

    class _Bar(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
        def paintEvent(self, _):
            p = QPainter(self)
            if transparent:
                p.fillRect(self.rect(), QColor(colour))
                p.fillRect(self.rect(), QColor(0, 0, 0, 80))  # darken slightly
            else:
                p.fillRect(self.rect(), QColor(colour))
            p.setFont(QFont("Arial", 18, QFont.Weight.Bold))
            p.setPen(QColor(255, 255, 255))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       f"{label}\n({'transparent' if transparent else 'opaque'})")
            p.end()

    bar = _Bar(w)
    w.setGeometry(wx, wy, 400, 120)
    bar.setGeometry(0, 0, 400, 120)

    # Report actual position after show
    w.show()
    w.raise_()
    actual = w.geometry()
    print(f"  Actual Qt geometry : ({actual.x()}, {actual.y()}) {actual.width()}×{actual.height()}")

    if nslevel:
        QTimer.singleShot(200, lambda: _apply_nslevel(w, 1000))

    state["win"] = w
    state["i"] += 1

# Run each step for 5 seconds
next_step()
timer = QTimer()
timer.timeout.connect(next_step)
timer.start(5000)

app.exec()
