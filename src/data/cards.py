"""
Hearthstone Battlegrounds minion database.

base_score  : raw win-rate contribution (0-10), higher is better
scaling     : long-game value multiplier (0-1)
synergies   : other card/tribe names this card amplifies
counters    : opponent tribe keywords this card counters
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class BGCard:
    card_id: str
    name: str
    tier: int
    attack: int
    health: int
    tribes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)   # divine_shield taunt poisonous reborn rush windfury deathrattle battlecry
    text: str = ""
    synergies: List[str] = field(default_factory=list)
    counters: List[str] = field(default_factory=list)
    base_score: float = 5.0
    scaling: float = 0.5
    notes: str = ""


# ── Tier 1 ───────────────────────────────────────────────────────────────────
TIER1: List[BGCard] = [
    BGCard("BG_MUUR001",  "Murloc Tidecaller",    1, 1, 2,  ["Murloc"],
           text="+1 ATK whenever a Murloc is summoned.",
           synergies=["Murloc"], base_score=6.5, scaling=0.7,
           notes="Snowballs hard in full Murloc boards."),

    BGCard("BG_CS2_125",  "Righteous Protector",  1, 1, 1,  [],
           ["divine_shield","taunt"],
           text="Divine Shield, Taunt.",
           base_score=5.5, scaling=0.3,
           notes="Buys time early; falls off late."),

    BGCard("BG_WC_003",   "Wrath Weaver",         1, 1, 3,  [],
           text="After you play a Demon, +2 ATK (set each turn).",
           synergies=["Demon"], base_score=5.0, scaling=0.6),

    BGCard("BG_DRG_900",  "Sellemental",          1, 1, 1,  ["Elemental"],
           text="Sell me to get a 1/1 Elemental.",
           synergies=["Elemental"], base_score=4.5, scaling=0.3),

    BGCard("BG_SCH_149",  "Tavern Tipper",        1, 1, 1,  ["Pirate"],
           text="After you play a Pirate, get a Coin.",
           synergies=["Pirate"], base_score=5.5, scaling=0.5),

    BGCard("BG20_101",    "Micro Mummy",          1, 1, 2,  ["Mech"],
           ["reborn"],
           text="Reborn. At end of turn, give a random friendly minion +1 ATK.",
           synergies=["Mech"], base_score=5.5, scaling=0.5),

    BGCard("BG20_003",    "Rocking and Rolling",  1, 2, 1,  ["Quilboar"],
           text="Battlecry: Gain a Blood Gem.",
           synergies=["Quilboar"], base_score=4.5, scaling=0.4),

    BGCard("BG21_017",    "Lil' Rag",             1, 1, 1,  ["Elemental"],
           text="After you play an Elemental, give a random friendly minion stats equal to its cost.",
           synergies=["Elemental"], base_score=8.5, scaling=0.9,
           notes="Top Elemental enabler; buy and protect."),

    BGCard("BG23_001",    "Alebear",              1, 1, 2,  ["Beast"],
           text="After a friendly Mech attacks, gain +1/+1.",
           synergies=["Mech","Beast"], base_score=4.5, scaling=0.4),

    BGCard("BG_ULD_178",  "Rabid Saurolisk",      1, 3, 2,  ["Beast"],
           text="After you play a Deathrattle minion, gain +1/+1.",
           synergies=["Deathrattle"], base_score=5.0, scaling=0.5),
]

# ── Tier 2 ───────────────────────────────────────────────────────────────────
TIER2: List[BGCard] = [
    BGCard("BG_KARA_A_02","Annoy-o-Tron",         2, 1, 2,  ["Mech"],
           ["divine_shield","taunt"],
           text="Taunt, Divine Shield.",
           synergies=["Mech"], base_score=5.5, scaling=0.4),

    BGCard("BG_GVG_075",  "Coldlight Seer",       2, 2, 3,  ["Murloc"],
           text="Battlecry: Give all other Murlocs +2 health.",
           synergies=["Murloc"], base_score=7.0, scaling=0.7,
           notes="Critical mass piece; essential for Murloc board."),

    BGCard("BG_TRL_537",  "Murloc Warleader",     2, 3, 3,  ["Murloc"],
           text="Other Murlocs have +2 ATK.",
           synergies=["Murloc"], base_score=7.5, scaling=0.8,
           notes="Aura buff; golden is win condition."),

    BGCard("BG_OG_006",   "Selfless Hero",        2, 2, 1,  [],
           ["deathrattle"],
           text="Deathrattle: Give a random friendly minion Divine Shield.",
           base_score=6.0, scaling=0.6,
           notes="Excellent with Mechs and Divine Shield comps."),

    BGCard("BG_OG_121a",  "Scavenging Hyena",     2, 2, 1,  ["Beast"],
           text="Whenever a friendly Beast dies, gain +2/+1.",
           synergies=["Beast"], base_score=6.5, scaling=0.7),

    BGCard("BG_NEW1_041", "Dragonhawk Rider",     2, 1, 3,  [],
           text="Whenever you play a card with Windfury, give this minion Windfury for the turn.",
           base_score=4.5, scaling=0.4),

    BGCard("BG_TRL_232",  "Yo-Ho-Ogre",           2, 2, 6,  ["Pirate"],
           text="After this attacks, it attacks again.",
           synergies=["Pirate"], base_score=5.5, scaling=0.5),

    BGCard("BG_CFM_315",  "Nathrezim Overseer",   2, 2, 4,  ["Demon"],
           text="Battlecry: Give a friendly Demon +2/+2.",
           synergies=["Demon"], base_score=6.5, scaling=0.6),

    BGCard("BG_EX1_509",  "Murloc Tidehunter",    2, 2, 1,  ["Murloc"],
           text="Battlecry: Summon a 1/1 Murloc Scout.",
           synergies=["Murloc"], base_score=5.5, scaling=0.4),

    BGCard("BG_GVG_085",  "Harvest Golem",        2, 2, 3,  ["Mech"],
           ["deathrattle"],
           text="Deathrattle: Summon a 2/1 Damaged Golem.",
           synergies=["Mech","Deathrattle"], base_score=5.5, scaling=0.5),

    BGCard("BG20_302",    "Party Elemental",      2, 3, 2,  ["Elemental"],
           text="Whenever you play an Elemental, give a random friendly minion +1/+1.",
           synergies=["Elemental"], base_score=6.5, scaling=0.7),

    BGCard("BG21_002",    "Molten Rock",          2, 2, 4,  ["Elemental"],
           text="After you play a Spell, gain +1 health and Taunt.",
           synergies=["Elemental"], base_score=5.0, scaling=0.5,
           keywords=["taunt"]),

    BGCard("BG21_031",    "Qiraji Harbinger",     2, 2, 5,  [],
           text="Battlecry: Give Rush minions in your hand +2/+1.",
           synergies=["Rush"], base_score=5.0, scaling=0.4),

    BGCard("BG23_009",    "Mechano-Egg",          2, 0, 5,  ["Mech"],
           ["deathrattle"],
           text="Deathrattle: Summon an 8/8 Robosaur.",
           synergies=["Mech","Deathrattle"], base_score=5.5, scaling=0.6),

    BGCard("BG21_050",    "Blood Gem",            2, 0, 0,  ["Quilboar"],
           text="Give a minion +1/+1.",
           synergies=["Quilboar"], base_score=4.0, scaling=0.5),
]

# ── Tier 3 ───────────────────────────────────────────────────────────────────
TIER3: List[BGCard] = [
    BGCard("BG_GIL_681",  "Infested Wolf",        3, 3, 3,  ["Beast"],
           ["deathrattle"],
           text="Deathrattle: Summon two 1/1 Spiders.",
           synergies=["Beast","Deathrattle"], base_score=6.0, scaling=0.6),

    BGCard("BG_ULD_271",  "Tortollan Shellraiser",3, 2, 6,  [],
           ["taunt","deathrattle"],
           text="Taunt. Deathrattle: Give a random friendly minion +1/+1.",
           base_score=5.5, scaling=0.5),

    BGCard("BG_BOT_606",  "Kangor's Apprentice",  3, 3, 3,  ["Mech"],
           text="Deathrattle: Summon 2 of your Mechs that died (without enchantments).",
           keywords=["deathrattle"],
           synergies=["Mech","Deathrattle"], base_score=8.0, scaling=0.9,
           notes="Win condition for Mech Deathrattle boards."),

    BGCard("BG_ICC_807",  "Deflect-o-Bot",        3, 3, 3,  ["Mech"],
           ["divine_shield"],
           text="Divine Shield. Whenever you summon a Mech, gain +1 ATK and a Divine Shield.",
           synergies=["Mech"], base_score=8.5, scaling=0.9,
           notes="Exceptional; buy immediately if building Mechs."),

    BGCard("BG_GVG_006",  "Screwjank Clunker",    3, 2, 5,  ["Mech"],
           text="Battlecry: Give a friendly Mech +2/+2.",
           synergies=["Mech"], base_score=6.0, scaling=0.6),

    BGCard("BG_CS2_182",  "Bloodsail Corsair",    3, 1, 4,  ["Pirate"],
           text="Battlecry: If you have a Pirate, discover a Pirate.",
           synergies=["Pirate"], base_score=6.5, scaling=0.6),

    BGCard("BG_CS2_188",  "Houndmaster",          3, 4, 3,  [],
           text="Battlecry: Give a friendly Beast +2/+2 and Taunt.",
           synergies=["Beast"], base_score=6.0, scaling=0.6),

    BGCard("BG_GIL_905",  "Cave Hydra",           3, 2, 4,  ["Beast"],
           ["cleave"],
           text="Also damages the minions next to whomever this attacks.",
           synergies=["Beast"], base_score=7.5, scaling=0.8,
           counters=["Mech","Divine Shield"],
           notes="Destroys token/wide boards; excellent counter."),

    BGCard("BG_BOT_218",  "Khadgar",              3, 2, 2,  [],
           text="Whenever you summon a minion, summon a copy of it.",
           synergies=["Token","Beast","Murloc"], base_score=8.0, scaling=0.8,
           notes="Pairs with token generators; can explode a board."),

    BGCard("BG20_101b",   "Crystalweaver",        3, 5, 4,  ["Demon"],
           text="Battlecry: Give all friendly Demons +1/+1.",
           synergies=["Demon"], base_score=6.5, scaling=0.7),

    BGCard("BG_ICC_810",  "Cobalt Scalebane",     3, 5, 5,  ["Dragon"],
           text="At the end of your turn, give a random friendly minion +3 ATK.",
           synergies=["Dragon"], base_score=6.5, scaling=0.6),

    BGCard("BG21_023",    "Arcane Assistant",     3, 3, 3,  ["Elemental"],
           text="Battlecry: For each Elemental you've played, gain +1/+1.",
           synergies=["Elemental"], base_score=6.0, scaling=0.6),

    BGCard("BG20_204",    "Imprisoned Sungill",   3, 2, 2,  ["Murloc"],
           text="Reborn. After two other Murlocs are played, Awaken.",
           keywords=["reborn"],
           synergies=["Murloc"], base_score=5.5, scaling=0.5),

    BGCard("BG21_040",    "Bronze Warden",        3, 2, 1,  ["Dragon","Mech"],
           ["divine_shield","rush"],
           text="Rush, Divine Shield.",
           synergies=["Dragon","Mech"], base_score=6.5, scaling=0.5),

    BGCard("BG_GIL_598",  "Nightmare Amalgam",    3, 3, 4,  ["All"],
           text="This is every minion type.",
           synergies=["Murloc","Beast","Mech","Dragon","Demon","Elemental","Pirate","Quilboar","Naga","Undead"],
           base_score=6.5, scaling=0.7,
           notes="Activates ALL tribe synergies; flexible pick."),

    BGCard("BG21_044",    "Selfish Shellfish",    3, 2, 2,  ["Naga"],
           text="Deathrattle: Give the two highest Attack friendly minions +3 ATK.",
           keywords=["deathrattle"],
           synergies=["Naga"], base_score=6.5, scaling=0.6),

    BGCard("BG25_030",    "Ghoul of the Feast",   3, 2, 3,  ["Undead"],
           text="After a friendly minion dies, gain +1/+1.",
           synergies=["Undead","Deathrattle"], base_score=6.0, scaling=0.7),
]

# ── Tier 4 ───────────────────────────────────────────────────────────────────
TIER4: List[BGCard] = [
    BGCard("BG_GIL_116",  "Saronite Chain Gang",  4, 2, 3,  [],
           ["taunt"],
           text="Taunt. Battlecry: Summon a copy of this minion.",
           base_score=5.5, scaling=0.4),

    BGCard("BG_AT_108",   "Defender of Argus",    4, 2, 3,  [],
           text="Battlecry: Give adjacent minions +1/+1 and Taunt.",
           synergies=["Divine Shield","Aggro"], base_score=6.0, scaling=0.5),

    BGCard("BG_GVG_103",  "Floating Watcher",     4, 4, 4,  ["Demon"],
           text="Whenever your hero takes damage on your turn, gain +2/+2.",
           synergies=["Demon"], base_score=7.0, scaling=0.7),

    BGCard("BG_GIL_128",  "Security Rover",       4, 2, 6,  ["Mech"],
           text="Whenever this minion takes damage, add a 2/3 Mech with Taunt to your hand.",
           keywords=["taunt"],
           synergies=["Mech"], base_score=6.5, scaling=0.6),

    BGCard("BG_CFM_342",  "Menagerie Magician",   4, 4, 4,  [],
           text="Battlecry: Give a random friendly Beast, Dragon, and Murloc +2/+2.",
           synergies=["Beast","Dragon","Murloc"], base_score=6.5, scaling=0.6,
           notes="Best in Menagerie/mixed tribe comps."),

    BGCard("BG_GVG_035",  "Piloted Shredder",     4, 4, 3,  ["Mech"],
           ["deathrattle"],
           text="Deathrattle: Summon a random 2-cost minion.",
           synergies=["Mech","Deathrattle"], base_score=5.5, scaling=0.5),

    BGCard("BG_EX1_116",  "Leeroy Jenkins",       4, 6, 2,  [],
           ["charge"],
           text="Battlecry: Summon two 1/1 Whelps for your opponent.",
           base_score=5.5, scaling=0.3),

    BGCard("BG_GVG_113",  "Bolvar Fordragon",     4, 1, 7,  ["Dragon"],
           text="Whenever a friendly minion with Divine Shield loses it, gain +2 ATK.",
           synergies=["Dragon","Divine Shield"], base_score=7.5, scaling=0.8,
           notes="Combine with Mech DS board for lethal attacker."),

    BGCard("BG21_013",    "Amalgadon",            4, 6, 6,  [],
           text="Battlecry: For each different minion type among your other minions, gain a random keyword.",
           synergies=["Menagerie"], base_score=7.5, scaling=0.8,
           notes="Can get divine shield, poisonous, etc. in mixed comps."),

    BGCard("BG21_047",    "Bristleback Knight",   4, 3, 6,  ["Quilboar"],
           ["divine_shield"],
           text="Divine Shield. Whenever this minion loses its Divine Shield, take no damage this combat.",
           synergies=["Quilboar"], base_score=7.0, scaling=0.7),

    BGCard("BG25_017",    "Sire Denathrius",      4, 3, 7,  ["Undead"],
           text="After each friendly minion attack, it deals 1 damage to all enemies.",
           synergies=["Undead","Aggro"], base_score=7.5, scaling=0.8,
           notes="Incredible board-wide damage every attack."),

    BGCard("BG25_043",    "Captain Flat Tusk",    4, 5, 4,  ["Pirate"],
           text="Whenever a friendly Pirate attacks, it gets +2 ATK.",
           synergies=["Pirate"], base_score=6.5, scaling=0.7),

    BGCard("BG20_402",    "Murozond",             4, 5, 5,  ["Dragon"],
           text="Battlecry: Gain the abilities of all enemy minions.",
           synergies=["Dragon"], base_score=7.0, scaling=0.7,
           counters=["Divine Shield","Taunt"],
           notes="Adapts to whatever enemies run; strong flex pick."),

    BGCard("BG_GIL_119",  "Spiteful Smith",       4, 4, 6,  [],
           text="Whenever a friendly minion attacks, give it +2 ATK.",
           synergies=["Aggro"], base_score=6.0, scaling=0.6),

    BGCard("BG21_055",    "Herald of Flame",      4, 5, 6,  ["Dragon"],
           text="Whenever this attacks, deal 3 damage to the opposing hero and all enemy minions.",
           synergies=["Dragon"], base_score=7.5, scaling=0.7,
           notes="Massive AoE; kills token boards instantly."),
]

# ── Tier 5 ───────────────────────────────────────────────────────────────────
TIER5: List[BGCard] = [
    BGCard("BG_GVG_082",  "Junkbot",              5, 1, 5,  ["Mech"],
           text="Whenever a friendly Mech dies, gain +2/+2.",
           synergies=["Mech","Deathrattle"], base_score=8.5, scaling=0.9,
           notes="Hard win condition with deathrattle Mechs."),

    BGCard("BG_FP1_031",  "Baron Rivendare",      5, 1, 7,  [],
           text="Your Deathrattles trigger twice.",
           synergies=["Deathrattle"], base_score=9.0, scaling=0.95,
           notes="Best in slot for ANY Deathrattle comp."),

    BGCard("BG_ICC_831",  "Mal'Ganis",            5, 9, 7,  ["Demon"],
           text="Your other Demons have +2/+2. Your hero is Immune.",
           synergies=["Demon"], base_score=9.0, scaling=0.9,
           notes="Win condition for Demon boards; hero immunity is huge."),

    BGCard("BG_FP1_014",  "Razorgore the Untamed",5, 2, 4,  ["Dragon"],
           text="At end of turn, gain +2/+2 for each Dragon you have.",
           synergies=["Dragon"], base_score=8.5, scaling=0.95,
           notes="Fastest scaling card in the game with a Dragon board."),

    BGCard("BG_ICC_900",  "Sneaky Delinquent",    5, 4, 4,  ["Pirate"],
           text="Stealth. Deathrattle: Add a 4/4 Ghost to your hand with Stealth.",
           keywords=["stealth","deathrattle"],
           synergies=["Pirate"], base_score=6.5, scaling=0.6),

    BGCard("BG_CS2_232",  "Ragnaros the Firelord",5, 8, 8,  ["Elemental"],
           text="At end of turn, deal 8 damage to a random enemy.",
           synergies=["Elemental"], base_score=7.5, scaling=0.7),

    BGCard("BG_FP1_012",  "Sludge Belcher",       5, 3, 5,  [],
           ["taunt","deathrattle"],
           text="Taunt. Deathrattle: Summon a 1/2 Slime with Taunt.",
           synergies=["Deathrattle"], base_score=6.0, scaling=0.6),

    BGCard("BG21_030",    "Gentle Megasaur",      5, 5, 4,  ["Murloc"],
           text="Battlecry: Adapt all your Murlocs.",
           synergies=["Murloc"], base_score=8.0, scaling=0.85,
           notes="Can grant Divine Shield or Poisonous to whole board."),

    BGCard("BG21_058",    "Brann Bronzebeard",    5, 2, 4,  [],
           text="Your Battlecries trigger twice.",
           synergies=["Battlecry"], base_score=9.0, scaling=0.9,
           notes="Doubles all Battlecry value; absolutely critical buy."),

    BGCard("BG21_059",    "Hoggar",               5, 4, 4,  ["Quilboar"],
           text="After you play a Blood Gem, give all Quilboar +1/+1.",
           synergies=["Quilboar"], base_score=7.5, scaling=0.8),

    BGCard("BG25_050",    "Lich King",            5, 5, 5,  ["Undead"],
           text="At end of turn, animate a random friendly minion (give it +1/+1 and Reborn).",
           keywords=["reborn"],
           synergies=["Undead","Deathrattle"], base_score=8.0, scaling=0.9,
           notes="Spreads Reborn; excellent sustain and value engine."),

    BGCard("BG23_020",    "Naga's Pride",         5, 5, 5,  ["Naga"],
           text="After you play a spell, give a friendly Naga +2/+2.",
           synergies=["Naga"], base_score=7.0, scaling=0.7),

    BGCard("BG25_801",    "Onyxia",               5, 8, 8,  ["Dragon"],
           text="Battlecry: Fill your board with 1/1 Whelps.",
           synergies=["Dragon","Token"], base_score=7.5, scaling=0.7,
           notes="Creates instant wide board; great with Khadgar."),
]

# ── Tier 6 ───────────────────────────────────────────────────────────────────
TIER6: List[BGCard] = [
    BGCard("BG_FP1_010",  "Maexxna",              6, 2, 8,  ["Beast"],
           ["poisonous"],
           text="Poisonous.",
           synergies=["Beast"], base_score=9.0, scaling=0.95,
           counters=["Mech","Dragon","Demon"],
           notes="Kills anything regardless of stats. Often game-winning."),

    BGCard("BG_EX1_556",  "The Boogeymonster",    6, 6, 7,  [],
           text="Whenever this attacks and kills a minion, gain +2/+2.",
           base_score=7.0, scaling=0.7),

    BGCard("BG_ICC_099",  "Snowflipper Penguin",  6, 1, 1,  ["Beast"],
           base_score=3.0, scaling=0.1,
           notes="Filler."),

    BGCard("BG21_076",    "Imp Mama",             6, 6, 10, ["Demon"],
           text="Whenever this takes damage, summon a random Imp and give it Taunt.",
           keywords=["taunt"],
           synergies=["Demon"], base_score=8.5, scaling=0.9,
           notes="Almost unkillable; generates unlimited Imps."),

    BGCard("BG21_083",    "Bassgill",             6, 4, 10, ["Murloc"],
           text="After you buy a minion, if it's the highest Tier in the Tavern, draw and give it +5/+5.",
           synergies=["Murloc"], base_score=7.0, scaling=0.7),

    BGCard("BG21_HERO_030", "Zapp Slywick",       6, 7, 10, [],
           text="At the start of combat, attack the lowest ATK enemy.",
           synergies=["Aggro"], base_score=8.0, scaling=0.8,
           counters=["Murloc","Low-ATK tokens"]),

    BGCard("BG25_043",    "Rock Master Voone",    6, 3, 6,  ["Dragon"],
           text="After a Dragon attacks, give all friendly Dragons +1/+1.",
           synergies=["Dragon"], base_score=8.0, scaling=0.9,
           notes="Win condition for Dragon boards."),

    BGCard("BG25_900",    "Ghastcoiler",          6, 7, 7,  ["Undead"],
           ["deathrattle"],
           text="Deathrattle: Summon 2 random Deathrattle minions.",
           synergies=["Undead","Deathrattle"], base_score=8.5, scaling=0.9,
           notes="Chains deathrattles; incredible with Baron Rivendare."),

    BGCard("BG25_901",    "Soulbound Construct",  6, 6, 6,  ["Undead"],
           text="When this dies, revive with half its stats.",
           synergies=["Undead"], base_score=7.5, scaling=0.8),

    BGCard("BG21_091",    "Nomi, Kitchen Nightmare", 6, 4, 4, ["Elemental"],
           text="After you play an Elemental, give all Elementals in the Tavern +2/+2.",
           synergies=["Elemental"], base_score=9.0, scaling=0.95,
           notes="Permanent buff engine; Elementals become unstoppable."),

    BGCard("BG25_600",    "Sky Pirate",           6, 6, 6,  ["Pirate"],
           ["windfury"],
           text="Windfury. After this attacks, your hero attacks the enemy hero.",
           synergies=["Pirate"], base_score=8.0, scaling=0.8),
]

# ── Master index ─────────────────────────────────────────────────────────────
ALL_CARDS: List[BGCard] = TIER1 + TIER2 + TIER3 + TIER4 + TIER5 + TIER6

CARDS_BY_ID: dict[str, BGCard]     = {c.card_id: c for c in ALL_CARDS}
CARDS_BY_NAME: dict[str, BGCard]   = {c.name.lower(): c for c in ALL_CARDS}

def find_card(query: str) -> BGCard | None:
    """Look up by card ID or (case-insensitive) name."""
    return CARDS_BY_ID.get(query) or CARDS_BY_NAME.get(query.lower())
