"""
Companion HUD overlay for Hearthstone Battlegrounds.

macOS 26 Game Mode puts fullscreen Metal games above every NSWindow level
we can set (confirmed by debug_skylight: even SLSSetWindowLevel at INT32_MAX
loses). So we don't try to overlay the game — we show a compact panel
beside it.

Bug fixes in this revision:
  1. Always paints SOMETHING (live status table) so the user can see the
     overlay is alive even before SHOPPING starts.
  2. WA_ShowWithoutActivating + WindowDoesNotAcceptFocus + NSWindow
     setHidesOnDeactivate:NO + orderFront: (not orderFrontRegardless) →
     clicks no longer steal focus from Hearthstone.
  3. NSScreenSaverWindowLevel (1000) + periodic re-assertion every 400 ms
     → HUD stays above WINDOWED Hearthstone. (Fullscreen Game Mode still
     wins — there is no fix for that on macOS 26; use windowed mode.)
"""
from __future__ import annotations

import json
import os
import sys
import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, pyqtSlot
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QMouseEvent,
)
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from src.game_state import GameState
from src.advisor import Advisor, Recommendation
import config

log = logging.getLogger(__name__)

HUD_W = 360
HUD_H = 520
_POS_FILE = os.path.expanduser("~/.bgoverlaypos")
HUD_LEVEL = 1000   # NSScreenSaverWindowLevel — above all normal app windows


# ── Persisted position ────────────────────────────────────────────────────────

def _load_pos() -> Optional[QPoint]:
    try:
        d = json.loads(open(_POS_FILE).read())
        return QPoint(d["x"], d["y"])
    except Exception:
        return None


def _save_pos(pt: QPoint):
    try:
        open(_POS_FILE, "w").write(json.dumps({"x": pt.x(), "y": pt.y()}))
    except Exception:
        pass


# ── macOS NSWindow setup (no-focus, always-on-top, re-assertable) ─────────────

class _MacWin:
    """Cached libobjc bindings so we can re-assert the level cheaply."""
    def __init__(self):
        import ctypes
        self.ok = False
        try:
            self.objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
            self.objc.sel_registerName.restype  = ctypes.c_void_p
            self.objc.sel_registerName.argtypes = [ctypes.c_char_p]
            self.ctypes = ctypes
            self.ok = True
        except Exception as e:
            log.warning("libobjc unavailable: %s", e)

    def sel(self, name: str):
        return self.objc.sel_registerName(name.encode())

    def nswindow(self, qwidget) -> int:
        self.objc.objc_msgSend.restype  = self.ctypes.c_void_p
        self.objc.objc_msgSend.argtypes = [self.ctypes.c_void_p, self.ctypes.c_void_p]
        return self.objc.objc_msgSend(int(qwidget.winId()), self.sel("window"))

    def configure(self, qwidget, level: int):
        if not self.ok:
            return False
        nsw = self.nswindow(qwidget)
        if not nsw:
            return False
        c = self.ctypes
        msg = self.objc.objc_msgSend

        # setLevel:
        msg.restype  = None
        msg.argtypes = [c.c_void_p, c.c_void_p, c.c_long]
        msg(nsw, self.sel("setLevel:"), level)

        # setCollectionBehavior: CanJoinAllSpaces | FullScreenAuxiliary
        #                       | Stationary | IgnoresCycle
        msg.argtypes = [c.c_void_p, c.c_void_p, c.c_ulong]
        msg(nsw, self.sel("setCollectionBehavior:"),
            (1 << 0) | (1 << 8) | (1 << 4) | (1 << 6))

        # setHidesOnDeactivate:NO — stay visible when HS gets focus
        msg.argtypes = [c.c_void_p, c.c_void_p, c.c_bool]
        msg(nsw, self.sel("setHidesOnDeactivate:"), False)

        # orderFront: nil   (NOT orderFrontRegardless — that activates the app)
        msg.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p]
        msg(nsw, self.sel("orderFront:"), None)
        return True


_mac = _MacWin() if sys.platform == "darwin" else None


def _apply_hud_flags(window: QMainWindow):
    if sys.platform == "darwin" and _mac:
        _mac.configure(window, HUD_LEVEL)
    elif sys.platform == "win32":
        try:
            import ctypes
            hwnd  = int(window.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # WS_EX_LAYERED | WS_EX_NOACTIVATE
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x08000000)
        except Exception as e:
            log.warning("Win32 HUD flag setup failed: %s", e)


# ── Colours ───────────────────────────────────────────────────────────────────

_C = {
    "bg":       QColor(18, 18, 35, 250),
    "header":   QColor(30, 30, 55, 255),
    "border":   QColor(255, 215, 0),
    "gold":     QColor(255, 215, 0),
    "white":    QColor(240, 240, 240),
    "dim":      QColor(170, 170, 170),
    "dimmer":   QColor(120, 120, 130),
    "green":    QColor(76, 175, 80),
    "orange":   QColor(255, 152, 0),
    "red":      QColor(244, 67, 54),
    "best_bg":  QColor(40, 50, 30, 220),
    "card2_bg": QColor(30, 35, 50, 200),
}

PHASE_LABEL = {
    "SHOPPING": ("Shopping",  _C["green"]),
    "COMBAT":   ("Combat",    _C["red"]),
    "UNKNOWN":  ("Waiting",   _C["dimmer"]),
}


# ── Panel ─────────────────────────────────────────────────────────────────────

class CompanionPanel(QWidget):
    """Always paints background + status. Recommendations shown when ready."""

    def __init__(self, state: GameState, parent=None):
        super().__init__(parent)
        self.state = state
        self._recs: List[Recommendation] = []
        self._tavern_count = 0

    def set_state(self, recs, tavern_count):
        self._recs = recs
        self._tavern_count = max(tavern_count, len(recs), 1)
        self.update()

    # ──────────────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        self._draw_chrome(p, w, h)

        y = 46

        # Always-visible live status block
        y = self._draw_status_block(p, y, w)

        # Recommendations only when SHOPPING and we have data
        if self.state.phase == "SHOPPING" and self._recs:
            y = self._draw_best(p, self._recs[0], y, w)
            for rank, rec in enumerate(self._recs[1:3], 2):
                y = self._draw_minor(p, rec, rank, y, w)
                if y + 60 > h:
                    break
        elif self.state.phase == "SHOPPING":
            self._draw_msg(p, y, w, h, "Tavern empty — waiting for cards…")
        else:
            self._draw_msg(p, y, w, h,
                           "Not in shopping phase.\nOverlay is live and reading the log.")
        p.end()

    # ──────────────────────────────────────────────────────────────────────────

    def _draw_chrome(self, p, w, h):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(_C["bg"]))
        p.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)

        p.setPen(QPen(_C["border"], 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 10, 10)

        # Header
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(_C["header"]))
        p.drawRoundedRect(QRectF(2, 2, w - 4, 36), 9, 9)
        p.drawRect(QRectF(2, 20, w - 4, 18))

        p.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        p.setPen(_C["gold"])
        p.drawText(12, 26, "BG Advisor")

        # Phase pill
        label, color = PHASE_LABEL.get(self.state.phase,
                                       (self.state.phase, _C["dimmer"]))
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        p.setPen(color)
        p.drawText(w - 92, 26, label)

        # Hint footer
        p.setFont(QFont("Arial", 8))
        p.setPen(_C["dimmer"])
        p.drawText(8, h - 8, "drag to move  •  no-focus mode")

    def _draw_status_block(self, p, y, w):
        rows = [
            ("Turn",       str(self.state.turn)),
            ("Tier",       str(self.state.tavern_tier)),
            ("Health",     str(self.state.health)),
            ("Tavern",     f"{len(self.state.tavern_cards)} card(s)"),
            ("Board",      f"{len(self.state.player_board)} minion(s)"),
            ("Opponents",  f"{len(getattr(self.state, 'opponent_boards', {}))} seen"),
        ]
        mx = 12
        bx = mx
        bw = w - mx * 2
        bh = 18 * len(rows) + 12

        p.setPen(QPen(_C["dimmer"], 0.8))
        p.setBrush(QBrush(QColor(25, 25, 45, 200)))
        p.drawRoundedRect(QRectF(bx, y, bw, bh), 6, 6)

        p.setFont(QFont("Arial", 9))
        ty = y + 16
        for label, value in rows:
            p.setPen(_C["dim"])
            p.drawText(bx + 10, ty, label)
            p.setPen(_C["white"])
            p.drawText(bx + bw - 10 - p.fontMetrics().horizontalAdvance(value),
                       ty, value)
            ty += 18
        return y + bh + 10

    def _draw_msg(self, p, y, w, h, msg):
        p.setFont(QFont("Arial", 10))
        p.setPen(_C["dim"])
        p.drawText(QRectF(0, y, w, h - y - 24),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, msg)

    def _draw_best(self, p, rec, y, w):
        h_block = 178
        mx = 8
        p.setPen(QPen(_C["gold"], 1.2))
        p.setBrush(QBrush(_C["best_bg"]))
        p.drawRoundedRect(QRectF(mx, y, w - mx * 2, h_block), 7, 7)

        p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        p.setPen(_C["gold"])
        p.drawText(mx + 10, y + 22, f"BUY  {self._trunc(rec.card.name, 24)}")

        p.setFont(QFont("Arial", 8))
        p.setPen(_C["dim"])
        p.drawText(mx + 10, y + 38, f"Slot {rec.board_index + 1}  ·  T{rec.card.tier}  ·  score {rec.total_score:.0f}")

        wr = rec.win_rate_estimate
        bar = (_C["green"] if wr >= 60 else _C["orange"] if wr >= 50 else _C["red"])
        bx, by_, bw, bh = mx + 10, y + 48, w - mx * 2 - 56, 8
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(60, 60, 80)))
        p.drawRoundedRect(QRectF(bx, by_, bw, bh), 3, 3)
        p.setBrush(QBrush(bar))
        p.drawRoundedRect(QRectF(bx, by_, (wr / 100) * bw, bh), 3, 3)
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.setPen(bar)
        p.drawText(int(bx + bw + 6), int(by_ + 9), f"{wr:.0f}%")

        # Score breakdown row
        ty = y + 78
        p.setFont(QFont("Arial", 8))
        scores = [
            ("base", rec.base), ("tribe", rec.tribe_bonus),
            ("comp", rec.comp_bonus), ("grow", rec.scaling_bonus),
            ("ctr",  rec.counter_bonus),
        ]
        col_w = (w - mx * 2 - 20) // len(scores)
        for i, (lbl, val) in enumerate(scores):
            cx_ = mx + 10 + i * col_w
            col = (_C["green"] if val > 0 else _C["red"] if val < 0 else _C["dim"])
            p.setPen(col)
            sign = "+" if val > 0 else ""
            p.drawText(cx_, ty, f"{sign}{val:.0f}")
            p.setPen(_C["dim"])
            p.drawText(cx_, ty + 12, lbl)

        # Reasons
        ry = ty + 28
        p.setFont(QFont("Arial", 8))
        p.setPen(_C["white"])
        for reason in rec.reasons[:3]:
            p.drawText(mx + 10, ry, f"• {self._trunc(reason, 48)}")
            ry += 13
            if ry > y + h_block - 4:
                break
        return y + h_block + 8

    def _draw_minor(self, p, rec, rank, y, w):
        h_block = 48
        mx = 8
        p.setPen(QPen(_C["dimmer"], 0.6))
        p.setBrush(QBrush(_C["card2_bg"]))
        p.drawRoundedRect(QRectF(mx, y, w - mx * 2, h_block), 5, 5)

        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.setPen(_C["dim"])
        p.drawText(mx + 10, y + 16, f"#{rank}  {self._trunc(rec.card.name, 22)}")

        wr = rec.win_rate_estimate
        bar = (_C["green"] if wr >= 60 else _C["orange"] if wr >= 50 else _C["red"])
        bx, by_, bw, bh = mx + 10, y + 24, w - mx * 2 - 56, 5
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(60, 60, 80)))
        p.drawRoundedRect(QRectF(bx, by_, bw, bh), 2, 2)
        p.setBrush(QBrush(bar))
        p.drawRoundedRect(QRectF(bx, by_, (wr / 100) * bw, bh), 2, 2)
        p.setFont(QFont("Arial", 8))
        p.setPen(bar)
        p.drawText(int(bx + bw + 6), int(by_ + 7), f"{wr:.0f}%")

        p.setFont(QFont("Arial", 7))
        p.setPen(_C["dim"])
        p.drawText(mx + 10, y + 42,
                   f"Slot {rec.board_index + 1}  ·  {self._trunc(rec.reasons[0], 42) if rec.reasons else ''}")
        return y + h_block + 6

    @staticmethod
    def _trunc(s, n):
        return s[:n] + "…" if s and len(s) > n else (s or "")


# ── Window ────────────────────────────────────────────────────────────────────

class OverlayWindow(QMainWindow):
    """Compact HUD beside the game — no-focus, always-on-top (above windowed apps)."""

    def __init__(self, state: GameState):
        super().__init__()
        self.state   = state
        self.advisor = Advisor(state)

        self.setWindowTitle("BG Advisor")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        # Never activate this window when shown or clicked
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowOpacity(config.OVERLAY_OPACITY)

        self.panel = CompanionPanel(state, self)
        self.setCentralWidget(self.panel)
        self.setFixedSize(HUD_W, HUD_H)

        self._drag_offset: Optional[QPoint] = None

        # Periodic content refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(config.POLL_INTERVAL_MS)

        # Periodic level re-assertion (counters macOS demotion on focus changes)
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._reassert_level)
        self._level_timer.start(400)

    # ── Dragging without activating ───────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_offset and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton and self._drag_offset:
            self._drag_offset = None
            _save_pos(self.pos())
            e.accept()

    # ── Show / position ───────────────────────────────────────────────────────
    def show_over_game(self, x: int, y: int, w: int, h: int):
        saved = _load_pos()
        if saved:
            self.move(saved)
        else:
            screen = QApplication.primaryScreen()
            sw = screen.geometry().width()  if screen else 1920
            sh = screen.geometry().height() if screen else 1080
            hud_x = x + w + 8
            hud_y = y
            if hud_x + HUD_W > sw:
                hud_x = max(0, x - HUD_W - 8)
            if hud_y + HUD_H > sh:
                hud_y = max(0, sh - HUD_H - 8)
            self.move(hud_x, hud_y)

        # show() does NOT activate because of WA_ShowWithoutActivating
        self.show()
        # Apply native flags after the NSWindow exists
        QTimer.singleShot(150, lambda: _apply_hud_flags(self))
        QTimer.singleShot(150, self.panel.update)
        log.info("HUD shown at %s (game %d,%d %dx%d)", self.pos(), x, y, w, h)

    def _reassert_level(self):
        if sys.platform == "darwin" and _mac and self.isVisible():
            _mac.configure(self, HUD_LEVEL)

    # ── Thread-safe refresh ───────────────────────────────────────────────────
    def force_refresh(self):
        QTimer.singleShot(0, self._refresh)

    @pyqtSlot()
    def _refresh(self):
        if self.state.phase == "SHOPPING":
            recs = self.advisor.recommend()
            self.panel.set_state(recs, len(self.state.tavern_cards))
        else:
            self.panel.set_state([], 0)
