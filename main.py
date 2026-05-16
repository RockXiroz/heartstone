#!/usr/bin/env python3
"""
Hearthstone Battlegrounds Overlay Helper
========================================
Reads the game log in real-time, scores every card in your tavern, and
draws a transparent arrow pointing at the highest-win-rate pick.

Usage
-----
  python main.py              # normal mode (game must be running)
  python main.py --simulate   # demo mode — no game needed
  python main.py --debug      # verbose logging

Requirements
------------
  pip install -r requirements.txt
"""
import sys
import logging
import time

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

import config
from src.game_state import GameState
from src.overlay import OverlayWindow
from src.window_finder import find_hearthstone_window

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG_MODE else logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def _locate_game(overlay: OverlayWindow) -> bool:
    """Find the HS window and position the overlay over it."""
    rect = find_hearthstone_window()
    if rect:
        x, y, w, h = rect
        overlay.show_over_game(x, y, w, h)
        log.info("Hearthstone window found at %d,%d size %dx%d", x, y, w, h)
        return True
    return False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BG Overlay Helper")

    state   = GameState()
    overlay = OverlayWindow(state)

    # ── Simulation mode ───────────────────────────────────────────────────
    if config.SIMULATE_MODE:
        log.info("Running in SIMULATE mode — no Hearthstone required")
        from src.simulator import run_simulation

        # Position overlay at a sensible demo size
        screen = app.primaryScreen()
        if screen:
            geom = screen.geometry()
            sw, sh = geom.width(), geom.height()
        else:
            sw, sh = 1920, 1080

        overlay.show_over_game(0, 0, sw, sh)
        run_simulation(state, overlay.force_refresh)
        sys.exit(app.exec())

    # ── Real mode ─────────────────────────────────────────────────────────
    from src.log_reader import LogReader

    if not config.LOG_PATH.exists():
        log.warning(
            "Power.log not found at %s\n"
            "Make sure Hearthstone is running and logging is enabled.\n"
            "See README for how to enable the log.",
            config.LOG_PATH,
        )

    reader = LogReader(
        log_path  = config.LOG_PATH,
        state     = state,
        on_update = overlay.force_refresh,
    )
    reader.start()

    # Try to find the game window; retry every 5 s if not found yet
    found = _locate_game(overlay)

    def _retry_window():
        nonlocal found
        if not found:
            found = _locate_game(overlay)

    retry_timer = QTimer()
    retry_timer.timeout.connect(_retry_window)
    retry_timer.start(5000)

    log.info("Overlay running. Press Ctrl+C to quit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
