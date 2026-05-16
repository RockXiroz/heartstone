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
  python main.py --test       # show a fixed arrow to verify overlay is visible
  python main.py --debug      # verbose logging

Requirements
------------
  pip install -r requirements.txt
  pip install pyobjc-framework-AppKit pyobjc-framework-Quartz   # macOS only
"""
import sys
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

import config
from src.game_state import GameState
from src.overlay import OverlayWindow
from src.window_finder import find_hearthstone_window

TEST_MODE = "--test" in sys.argv

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG_MODE else logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def _run_test_mode(app: QApplication, state: GameState, overlay: OverlayWindow):
    """
    --test: fill state with fake shopping data and cover the full screen.
    Use this to verify the overlay window is visible before connecting to the game.
    """
    log.info("TEST MODE — fixed arrow shown on primary screen. Press Ctrl+C to quit.")
    from src.simulator import run_simulation

    screen = app.primaryScreen()
    geom   = screen.geometry() if screen else None
    sw     = geom.width()  if geom else 1920
    sh     = geom.height() if geom else 1080

    overlay.show_over_game(0, 0, sw, sh)
    run_simulation(state, overlay.force_refresh)
    sys.exit(app.exec())


def _run_simulate_mode(app: QApplication, state: GameState, overlay: OverlayWindow):
    log.info("SIMULATE MODE — no Hearthstone required.")
    from src.simulator import run_simulation

    screen = app.primaryScreen()
    geom   = screen.geometry() if screen else None
    sw     = geom.width()  if geom else 1920
    sh     = geom.height() if geom else 1080

    overlay.show_over_game(0, 0, sw, sh)
    run_simulation(state, overlay.force_refresh)
    sys.exit(app.exec())


def _locate_game(overlay: OverlayWindow) -> bool:
    rect = find_hearthstone_window()
    if rect:
        x, y, w, h = rect
        overlay.show_over_game(x, y, w, h)
        log.info("Hearthstone found at %d,%d  %dx%d", x, y, w, h)
        return True
    return False


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BG Overlay Helper")

    state   = GameState()
    overlay = OverlayWindow(state)

    if TEST_MODE:
        _run_test_mode(app, state, overlay)

    if config.SIMULATE_MODE:
        _run_simulate_mode(app, state, overlay)

    # ── Real mode ─────────────────────────────────────────────────────────
    from src.log_reader import LogReader

    if not config.LOG_PATH.exists():
        log.warning(
            "Power.log not found at:\n  %s\n"
            "Run  python enable_hs_logging.py  then restart Hearthstone.",
            config.LOG_PATH,
        )

    reader = LogReader(
        log_path  = config.LOG_PATH,
        state     = state,
        on_update = overlay.force_refresh,
    )
    reader.start()

    found = _locate_game(overlay)
    if not found:
        log.warning(
            "Hearthstone window not found yet — overlay will appear automatically "
            "once the game starts."
        )

    retry = QTimer()
    retry.timeout.connect(lambda: _locate_game(overlay) or None)
    retry.start(5000)

    log.info("Overlay running.  Tip: run with --test to verify visibility first.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
