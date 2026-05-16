"""
Transparent PyQt6 overlay window that draws recommendation arrows and an
info panel on top of the Hearthstone game window.

The window is:
  • Always-on-top
  • Fully transparent background
  • Click-through (user input passes through to the game)

On Windows the WS_EX_TRANSPARENT + WS_EX_LAYERED styles are applied.
On macOS the NSWindow floating level handles it.
"""
from __future__ import annotations

import sys
import math
import logging
from typing import Optional, List

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPolygonF,
    QLinearGradient, QRadialGradient, QPainterPath,
)
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from src.game_state import GameState
from src.advisor import Advisor, Recommendation
import config

log = logging.getLogger(__name__)


def _make_click_through(window: QMainWindow):
    """Apply OS-specific click-through so mouse events pass to the game."""
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd  = int(window.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # WS_EX_LAYERED | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
        except Exception as e:
            log.warning("click-through setup failed: %s", e)
    # macOS: Qt Tool + TranslucentBackground is sufficient


class OverlayCanvas(QWidget):
    """The painting surface that draws arrows and the info panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._recs: List[Recommendation] = []
        self._show_panel = True

    def update_recommendations(self, recs: List[Recommendation]):
        self._recs = recs
        self.update()

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        if not self._recs:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        best = self._recs[0]
        cx, cy = self._card_centre(best.board_index)

        self._draw_glow(p, cx, cy)
        self._draw_arrow(p, cx, cy)
        if self._show_panel:
            self._draw_panel(p, best, cx, cy)

        # Draw dimmer rank badges for 2nd / 3rd picks
        for rank, rec in enumerate(self._recs[1:3], start=2):
            rx, ry = self._card_centre(rec.board_index)
            self._draw_rank_badge(p, rx, ry, rank)

        p.end()

    # ── Card position helpers ─────────────────────────────────────────────
    def _card_centre(self, slot: int) -> tuple[float, float]:
        """
        Return pixel (x, y) for tavern card at `slot` index,
        relative to this widget's coordinate system.
        """
        w = self.width()
        h = self.height()
        n = max(len(self._recs), 1)

        # Distribute slots evenly across the tavern X range
        x_start = config.TAVERN_X_START * w
        x_end   = config.TAVERN_X_END   * w
        step    = (x_end - x_start) / max(n - 1, 1) if n > 1 else 0
        x       = x_start + slot * step
        y       = config.TAVERN_ROW_Y * h
        return x, y

    # ── Drawing primitives ────────────────────────────────────────────────
    def _draw_glow(self, p: QPainter, cx: float, cy: float):
        radius = 70
        grad = QRadialGradient(QPointF(cx, cy), radius)
        grad.setColorAt(0.0, QColor(255, 215, 0, 160))
        grad.setColorAt(0.6, QColor(255, 215, 0, 40))
        grad.setColorAt(1.0, QColor(255, 215, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

    def _draw_arrow(self, p: QPainter, cx: float, cy: float):
        """Draw a downward-pointing arrow above the target card."""
        tip_y     = cy - 15          # arrowhead tip (near card top)
        tail_y    = tip_y - 70       # shaft top
        shaft_w   = 10
        head_h    = 30
        head_w    = 34

        # Shaft
        shaft_path = QPainterPath()
        shaft_path.addRect(QRectF(cx - shaft_w/2, tail_y, shaft_w, tip_y - tail_y - head_h))

        # Arrowhead triangle
        head_path = QPainterPath()
        head_path.moveTo(cx, tip_y)
        head_path.lineTo(cx - head_w/2, tip_y - head_h)
        head_path.lineTo(cx + head_w/2, tip_y - head_h)
        head_path.closeSubpath()

        full = shaft_path.united(head_path)

        # White fill
        p.setPen(QPen(QColor(0, 0, 0, 180), 2))
        p.setBrush(QBrush(QColor(255, 255, 255, 230)))
        p.drawPath(full)

        # Gold outline
        p.setPen(QPen(QColor(255, 215, 0), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(full)

    def _draw_panel(self, p: QPainter, rec: Recommendation, cx: float, cy: float):
        """Draw the info panel to the right of the arrow."""
        pw, ph = 320, 220
        margin = 20
        w = self.width()

        # Prefer right side; flip left if near edge
        px = cx + 55 if cx + 55 + pw + margin < w else cx - pw - 55
        py = cy - ph // 2

        # Panel background
        bg = QColor(26, 26, 46, 220)
        border = QColor(255, 215, 0)
        p.setPen(QPen(border, 2))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(px, py, pw, ph), 10, 10)

        # Title
        p.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        p.setPen(QColor(255, 215, 0))
        p.drawText(int(px + 12), int(py + 26), f"▶ {rec.card.name}")

        # Win-rate bar
        wr = rec.win_rate_estimate
        p.setFont(QFont("Arial", 10))
        p.setPen(QColor(200, 200, 200))
        p.drawText(int(px + 12), int(py + 48), f"推薦勝率估計: {wr:.0f}%")

        bar_x, bar_y, bar_w, bar_h = px + 12, py + 54, pw - 24, 10
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(60, 60, 80)))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)
        fill_w = (wr / 100) * bar_w
        bar_color = (QColor(76, 175, 80) if wr >= 60
                     else QColor(255, 152, 0) if wr >= 50
                     else QColor(244, 67, 54))
        p.setBrush(QBrush(bar_color))
        p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

        # Score breakdown
        p.setFont(QFont("Arial", 9))
        p.setPen(QColor(170, 170, 170))
        breakdown_y = int(py + 80)
        scores = [
            ("基礎分",   rec.base),
            ("種族協同", rec.tribe_bonus),
            ("套牌完整", rec.comp_bonus),
            ("成長性",   rec.scaling_bonus),
            ("剋制對手", rec.counter_bonus),
        ]
        for label, val in scores:
            color = (QColor(76, 175, 80) if val > 0
                     else QColor(244, 67, 54) if val < 0
                     else QColor(150, 150, 150))
            p.setPen(color)
            sign = "+" if val > 0 else ""
            p.drawText(int(px + 12), breakdown_y, f"{label}: {sign}{val:.1f}")
            breakdown_y += 16

        # Reasons
        p.setFont(QFont("Arial", 9))
        p.setPen(QColor(220, 220, 220))
        reason_y = breakdown_y + 6
        for reason in rec.reasons[:3]:
            # Word-wrap at 44 chars
            if len(reason) > 44:
                reason = reason[:42] + "…"
            p.drawText(int(px + 12), reason_y, f"• {reason}")
            reason_y += 16
            if reason_y > py + ph - 12:
                break

    def _draw_rank_badge(self, p: QPainter, cx: float, cy: float, rank: int):
        """Small numbered badge for 2nd/3rd best options."""
        r = 14
        alpha = 160 if rank == 2 else 110
        p.setPen(QPen(QColor(200, 200, 200, alpha), 1))
        p.setBrush(QBrush(QColor(0, 0, 0, alpha)))
        p.drawEllipse(QPointF(cx, cy - 28), r, r)
        p.setPen(QColor(255, 255, 255, alpha))
        p.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        p.drawText(int(cx - 4), int(cy - 28 + 5), str(rank))


class OverlayWindow(QMainWindow):
    """Top-level always-on-top transparent window."""

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

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(config.POLL_INTERVAL_MS)

    def show_over_game(self, game_x: int, game_y: int, game_w: int, game_h: int):
        self.setGeometry(game_x, game_y, game_w, game_h)
        self.show()
        _make_click_through(self)
        log.info("Overlay shown at %d,%d size %dx%d", game_x, game_y, game_w, game_h)

    def force_refresh(self):
        self._refresh()

    def _refresh(self):
        if self.state.phase != "SHOPPING":
            self.canvas.update_recommendations([])
            return

        recs = self.advisor.recommend()
        self.canvas.update_recommendations(recs)
        if recs and config.DEBUG_MODE:
            log.debug(
                "Best pick: %s  score=%.2f  wr=%.0f%%",
                recs[0].card.name, recs[0].total_score, recs[0].win_rate_estimate,
            )
