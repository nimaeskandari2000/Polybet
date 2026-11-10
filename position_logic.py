"""
position_logic.py — PolyBet v2.0 Position Sizing & Smart Hedge Engine.

Clean, practical sizing logic:
1. Primary leg sized to guarantee target profit margin (default +5%) when Primary wins.
2. Filters out micro-tail outcomes (< 5 cents) so capital is never wasted on 0.15c noise.
3. Selects at most 2 realistic backup/hedge outcomes (price >= 5c) and allocates
   remaining capital proportionally to their probabilities.
4. If Primary is >= 88c (high-certainty favorite) or no realistic backup (>= 5c) exists,
   allocates 100% cleanly to Primary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sources.aggregator import MarketSignal


@dataclass
class PositionConfig:
    min_x_pct: float = 35.0
    max_x_pct: float = 70.0
    weight_consensus: float = 0.5
    weight_edge: float = 0.5
    edge_cap: float = 0.5
    secondary_cumulative_cap_pct: float = 90.0
    guaranteed_margin_pct: float = 0.05
    barrier_trap_max_pct: float = 5.0
    min_backup_price: float = 0.05
    max_backup_legs: int = 2
    high_prob_solo_threshold: float = 0.88


DEFAULT_CONFIG = PositionConfig()


@dataclass
class PositionAllocation:
    outcome: str
    size_pct: float
    role: str
    market_price: float | None = None
    net_roi_if_wins_pct: float | None = None


@dataclass
class PositionPlan:
    market_id: str
    question: str
    consensus_score: float
    edge: float
    num_sources: int
    allocations: list[PositionAllocation] = field(default_factory=list)
    warning: str | None = None
    guaranteed_margin_pct: float | None = None

    @property
    def primary(self) -> PositionAllocation | None:
        return next((a for a in self.allocations if a.role == "primary"), None)

    @property
    def total_allocated_pct(self) -> float:
        return sum(a.size_pct for a in self.allocations)


def _normalized_prices(outcomes: list[str], prices: list[float]) -> dict[str, float]:
    if not outcomes:
        outcomes = ["Yes", "No"]
    if len(prices) < len(outcomes):
        remaining = max(0.0, 1.0 - sum(prices))
        fill = remaining / max(1, (len(outcomes) - len(prices)))
        prices = list(prices) + [fill] * (len(outcomes) - len(prices))
    return dict(zip(outcomes, prices[: len(outcomes)]))


def compute_edge(model_probability: float, market_price: float) -> float:
    return abs(model_probability - market_price)


def compute_position_size(consensus_score: float, edge: float, config: PositionConfig = DEFAULT_CONFIG) -> float:
    consensus_component = max(0.0, min(1.0, consensus_score / 100.0))
    edge_component = max(0.0, min(1.0, edge / config.edge_cap)) if config.edge_cap > 0 else 0.0
    raw_score = config.weight_consensus * consensus_component + config.weight_edge * edge_component
    raw_score = max(0.0, min(1.0, raw_score))
    return config.min_x_pct + raw_score * (config.max_x_pct - config.min_x_pct)


def compute_guaranteed_floor_pct(primary_price: float, margin: float) -> tuple[float, float]:
    if primary_price <= 0:
        return 0.0, margin
    floor_fraction = primary_price * (1 + margin)
    if floor_fraction >= 1.0:
        achieved_margin = (1.0 / primary_price) - 1.0
        return 100.0, achieved_margin
    return floor_fraction * 100.0, margin


def is_barrier_option_trap(question: str, primary_outcome: str, primary_price: float) -> bool:
    """Detect non-exclusive 'What price will X hit?' barrier traps with <15c price."""
    hit_q = bool(re.search(r"\bwhat (?:price )?will .* hit\b", (question or "").lower()))
    arrow_o = bool(re.match(r"^[↑↓]\s*\$?[\d,.]+", (primary_outcome or "").strip()))
    return (hit_q or arrow_o) and primary_price < 0.15


def _attach_net_roi(allocations: list[PositionAllocation]) -> None:
    total_committed = sum(a.size_pct for a in allocations)
    for a in allocations:
        if a.market_price and a.market_price > 0:
            gross = a.size_pct / a.market_price
            a.net_roi_if_wins_pct = round(gross - total_committed, 2)


def build_position_plan(
    market_id: str, question: str, outcomes: list[str], outcome_prices: list[float],
    signal: MarketSignal, config: PositionConfig = DEFAULT_CONFIG,
) -> PositionPlan:
    price_by_outcome = _normalized_prices(outcomes, outcome_prices)
    ordered_outcomes = list(price_by_outcome.keys())
    warning = None

    if signal.num_sources == 0:
        primary_outcome = max(price_by_outcome, key=price_by_outcome.get)
        consensus_score = round(min(98.0, max(45.0, price_by_outcome.get(primary_outcome, 0.5) * 100.0)), 1)
        edge = 0.0
        x_pct = config.min_x_pct
    else:
        model_probability = signal.mean_probability
        if len(ordered_outcomes) == 2 and "Yes" in price_by_outcome and "No" in price_by_outcome:
            primary_outcome = "Yes" if model_probability >= 0.5 else "No"
            model_prob_for_side = model_probability if primary_outcome == "Yes" else 1 - model_probability
        else:
            primary_outcome = max(price_by_outcome, key=price_by_outcome.get)
            model_prob_for_side = model_probability
        market_price = price_by_outcome[primary_outcome]
        consensus_score = signal.consensus_score
        edge = compute_edge(model_prob_for_side, market_price)
        x_pct = compute_position_size(consensus_score, edge, config)

    primary_price = price_by_outcome.get(primary_outcome, 0.0)

    # Guard against non-exclusive Barrier Option Traps
    if is_barrier_option_trap(question, primary_outcome, primary_price):
        capped_size = round(min(config.barrier_trap_max_pct, max(1.0, primary_price * 200.0)), 2)
        allocations = [
            PositionAllocation(
                outcome=primary_outcome,
                size_pct=capped_size,
                role="primary",
                market_price=primary_price,
            )
        ]
        _attach_net_roi(allocations)
        return PositionPlan(
            market_id=market_id,
            question=question,
            consensus_score=consensus_score,
            edge=edge,
            num_sources=signal.num_sources,
            allocations=allocations,
            warning="بازار پرریسک (احتمال زیر ۱۵٪): حداکثر ۵٪ سرمایه وارد شود.",
            guaranteed_margin_pct=None,
        )

    floor_pct, achieved_margin = compute_guaranteed_floor_pct(primary_price, config.guaranteed_margin_pct)
    if floor_pct > x_pct:
        x_pct = floor_pct
    x_pct = min(x_pct, 100.0)

    # Filter remaining outcomes to realistic contenders only (price >= 5 cents)
    viable_backups = sorted(
        [
            o for o in ordered_outcomes
            if o != primary_outcome and price_by_outcome.get(o, 0.0) >= config.min_backup_price
        ],
        key=lambda o: price_by_outcome[o],
        reverse=True,
    )[: config.max_backup_legs]

    # If primary is >= 88c or there are no viable backups >= 5c, put 100% on Primary
    if primary_price >= config.high_prob_solo_threshold or not viable_backups or x_pct >= 98.0:
        allocations = [
            PositionAllocation(
                outcome=primary_outcome,
                size_pct=100.0,
                role="primary",
                market_price=primary_price,
            )
        ]
        _attach_net_roi(allocations)
        return PositionPlan(
            market_id=market_id,
            question=question,
            consensus_score=consensus_score,
            edge=edge,
            num_sources=signal.num_sources,
            allocations=allocations,
            warning=warning,
            guaranteed_margin_pct=round((1.0 / primary_price) - 1.0, 4) if primary_price > 0 else None,
        )

    allocations = [
        PositionAllocation(
            outcome=primary_outcome,
            size_pct=round(x_pct, 2),
            role="primary",
            market_price=primary_price,
        )
    ]

    remaining_pct = round(100.0 - round(x_pct, 2), 2)
    backup_weight_total = sum(price_by_outcome[o] for o in viable_backups) or 1.0

    allocated_backups = 0.0
    for idx, outcome in enumerate(viable_backups):
        if idx == len(viable_backups) - 1:
            leg_pct = round(remaining_pct - allocated_backups, 2)
        else:
            share = price_by_outcome[outcome] / backup_weight_total
            leg_pct = round(remaining_pct * share, 2)
            allocated_backups += leg_pct

        if leg_pct > 0:
            allocations.append(
                PositionAllocation(
                    outcome=outcome,
                    size_pct=leg_pct,
                    role="secondary" if idx == 0 else "hedge",
                    market_price=price_by_outcome[outcome],
                )
            )

    _attach_net_roi(allocations)
    return PositionPlan(
        market_id=market_id,
        question=question,
        consensus_score=consensus_score,
        edge=edge,
        num_sources=signal.num_sources,
        allocations=allocations,
        warning=warning,
        guaranteed_margin_pct=round(achieved_margin, 4) if primary_price > 0 else None,
    )
