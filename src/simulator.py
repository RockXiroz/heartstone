"""
Simulation mode: feeds a fake game state into the overlay so the UI can be
tested without a running Hearthstone client.

Usage: python main.py --simulate
"""
from __future__ import annotations
import time
import threading
import logging

from src.game_state import GameState, BoardMinion, OpponentBoard
from src.data.cards import ALL_CARDS, TIER3, TIER4, TIER5

log = logging.getLogger(__name__)


def _make_minion(card_id: str) -> BoardMinion | None:
    from src.data.cards import find_card
    card = find_card(card_id)
    if card is None:
        return None
    return BoardMinion(
        card_id    = card.card_id,
        entity_id  = hash(card.card_id) & 0xFFFF,
        name       = card.name,
        attack     = card.attack,
        health     = card.health,
        max_health = card.health,
        keywords   = list(card.keywords),
        golden     = False,
        card       = card,
    )


def run_simulation(state: GameState, on_update):
    """Populate state with a realistic mid-game scenario and keep cycling."""

    def _setup():
        state.player_id   = 1
        state.hero_name   = "George the Fallen"
        state.health      = 28
        state.tavern_tier = 3
        state.gold        = 6
        state.turn        = 5
        state.phase       = "SHOPPING"

        # Player board — partial Mech comp
        for cid in ["BG_ICC_807", "BG_GVG_006", "BG_OG_006"]:   # Deflect-o-Bot, Screwjank, Selfless Hero
            m = _make_minion(cid)
            if m:
                state.player_board.append(m)

        # Tavern offerings
        tavern_card_ids = [
            "BG_BOT_606",   # Kangor's Apprentice  ← strong Mech DR pick
            "BG_GIL_905",   # Cave Hydra
            "BG_CS2_182",   # Bloodsail Corsair
            "BG21_023",     # Arcane Assistant
            "BG_CFM_315",   # Nathrezim Overseer
        ]
        for i, cid in enumerate(tavern_card_ids):
            m = _make_minion(cid)
            if m:
                state.tavern_cards.append(m)

        # Opponent boards
        opp1 = OpponentBoard(player_id=2, hero_name="Alexstrasza", health=35, last_seen_turn=4)
        for cid in ["BG_GVG_075", "BG_TRL_537", "BG21_017"]:    # Murloc board
            m = _make_minion(cid)
            if m:
                opp1.minions.append(m)
        state.add_opponent_board(opp1)

        opp2 = OpponentBoard(player_id=3, hero_name="Reno Jackson", health=30, last_seen_turn=3)
        for cid in ["BG_GVG_113", "BG_ICC_807"]:                 # Mech comp
            m = _make_minion(cid)
            if m:
                opp2.minions.append(m)
        state.add_opponent_board(opp2)

        on_update()
        log.info("[SIMULATE] Initial state loaded")

    def _cycle():
        """Every 8 s rotate to a new tavern hand so the demo keeps moving."""
        while True:
            time.sleep(8)
            state.reset_tavern()
            # pull 4 random different cards each cycle
            import random
            picks = random.sample(ALL_CARDS, 5)
            for i, card in enumerate(picks):
                m = _make_minion(card.card_id)
                if m:
                    state.tavern_cards.append(m)
            on_update()
            log.info("[SIMULATE] Tavern refreshed")

    threading.Thread(target=_setup, daemon=True).start()
    threading.Thread(target=_cycle, daemon=True).start()
