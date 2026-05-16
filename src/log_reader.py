"""
Reads Hearthstone's Power.log in real-time and translates raw log lines
into GameState updates.

Hearthstone writes structured log lines.  The key patterns we parse:

  FULL_ENTITY – a new entity appearing (new card entering any zone)
  TAG_CHANGE   – an entity attribute changing (zone, health, attack …)
  BLOCK_START  – start of a game action (attack, trigger, power …)

BG-specific zone assignment:
  Zone PLAY     + our player → player board
  Zone HAND     + BG_Bob id → tavern cards ready to buy
  Zone SETASIDE → cards waiting in the tavern pool
"""
from __future__ import annotations
import re
import time
import threading
from pathlib import Path
from typing import Callable, Optional
import logging

from src.game_state import GameState, BoardMinion, OpponentBoard
from src.data.cards import find_card

log = logging.getLogger(__name__)

# ── Regex patterns ─────────────────────────────────────────────────────────
RE_FULL_ENTITY  = re.compile(
    r"FULL_ENTITY.*?CardID=(?P<card_id>\S+)")
RE_TAG_CHANGE   = re.compile(
    r"TAG_CHANGE Entity=(?P<entity>.+?) tag=(?P<tag>\S+) value=(?P<value>\S+)")
RE_SHOW_ENTITY  = re.compile(
    r"SHOW_ENTITY.*?CardID=(?P<card_id>\S+)")
RE_ENTITY_ID    = re.compile(r"\[id=(?P<id>\d+)")
RE_BLOCK_START  = re.compile(
    r"BLOCK_START BlockType=(?P<type>\S+).*?Entity=(?P<entity>.+?) ")
RE_BLOCK_END    = re.compile(r"BLOCK_END")

# BG phase triggers — Blizzard has renamed these across patches, so we match
# any known variant.  A line must also contain "BLOCK_START" to qualify.
SHOP_TRIGGERS = [
    "TB_BaconShop_SetAside_enchantment",   # original
    "TB_BaconShop_SetAside",               # abbreviated form seen in some logs
    "TB_BaconShopPhase",                   # newer patch variant
    "BaconShop_SetAside",                  # another abbreviation
]
COMBAT_TRIGGERS = [
    "TB_BaconShop_8p_Phase_Main",
    "TB_BaconShop_Combat",
    "BaconShop_Combat",
]
BOB_NAME = "TB_BaconShopBob"

# Zone constants
ZONE_PLAY     = "PLAY"
ZONE_HAND     = "HAND"
ZONE_SETASIDE = "SETASIDE"
ZONE_DECK     = "DECK"


class Entity:
    """Lightweight representation of any game entity."""
    __slots__ = ("entity_id", "card_id", "name", "tags")

    def __init__(self, entity_id: int, card_id: str = "", name: str = ""):
        self.entity_id = entity_id
        self.card_id   = card_id
        self.name      = name
        self.tags: dict[str, str] = {}

    def zone(self) -> str:
        return self.tags.get("ZONE", "")

    def controller(self) -> str:
        return self.tags.get("CONTROLLER", "")

    def attack(self) -> int:
        return int(self.tags.get("ATK", 0))

    def health(self) -> int:
        return int(self.tags.get("HEALTH", 0))

    def is_golden(self) -> bool:
        return self.tags.get("PREMIUM", "0") == "1"


class LogReader:
    """
    Tails Power.log and maintains a live GameState.
    Call `start()` to begin reading in a background thread.
    Pass an `on_update` callback to be notified whenever the state changes.
    """

    def __init__(self,
                 log_path: Path,
                 state: GameState,
                 on_update: Optional[Callable[[], None]] = None):
        self.log_path   = log_path
        self.state      = state
        self.on_update  = on_update
        self._entities: dict[int, Entity] = {}
        self._bob_id: Optional[int] = None
        self._player_controller: str = "1"
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Public API ────────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._tail_loop, daemon=True)
        self._thread.start()
        log.info("LogReader started, watching %s", self.log_path)

    def stop(self):
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────
    def _tail_loop(self):
        while self._running and not self.log_path.exists():
            log.debug("Waiting for log file …")
            time.sleep(2)

        with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)   # jump to end, skip historical data
            while self._running:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                self._parse_line(line.rstrip())

    def _parse_line(self, line: str):
        changed = False

        # Detect shopping phase — try all known trigger strings
        if "BLOCK_START" in line:
            if any(t in line for t in SHOP_TRIGGERS):
                if self.state.phase != "SHOPPING":
                    self.state.phase = "SHOPPING"
                    self.state.turn += 1
                    self.state.reset_tavern()
                    log.debug("Phase → SHOPPING (turn %d)", self.state.turn)
                    changed = True
            elif any(t in line for t in COMBAT_TRIGGERS):
                if self.state.phase != "COMBAT":
                    self.state.phase = "COMBAT"
                    log.debug("Phase → COMBAT")
                    changed = True

        # Track entities
        m = RE_FULL_ENTITY.search(line) or RE_SHOW_ENTITY.search(line)
        if m:
            eid = self._extract_entity_id(line)
            card_id = m.group("card_id")
            if eid:
                entity = self._entities.setdefault(eid, Entity(eid))
                entity.card_id = card_id
                if card_id == BOB_NAME:
                    self._bob_id = eid

        # Tag changes
        m2 = RE_TAG_CHANGE.search(line)
        if m2:
            entity_ref = m2.group("entity")
            tag        = m2.group("tag")
            value      = m2.group("value")
            eid2 = self._resolve_entity_id(entity_ref)
            if eid2 and eid2 in self._entities:
                entity = self._entities[eid2]
                entity.tags[tag] = value

                # Sync player ID
                if tag == "PLAYER_ID" and value == "1":
                    self._player_controller = entity.tags.get("CONTROLLER", "1")

                # React to zone changes
                if tag == "ZONE":
                    changed |= self._on_zone_change(entity, value)

                # Tavern tier
                if tag == "PLAYER_TAVERN_TIER" and entity.controller() == self._player_controller:
                    tier = int(value)
                    if tier != self.state.tavern_tier:
                        self.state.tavern_tier = tier
                        log.debug("Tavern tier → %d", tier)
                        changed = True

                # Health
                if tag == "HEALTH" and entity.controller() == self._player_controller:
                    if entity.zone() == "PLAY" and entity.card_id.startswith("TB_BaconShop_HERO"):
                        self.state.health = int(value)
                        changed = True

        if changed and self.on_update:
            self.on_update()

    def _on_zone_change(self, entity: Entity, new_zone: str) -> bool:
        card = find_card(entity.card_id) or find_card(entity.name)
        if card is None:
            return False

        minion = BoardMinion(
            card_id   = entity.card_id,
            entity_id = entity.entity_id,
            name      = entity.name or card.name,
            attack    = entity.attack() or card.attack,
            health    = entity.health() or card.health,
            max_health= entity.health() or card.health,
            keywords  = list(card.keywords),
            golden    = entity.is_golden(),
            card      = card,
        )

        controller = entity.controller()

        # Cards entering PLAY for the player
        if new_zone == ZONE_PLAY and controller == self._player_controller:
            if not any(m.entity_id == entity.entity_id for m in self.state.player_board):
                self.state.player_board.append(minion)
            return True

        # Cards leaving PLAY for the player (died or sold)
        if new_zone != ZONE_PLAY and controller == self._player_controller:
            self.state.player_board = [
                m for m in self.state.player_board
                if m.entity_id != entity.entity_id
            ]
            return True

        # Cards entering HAND from Bob = tavern offerings
        if (new_zone == ZONE_HAND
                and self._bob_id is not None
                and controller == str(self._bob_id)):
            if not any(m.entity_id == entity.entity_id for m in self.state.tavern_cards):
                self.state.tavern_cards.append(minion)
            return True

        return False

    @staticmethod
    def _extract_entity_id(line: str) -> Optional[int]:
        m = RE_ENTITY_ID.search(line)
        return int(m.group("id")) if m else None

    def _resolve_entity_id(self, ref: str) -> Optional[int]:
        """Resolve an entity reference string to an integer ID."""
        m = RE_ENTITY_ID.search(ref)
        if m:
            return int(m.group("id"))
        # Try matching by name
        for eid, entity in self._entities.items():
            if entity.name == ref or entity.card_id == ref:
                return eid
        try:
            return int(ref)
        except ValueError:
            return None
