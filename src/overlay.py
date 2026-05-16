"""
Transparent PyQt6 overlay — always-on-top, click-through, thread-safe.

macOS: NSWindowLevel is set to NSStatusWindowLevel so the overlay floats
       above fullscreen Metal apps (Hearthstone).
Win32: WS_EX_TRANSPARENT|WS_EX_LAYERED applied for click-through.

Thread safety: force_refresh() is safe to call from any thread — it posts
a zero-delay QTimer to the main-thread event loop instead of touching Qt
objects directly.
"""
from __future__ import annotations

import sys
import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSlot
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QRadialGradient, QPainterPath,
)
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from src.game_state import GameState
from src.advisor import Advisor, Recommendation
import config

log = logging.getLogger(__name__)


# ── OS helpers ────────────────────────────────────────────────────────────────

def _apply_platform_flags(window: QMainWindow):
    """Make the overlay click-through and float above everything."""
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd  = int(window.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
            log.debug("Win32 click-through applied")
        except Exception as e:
            log.warning("Win32 click-through failed: %s", e)

    elif sys.platform == "darwin":
        _macos_float_level(window)


def _macos_float_level(window: QMainWindow):
    """
    Raise the NSWindow to NSStatusWindowLevel (25) so it appears above
    full-screen Metal apps.  Requires pyobjc-framework-AppKit.
    """
    try:
        import objc                          # type: ignore[import]
        from AppKit import NSApp             # type: ignore[import]
        # NSStatusWindowLevel = 25
        NSStatusWindowLevel = 25
        ptr = int(window.winId())
        ns_win = objc.objc_object(c_void_p=ptr)
        ns_win.setLevel_(NSStatusWindowLevel)
        ns_win.setCollectionBehavior_(
            1 << 2 |   # NSWindowCollectionBehaviorCanJoinAllSpaces
            1 << 7     # NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        log.debug("macOS NSWindow level set to NSStatusWindowLevel")
    except Exception as e:
        log.debug("pyobjc not available, skipping NSWindow level: %s", e)


# ── Canvas ────────────────────────────────────────────────────────────────────

class OverlayCanvas(QWidget):
    """The paint surface — transparent, mouse-passthrough."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._recs:         List[Recommendation] = []
        self._tavern_count: int = 0            # total slots for spacing
        self._phase:        str = "UNKNOWN"

    # Called from main thread only (enforced by OverlayWindow.force_refresh)
    def set_state(self, recs: List[Recommendation],
                  tavern_count: int, phase: str):
        self._recs         = recs
        self._tavern_count = max(tavern_count, len(recs), 1)
        self._phase        = phase
        self.update()                          # triggers paintEvent on main thread

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        self._draw_status_badge(p)

        if self._recs and self._phase == "SHOPPING":
            best = self._recs[0]
            cx, cy = self._card_centre(best.board_index)
            self._draw_glow(p, cx, cy)
            self._draw_arrow(p, cx, cy)
            self._draw_panel(p, best, cx, cy)
            for rank, rec in enumerate(self._recs[1:3], 2):
                self._draw_rank_badge(p, *self._card_centre(rec.board_index), rank)

        p.end()

    # ── Card positions ────────────────────────────────────────────────────
    def _card_centre(self, slot: int) -> tuple[float, float]:
        w, h = self.width(), self.height()
        n    = self._tavern_count             # use TOTAL slots, not len(recs)
        x0   = config.TAVERN_X_START * w
        x1   = config.TAVERN_X_END   * w
        step = (x1 - x0) / max(n - 1, 1) if n > 1 else 0
        return x0 + slot * step, config.TAVERN_ROW_Y * h

    # ── Drawing ───────────────────────────────────────────────────────────
    def _draw_status_badge(self, p: QPainter):
        """Small pill in the top-right corner — always visible so user knows
        the overlay is active."""
        phase_colors = {
            "SHOPPING": (QColor(76, 175, 80),  "購物階段"),
            "COMBAT":   (QColor(244, 67, 54),  "戰鬥階段"),
            "UNKNOWN":  (QColor(120, 120, 120),"等待遊戲…"),
        }
        color, label = phase_colors.get(self._phase,
                                        (QColor(120, 120, 120), self._phase))
        pw, ph = 130, 26
        px = self.width() - pw - 12
        py = 10
        p.setPen(QPen(color, 1))
        p.setBrush(QBrush(QColor(0, 0, 0, 180)))
        p.drawRoundedRect(QRectF(px, py, pw, ph), 8, 8)
        p.setPen(color)
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        p.drawText(int(px + 8), int(py + 18), label)

    def _draw_glow(self, p: QPainter, cx: float, cy: float):
        r = 72
        g = QRadialGradient(QPointF(cx, cy), r)
        g.setColorAt(0.0, QColor(255, 215, 0, 170))
        g.setColorAt(0.6, QColor(255, 215, 0,  45))
        g.setColorAt(1.0, QColor(255, 215, 0,   0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_arrow(self, p: QPainter, cx: float, cy: float):
        tip_y  = cy - 14
        tail_y = tip_y - 68
        sw, hw, hh = 10, 34, 30

        shaft = QPainterPath()
        shaft.addRect(QRectF(cx - sw/2, tail_y, sw, tip_y - tail_y - hh))
        head  = QPainterPath()
        head.moveTo(cx, tip_y)
        head.lineTo(cx - hw/2, tip_y - hh)
        head.lineTo(cx + hw/2, tip_y - hh)
        head.closeSubpath()
        full = shaft.united(head)

        p.setPen(QPen(QColor(0, 0, 0, 160), 2))
        p.setBrush(QBrush(QColor(255, 255, 255, 235)))
        p.drawPath(full)
        p.setPen(QPen(QColor(255, 215, 0), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(full)

    def _draw_panel(self, p: QPainter, rec: Recommendation, cx: float, cy: float):
        pw, ph = 320, 224
        margin = 20
        px = cx + 58 if cx + 58 + pw + margin < self.width() else cx - pw - 58
        py = max(10, cy - ph // 2)

        p.setPen(QPen(QColor(255, 215, 0), 2))
        p.setBrush(QBrush(QColor(26, 26, 46, 220)))
        p.drawRoundedRect(QRectF(px, py, pw, ph), 10, 10)

        p.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        p.setPen(QColor(255, 215, 0))
        name = rec.card.name[:28] + "…" if len(rec.card.name) > 28 else rec.card.name
        p.drawText(int(px + 12), int(py + 26), f"▶ {name}")

        wr = rec.win_rate_estimate
        p.setFont(QFont("Arial", 10))
        p.setPen(QColor(200, 200, 200))
        p.drawText(int(px + 12), int(py + 48), f"推薦勝率估計: {wr:.0f}%")

        bx, by, bw, bh = px + 12, py + 54, pw - 24, 10
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(60, 60, 80)))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
        bar_color = (QColor(76, 175, 80) if wr >= 60
                     else QColor(255, 152, 0) if wr >= 50
                     else QColor(244, 67, 54))
        p.setBrush(QBrush(bar_color))
        p.drawRoundedRect(QRectF(bx, by, (wr / 100) * bw, bh), 4, 4)

        p.setFont(QFont("Arial", 9))
        ty = int(py + 82)
        for label, val in [("基礎分", rec.base), ("種族協同", rec.tribe_bonus),
                            ("套牌完整", rec.comp_bonus), ("成長性", rec.scaling_bonus),
                            ("剋制對手", rec.counter_bonus)]:
            col = (QColor(76,175,80) if val > 0 else
                   QColor(244,67,54) if val < 0 else QColor(150,150,150))
            p.setPen(col)
            p.drawText(int(px + 12), ty, f"{label}: {'+' if val>0 else ''}{val:.1f}")
            ty += 16

        p.setPen(QColor(220, 220, 220))
        ry = ty + 6
        for reason in rec.reasons[:3]:
            text = reason[:42] + "…" if len(reason) > 42 else reason
            p.drawText(int(px + 12), ry, f"• {text}")
            ry += 16
            if ry > py + ph - 8:
                break

    def _draw_rank_badge(self, p: QPainter, cx: float, cy: float, rank: int):
        r, alpha = 14, (160 if rank == 2 else 110)
        p.setPen(QPen(QColor(200, 200, 200, alpha), 1))
        p.setBrush(QBrush(QColor(0, 0, 0, alpha)))
        p.drawEllipse(QPointF(cx, cy - 30), r, r)
        p.setPen(QColor(255, 255, 255, alpha))
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.drawText(int(cx - 4), int(cy - 30 + 5), str(rank))


# ── Window ────────────────────────────────────────────────────────────────────

class OverlayWindow(QMainWindow):
    """Top-level frameless transparent always-on-top window."""

    def __init__(self, state: GameState):
        super().__init__()
        self.state   = state
        self.advisor = Advisor(state)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(config.OVERLAY_OPACITY)

        self.canvas = OverlayCanvas(self)
        self.setCentralWidget(self.canvas)

        # Periodic refresh from the main thread (backup for when no signal fires)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(config.POLL_INTERVAL_MS)

    def show_over_game(self, x: int, y: int, w: int, h: int):
        self.setGeometry(x, y, w, h)
        self.show()
        self.raise_()
        self.activateWindow()
        _apply_platform_flags(self)
        log.info("Overlay visible at %d,%d  %dx%d", x, y, w, h)

    # ── Thread-safe refresh ───────────────────────────────────────────────

    def force_refresh(self):
        """Safe to call from any thread — posts refresh to the Qt event loop."""
        QTimer.singleShot(0, self._refresh)

    @pyqtSlot()
    def _refresh(self):
        """Always runs on the main thread (called by QTimer)."""
        if self.state.phase != "SHOPPING":
            self.canvas.set_state([], 0, self.state.phase)
            return

        recs = self.advisor.recommend()
        self.canvas.set_state(recs, len(self.state.tavern_cards), self.state.phase)
