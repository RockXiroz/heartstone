"""
Central configuration for the BG Overlay.
All screen-position constants are expressed as fractions of the game window
so they stay correct regardless of resolution.
"""
import os
import sys
from pathlib import Path

# ── Log file paths ───────────────────────────────────────────────────────────
def get_log_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Blizzard" / "Hearthstone" / "Logs"
    else:  # macOS
        base = Path.home() / "Library" / "Logs" / "Blizzard" / "Hearthstone"
    return base / "Power.log"

LOG_PATH = get_log_path()

# ── Overlay appearance ───────────────────────────────────────────────────────
OVERLAY_OPACITY = 0.93          # global window opacity
ARROW_COLOR     = "#FFFFFF"     # recommendation arrow colour
ARROW_GLOW      = "#FFD700"     # glow halo colour (gold)
PANEL_BG        = "#1A1A2E"     # info panel background
PANEL_BORDER    = "#FFD700"
TEXT_PRIMARY    = "#FFFFFF"
TEXT_SECONDARY  = "#AAAAAA"
SCORE_GOOD      = "#4CAF50"
SCORE_OK        = "#FF9800"
SCORE_BAD       = "#F44336"

# ── Tavern card screen positions (relative to game window 0-1) ───────────────
# These match the default Hearthstone BG layout on a 16:9 screen.
# Y is measured from top of game client.
TAVERN_ROW_Y   = 0.265          # vertical centre of top tavern row
TAVERN_CARD_W  = 0.067          # width of one card slot
TAVERN_CARD_H  = 0.22           # height of one card slot
# X start/end of the full tavern area (all 7 slots)
TAVERN_X_START = 0.245
TAVERN_X_END   = 0.875
# Computed slot centres (populated at runtime)
TAVERN_SLOTS   = 7              # max cards in tier-6 tavern

# ── Update rate ──────────────────────────────────────────────────────────────
POLL_INTERVAL_MS = 800          # overlay refresh rate

# ── Debug ────────────────────────────────────────────────────────────────────
DEBUG_MODE      = "--debug" in sys.argv
SIMULATE_MODE   = "--simulate" in sys.argv   # run without real game
