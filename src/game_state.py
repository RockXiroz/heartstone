"""
Tracks the full game state derived from the Hearthstone Power.log parser.

The log parser feeds raw events here; this module maintains the authoritative
snapshot of what's on the board, in the tavern, and on opponent boards.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from src.data.cards import BGCard, find_card


@dataclass
class BoardMinion:
    card_id: str
    entity_id: int
    name: str
    attack: int
    health: int
    max_health: int
    keywords: List[str] = field(default_factory=list)
    golden: bool = False
    card: Optional[BGCard] = None

    def __post_init__(self):
        if self.card is None:
            self.card = find_card(self.card_id) or find_card(self.name)


@dataclass
class OpponentBoard:
    player_id: int
    hero_name: str
    minions: List[BoardMinion] = field(default_factory=list)
    health: int = 40
    last_seen_turn: int = 0


@dataclass
class GameState:
    # Current player info
    player_id: int = 0
    hero_name: str = ""
    health: int = 40
    tavern_tier: int = 1
    gold: int = 3
    turn: int = 1

    # Phase
    phase: str = "UNKNOWN"   # "SHOPPING" | "COMBAT" | "UNKNOWN"

    # Cards currently in the tavern (available to buy)
    tavern_cards: List[BoardMinion] = field(default_factory=list)

    # Player's current board
    player_board: List[BoardMinion] = field(default_factory=list)

    # Frozen cards (leftover from last turn)
    frozen_cards: List[BoardMinion] = field(default_factory=list)

    # Opponent boards seen this game (keyed by player_id)
    opponent_boards: Dict[int, OpponentBoard] = field(default_factory=dict)

    # Tribes present on player board
    @property
    def player_tribes(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for m in self.player_board:
            for t in (m.card.tribes if m.card else []):
                counts[t] = counts.get(t, 0) + 1
        return counts

    # Tribes seen on opponent boards (aggregate)
    @property
    def opponent_tribes(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for ob in self.opponent_boards.values():
            for m in ob.minions:
                for t in (m.card.tribes if m.card else []):
                    counts[t] = counts.get(t, 0) + 1
        return counts

    def dominant_tribe(self) -> Optional[str]:
        """The tribe with the most cards on the player's board, or None."""
        tribes = self.player_tribes
        if not tribes:
            return None
        best = max(tribes, key=lambda t: tribes[t])
        return best if tribes[best] >= 2 else None

    def add_opponent_board(self, opponent: OpponentBoard):
        self.opponent_boards[opponent.player_id] = opponent

    def reset_tavern(self):
        self.tavern_cards = []

    def snapshot(self) -> dict:
        return {
            "turn": self.turn,
            "phase": self.phase,
            "tier": self.tavern_tier,
            "health": self.health,
            "tavern": [m.name for m in self.tavern_cards],
            "board": [m.name for m in self.player_board],
            "dominant_tribe": self.dominant_tribe(),
        }
