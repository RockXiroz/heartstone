"""
Recommendation engine — scores every card currently in the tavern and
returns an ordered list of Recommendations with full reasoning.

Scoring formula (all additive):
  base_score          from the card database (0-10)
  + tribe_bonus       for synergy with the dominant board tribe
  + comp_bonus        for completing a known "package"
  + scaling_bonus     weighted by how many turns are left
  + counter_bonus     for countering common opponent tribes
  - cost_penalty      if gold is tight this turn
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from src.game_state import GameState, BoardMinion
from src.data.cards import BGCard, find_card
from src.data.synergies import (
    TRIBE_COMMIT_THRESHOLD, TRIBE_BONUS_PER_CARD,
    KEYWORD_SYNERGY, COUNTER_MAP, COMP_PACKAGES, STRATEGY_LOCK_TURN,
)


@dataclass
class Recommendation:
    card: BGCard
    board_index: int          # index in state.tavern_cards (for arrow placement)
    total_score: float
    base: float
    tribe_bonus: float
    comp_bonus: float
    scaling_bonus: float
    counter_bonus: float
    reasons: List[str] = field(default_factory=list)

    @property
    def win_rate_estimate(self) -> float:
        """Rough 0-100 % estimate derived from score."""
        return min(95.0, max(35.0, 35.0 + self.total_score * 5.0))

    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else "Strong stats for tier"


class Advisor:
    """Scores tavern cards and returns sorted Recommendations."""

    def __init__(self, state: GameState):
        self.state = state

    def recommend(self) -> List[Recommendation]:
        """Return all tavern cards scored, best first."""
        if not self.state.tavern_cards:
            return []

        recs = []
        for idx, minion in enumerate(self.state.tavern_cards):
            card = minion.card or find_card(minion.name)
            if card is None:
                continue
            rec = self._score(card, idx)
            recs.append(rec)

        recs.sort(key=lambda r: r.total_score, reverse=True)
        return recs

    def best(self) -> Optional[Recommendation]:
        recs = self.recommend()
        return recs[0] if recs else None

    # ── Scoring ──────────────────────────────────────────────────────────
    def _score(self, card: BGCard, idx: int) -> Recommendation:
        s        = self.state
        reasons: List[str] = []

        base          = card.base_score
        tribe_bonus   = self._tribe_bonus(card, reasons)
        comp_bonus    = self._comp_bonus(card, reasons)
        scaling_bonus = self._scaling_bonus(card, reasons)
        counter_bonus = self._counter_bonus(card, reasons)

        # Add keyword synergies already on board
        kw_bonus = 0.0
        for kw in card.keywords:
            if kw in KEYWORD_SYNERGY:
                kw_bonus += KEYWORD_SYNERGY[kw] * 0.5
        if kw_bonus > 0:
            reasons.append(f"Has valuable keyword: {', '.join(card.keywords)}")

        total = base + tribe_bonus + comp_bonus + scaling_bonus + counter_bonus + kw_bonus

        if not reasons:
            reasons.append(f"Solid tier-{card.tier} body ({card.attack}/{card.health})")

        return Recommendation(
            card          = card,
            board_index   = idx,
            total_score   = round(total, 2),
            base          = round(base, 2),
            tribe_bonus   = round(tribe_bonus, 2),
            comp_bonus    = round(comp_bonus, 2),
            scaling_bonus = round(scaling_bonus, 2),
            counter_bonus = round(counter_bonus, 2),
            reasons       = reasons,
        )

    def _tribe_bonus(self, card: BGCard, reasons: List[str]) -> float:
        player_tribes = self.state.player_tribes
        dominant      = self.state.dominant_tribe()
        bonus         = 0.0

        for tribe in card.tribes:
            if tribe == "All":
                # Amalgam — count as matching everything
                if player_tribes:
                    bonus += 2.0
                    reasons.append("Amalgam activates ALL your tribe synergies")
                break
            count = player_tribes.get(tribe, 0)
            if count >= TRIBE_COMMIT_THRESHOLD:
                bonus += TRIBE_BONUS_PER_CARD * count
                reasons.append(
                    f"Deepens your {tribe} comp ({count} already on board) → strong synergy"
                )
            elif count >= 2:
                bonus += TRIBE_BONUS_PER_CARD * 0.5
                reasons.append(f"Contributes to your {tribe} build (2+ on board)")
            elif dominant and tribe == dominant:
                bonus += 0.8
                reasons.append(f"Matches your dominant {tribe} strategy")

        # If card has no matching tribe but is neutral, small penalty in late game
        if not any(t in player_tribes for t in card.tribes) and card.tribes:
            if self.state.turn > STRATEGY_LOCK_TURN:
                bonus -= 1.5
                reasons.append(
                    "Off-tribe pick after strategy is locked — hard to integrate"
                )

        return bonus

    def _comp_bonus(self, card: BGCard, reasons: List[str]) -> float:
        board_names = {m.name for m in self.state.player_board}
        best_bonus  = 0.0
        best_comp   = ""

        for comp_name, required in COMP_PACKAGES.items():
            have   = sum(1 for r in required if r in board_names)
            total  = len(required)
            if have == 0:
                continue
            # Check if this card is part of the package
            if card.name in required:
                completion = (have + 1) / total
                bonus = completion * 3.0
                if bonus > best_bonus:
                    best_bonus = bonus
                    best_comp  = comp_name

        if best_comp:
            reasons.append(
                f"Completes your '{best_comp}' package — "
                f"this card is a key piece of that win condition"
            )
        return best_bonus

    def _scaling_bonus(self, card: BGCard, reasons: List[str]) -> float:
        # Early game (turn ≤ 4): value scaling
        # Late game (turn ≥ 8): value immediate impact
        turn = self.state.turn
        if turn <= 4:
            bonus = card.scaling * 2.5
            if card.scaling >= 0.8:
                reasons.append(
                    f"Exceptional late-game scaling — "
                    "grows exponentially; buy early to maximise compounding"
                )
        else:
            # Reward immediate stat-sticks in late game
            stat_value = (card.attack + card.health) / 4.0
            bonus = stat_value * (1 - card.scaling) * 1.5
        return bonus

    def _counter_bonus(self, card: BGCard, reasons: List[str]) -> float:
        opponent_tribes = self.state.opponent_tribes
        if not opponent_tribes:
            return 0.0

        bonus = 0.0
        for opp_tribe, opp_count in opponent_tribes.items():
            if opp_tribe in COUNTER_MAP:
                counter_tribes = COUNTER_MAP[opp_tribe]
                for ct in counter_tribes:
                    if ct in card.tribes or ct in card.counters:
                        weight = min(opp_count / 4, 1.0)
                        bonus += 1.5 * weight
                        reasons.append(
                            f"Counters dominant opponent tribe ({opp_tribe}) — "
                            f"{opp_count} seen across enemy boards"
                        )
                        break

        for opp_tribe in card.counters:
            if opp_tribe in opponent_tribes:
                bonus += 1.0
                reasons.append(f"Hard counter to opponent {opp_tribe} strategy")

        return bonus
