"""
Companion HUD overlay for Hearthstone Battlegrounds.

macOS 26 Game Mode places fullscreen Metal games above every public and
private NSWindow level, so a transparent full-screen overlay is not
feasible. Instead we show a compact draggable panel (the "HUD") that the
user keeps positioned beside the game window.

The public interface is unchanged:
  OverlayWindow(state)          — create
  .show_over_game(x, y, w, h)  — position and show (HUD anchors beside game)
  .force_refresh()              — thread-safe repaint trigger

Windows note: the same HUD is used; a future enhancement can re-add the
transparent overlay approach for Windows where it works reliably.
"""
from __future__ import annotations

import json
import os
import sys
import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, QPointF, pyqtSlot
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QPainterPath, QMouseEvent,
)
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from src.game_state import GameState
from src.advisor import Advisor, Recommendation
import config

log = logging.getLogger(__name__)

HUD_W = 360
HUD_H = 500
_POS_FILE = os.path.expanduser("~/.bgoverlaypos")

# ── Persist HUD position ──────────────────────────────────────────────────────

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


# ── Platform: keep HUD above Finder/desktop, but don't fight the game ─────────

def _apply_hud_flags(window: QMainWindow):
    if sys.platform == "darwin":
        _macos_hud(window)
    elif sys.platform == "win32":
        _win32_hud(window)


def _macos_hud(window: QMainWindow):
    """NSStatusWindowLevel (25) — floats above desktop, yields to focused apps."""
    import ctypes
    try:
        libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        libobjc.sel_registerName.restype  = ctypes.c_void_p
        libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
        def SEL(n): return libobjc.sel_registerName(n.encode())

        libobjc.objc_msgSend.restype  = ctypes.c_void_p
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        nsw = libobjc.objc_msgSend(int(window.winId()), SEL("window"))
        if not nsw:
            return

        # NSStatusWindowLevel = 25 (above Finder, below focused apps)
        libobjc.objc_msgSend.restype  = None
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        libobjc.objc_msgSend(nsw, SEL("setLevel:"), 25)

        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        libobjc.objc_msgSend(nsw, SEL("setCollectionBehavior:"),
                             (1 << 0) | (1 << 4))   # CanJoinAllSpaces | Stationary

        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        libobjc.objc_msgSend(nsw, SEL("orderFrontRegardless"))
        log.debug("macOS HUD: NSStatusWindowLevel applied")
    except Exception as e:
        log.warning("macOS HUD setup failed: %s", e)


def _win32_hud(window: QMainWindow):
    try:
        import ctypes
        hwnd  = int(window.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        # WS_EX_LAYERED — allows opacity; do NOT add WS_EX_TRANSPARENT (we want clicks)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000)
        log.debug("Win32 HUD layered flag applied")
    except Exception as e:
        log.warning("Win32 HUD setup failed: %s", e)


# ── Companion panel ───────────────────────────────────────────────────────────

_C = {
    "bg":       QColor(18, 18, 35, 245),
    "header":   QColor(30, 30, 55, 255),
    "border":   QColor(255, 215, 0),
    "gold":     QColor(255, 215, 0),
    "white":    QColor(240, 240, 240),
    "dim":      QColor(160, 160, 160),
    "green":    QColor(76, 175, 80),
    "orange":   QColor(255, 152, 0),
    "red":      QColor(244, 67, 54),
    "best_bg":  QColor(40, 50, 30, 200),
    "card2_bg": QColor(30, 35, 50, 180),
}

PHASE_LABEL = {
    "SHOPPING": ("購物階段", _C["green"]),
    "COMBAT":   ("戰鬥中",   _C["red"]),
    "UNKNOWN":  ("等待遊戲…", _C["dim"]),
}


class CompanionPanel(QWidget):
    """Paints all HUD content — no transparency needed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recs:         List[Recommendation] = []
        self._tavern_count: int = 0
        self._phase:        str = "UNKNOWN"

    def set_state(self, recs: List[Recommendation], tavern_count: int, phase: str):
        self._recs         = recs
        self._tavern_count = max(tavern_count, len(recs), 1)
        self._phase        = phase
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(_C["bg"]))
        p.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)

        # Gold border
        p.setPen(QPen(_C["border"], 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 10, 10)

        # Header bar
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(_C["header"]))
        p.drawRoundedRect(QRectF(2, 2, w - 4, 36), 9, 9)
        p.drawRect(QRectF(2, 20, w - 4, 18))   # square off bottom of header

        p.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        p.setPen(_C["gold"])
        p.drawText(12, 26, "⚔  BG Advisor")

        # Phase pill
        phase_label, phase_color = PHASE_LABEL.get(self._phase, ("…", _C["dim"]))
        p.setFont(QFont("Arial", 9))
        p.setPen(phase_color)
        p.drawText(w - 88, 26, phase_label)

        y = 46  # content start

        if self._phase != "SHOPPING" or not self._recs:
            p.setFont(QFont("Arial", 11))
            p.setPen(_C["dim"])
            msg = "等待購物階段…" if self._phase != "SHOPPING" else "無酒館資料"
            p.drawText(QRectF(0, y, w, h - y),
                       Qt.AlignmentFlag.AlignCenter, msg)
            p.end()
            return

        # Best card
        y = self._draw_best(p, self._recs[0], y, w)

        # 2nd and 3rd
        for rank, rec in enumerate(self._recs[1:3], 2):
            y = self._draw_minor(p, rec, rank, y, w)
            if y + 60 > h:
                break

        p.end()

    # ── Card sections ─────────────────────────────────────────────────────────

    def _draw_best(self, p: QPainter, rec: Recommendation, y: int, w: int) -> int:
        h_block = 190
        mx = 8

        # Card background
        p.setPen(QPen(_C["gold"], 1))
        p.setBrush(QBrush(_C["best_bg"]))
        p.drawRoundedRect(QRectF(mx, y + 2, w - mx * 2, h_block), 7, 7)

        p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        p.setPen(_C["gold"])
        p.drawText(mx + 10, y + 22, f"▶  {self._truncate(rec.card.name, 26)}")

        p.setFont(QFont("Arial", 8))
        p.setPen(_C["dim"])
        slot_txt = f"酒館第 {rec.board_index + 1} 格"
        tier_txt = f"T{rec.card.tier}"
        p.drawText(mx + 10, y + 36, f"{slot_txt}  ·  {tier_txt}")

        # Win-rate bar
        wr  = rec.win_rate_estimate
        bar_color = (_C["green"] if wr >= 60 else _C["orange"] if wr >= 50 else _C["red"])
        bx, by_, bw, bh = mx + 10, y + 44, w - mx * 2 - 20, 8
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(60, 60, 80)))
        p.drawRoundedRect(QRectF(bx, by_, bw, bh), 3, 3)
        p.setBrush(QBrush(bar_color))
        p.drawRoundedRect(QRectF(bx, by_, (wr / 100) * bw, bh), 3, 3)

        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.setPen(bar_color)
        p.drawText(int(bx + bw + 4), int(by_ + 9), f"{wr:.0f}%")

        # Score breakdown
        ty = y + 68
        p.setFont(QFont("Arial", 8))
        scores = [
            ("基礎分",   rec.base),
            ("種族",     rec.tribe_bonus),
            ("套牌",     rec.comp_bonus),
            ("成長",     rec.scaling_bonus),
            ("剋制",     rec.counter_bonus),
        ]
        col_w = (w - mx * 2 - 20) // len(scores)
        for i, (lbl, val) in enumerate(scores):
            cx_ = mx + 10 + i * col_w
            col = (_C["green"] if val > 0 else _C["red"] if val < 0 else _C["dim"])
            p.setPen(col)
            sign = "+" if val > 0 else ""
            p.drawText(cx_, ty,      f"{sign}{val:.0f}")
            p.setPen(_C["dim"])
            p.drawText(cx_, ty + 12, lbl)

        # Reasons
        ry = ty + 28
        p.setFont(QFont("Arial", 8))
        p.setPen(_C["white"])
        for reason in rec.reasons[:3]:
            p.drawText(mx + 10, ry, f"• {self._truncate(reason, 46)}")
            ry += 14
            if ry > y + h_block - 4:
                break

        return y + h_block + 8

    def _draw_minor(self, p: QPainter, rec: Recommendation, rank: int,
                    y: int, w: int) -> int:
        h_block = 52
        mx = 8
        p.setPen(QPen(_C["dim"], 0.8))
        p.setBrush(QBrush(_C["card2_bg"]))
        p.drawRoundedRect(QRectF(mx, y + 2, w - mx * 2, h_block), 5, 5)

        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.setPen(_C["dim"])
        p.drawText(mx + 10, y + 18,
                   f"#{rank}  {self._truncate(rec.card.name, 24)}")

        wr = rec.win_rate_estimate
        bar_color = (_C["green"] if wr >= 60 else _C["orange"] if wr >= 50 else _C["red"])
        bx, by_, bw, bh = mx + 10, y + 26, w - mx * 2 - 60, 5
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(60, 60, 80)))
        p.drawRoundedRect(QRectF(bx, by_, bw, bh), 2, 2)
        p.setBrush(QBrush(bar_color))
        p.drawRoundedRect(QRectF(bx, by_, (wr / 100) * bw, bh), 2, 2)

        p.setFont(QFont("Arial", 8))
        p.setPen(bar_color)
        p.drawText(int(bx + bw + 5), int(by_ + 7), f"{wr:.0f}%")

        p.setFont(QFont("Arial", 7))
        p.setPen(_C["dim"])
        p.drawText(mx + 10, y + 46,
                   f"酒館第 {rec.board_index + 1} 格  ·  {self._truncate(rec.reasons[0], 38) if rec.reasons else ''}")

        return y + h_block + 6

    @staticmethod
    def _truncate(s: str, n: int) -> str:
        return s[:n] + "…" if len(s) > n else s


# ── Main window ───────────────────────────────────────────────────────────────

class OverlayWindow(QMainWindow):
    """
    Companion HUD window.

    Draggable by clicking and dragging anywhere on the panel.
    Position is persisted to ~/.bgoverlaypos between sessions.
    """

    def __init__(self, state: GameState):
        super().__init__()
        self.state   = state
        self.advisor = Advisor(state)

        self.setWindowTitle("BG Advisor")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Solid background — no transparency needed
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setWindowOpacity(config.OVERLAY_OPACITY)

        self.panel = CompanionPanel(self)
        self.setCentralWidget(self.panel)
        self.setFixedSize(HUD_W, HUD_H)

        self._drag_start: Optional[QPoint] = None

        # Periodic refresh fallback
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(config.POLL_INTERVAL_MS)

    # ── Dragging ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_start and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_start)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            _save_pos(self.pos())

    # ── Positioning ───────────────────────────────────────────────────────────

    def show_over_game(self, x: int, y: int, w: int, h: int):
        """
        Position the HUD to the right of the game window (or top-right of
        screen if it would go off-screen), then show.
        """
        saved = _load_pos()
        if saved:
            self.move(saved)
        else:
            screen = QApplication.primaryScreen()
            sw = screen.geometry().width() if screen else 1920
            sh = screen.geometry().height() if screen else 1080

            # Prefer: right edge of game window
            hud_x = x + w + 8
            hud_y = y
            # Clamp to screen
            if hud_x + HUD_W > sw:
                hud_x = max(0, x - HUD_W - 8)
            if hud_y + HUD_H > sh:
                hud_y = max(0, sh - HUD_H - 8)
            self.move(hud_x, hud_y)

        self.show()
        self.raise_()
        QTimer.singleShot(200, lambda: _apply_hud_flags(self))
        log.info("HUD shown (game at %d,%d %dx%d)", x, y, w, h)

    # ── Thread-safe refresh ───────────────────────────────────────────────────

    def force_refresh(self):
        """Safe to call from any thread."""
        QTimer.singleShot(0, self._refresh)

    @pyqtSlot()
    def _refresh(self):
        phase = self.state.phase
        if phase != "SHOPPING":
            self.panel.set_state([], 0, phase)
            return
        recs = self.advisor.recommend()
        self.panel.set_state(recs, len(self.state.tavern_cards), phase)
