"""
Tribe and keyword synergy definitions used by the scoring engine.

TRIBE_WEIGHTS maps (tribe → dict of {synergy_card_name → bonus_score}).
COMP_PACKAGES defines "full deck archetypes" — what a complete comp looks like.
"""
from typing import Dict, List

# How many same-tribe cards before we commit to that tribe
TRIBE_COMMIT_THRESHOLD = 3

# Base scaling bonus per tribe card when tribe count >= threshold
TRIBE_BONUS_PER_CARD = 1.2

# Keyword synergy bonuses (card has keyword X → bonus when already on board)
KEYWORD_SYNERGY: Dict[str, float] = {
    "divine_shield": 1.5,
    "poisonous":     2.0,
    "deathrattle":   1.0,
    "reborn":        0.8,
    "windfury":      0.7,
    "taunt":         0.5,
}

# Counter bonuses: if opponent_tribes contains key, buying a card with value in tribes is a bonus
COUNTER_MAP: Dict[str, List[str]] = {
    "Mech":    ["Beast"],         # Cave Hydra/Maexxna kills Mechs easily
    "Divine Shield": ["Cleave", "Beast"],  # AoE cleave ignores divine shields
    "Murloc":  ["Elemental"],     # big Elementals out-stat Murlocs
    "Demon":   ["Mech"],          # Mechs with divine shield counter Demons
    "Dragon":  ["Undead"],        # Undead deathrattles grind out Dragons
}

# "Complete comp" archetypes: the synergy name → list of must-have card names
COMP_PACKAGES: Dict[str, List[str]] = {
    "Mech Deathrattle": [
        "Kangor's Apprentice", "Deflect-o-Bot", "Junkbot", "Baron Rivendare"
    ],
    "Murloc": [
        "Murloc Warleader", "Coldlight Seer", "Gentle Megasaur", "Murloc Tidecaller"
    ],
    "Dragon Ramp": [
        "Razorgore the Untamed", "Cobalt Scalebane", "Herald of Flame", "Rock Master Voone"
    ],
    "Demon Flood": [
        "Mal'Ganis", "Imp Mama", "Floating Watcher", "Nathrezim Overseer"
    ],
    "Elemental": [
        "Lil' Rag", "Nomi, Kitchen Nightmare", "Party Elemental", "Arcane Assistant"
    ],
    "Undead DR": [
        "Baron Rivendare", "Ghastcoiler", "Lich King", "Sire Denathrius"
    ],
    "Quilboar Blood Gem": [
        "Hoggar", "Bristleback Knight", "Selfless Hero"
    ],
    "Pirate": [
        "Captain Flat Tusk", "Sky Pirate", "Tavern Tipper"
    ],
    "Brann Battlecry": [
        "Brann Bronzebeard", "Coldlight Seer", "Murloc Warleader", "Nathrezim Overseer"
    ],
}

# Min-cost-tier to transition strategies (don't switch if past this turn)
STRATEGY_LOCK_TURN = 6
