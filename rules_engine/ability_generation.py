from __future__ import annotations

from collections import Counter
import random

from shared_types.errors import ValidationError
from shared_types.models import AbilityMethod


POINT_BUY_COSTS: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}


def roll_dice(rng: random.Random, *, die_count: int, die_faces: int) -> tuple[int, tuple[int, ...]]:
    rolls = tuple(rng.randint(1, die_faces) for _ in range(die_count))
    return sum(rolls), rolls


def roll_4d6_keep_highest_3(rng: random.Random) -> tuple[int, tuple[int, int, int, int]]:
    total, dice = roll_dice(rng, die_count=4, die_faces=6)
    kept = sorted(dice, reverse=True)[:3]
    return sum(kept), dice


def roll_six_ability_scores(rng: random.Random) -> tuple[tuple[int, ...], tuple[tuple[int, int, int, int], ...]]:
    scores: list[int] = []
    breakdown: list[tuple[int, int, int, int]] = []
    for _ in range(6):
        score, dice = roll_4d6_keep_highest_3(rng)
        scores.append(score)
        breakdown.append(dice)
    return tuple(scores), tuple(breakdown)


def validate_point_buy_scores(scores: tuple[int, ...]) -> int:
    if len(scores) != 6:
        raise ValidationError("Point buy requires exactly six scores.")
    total_cost = 0
    for score in scores:
        if score not in POINT_BUY_COSTS:
            raise ValidationError("Point buy scores must be between 8 and 15.")
        total_cost += POINT_BUY_COSTS[score]
    if total_cost > 27:
        raise ValidationError(f"Point buy spent {total_cost} points; the maximum is 27.")
    return total_cost


def arrays_match_multiset(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return Counter(left) == Counter(right)


def higher_total_methods(
    rolled_scores: tuple[int, ...],
    point_buy_scores: tuple[int, ...],
) -> set[AbilityMethod]:
    rolled_total = sum(rolled_scores)
    point_buy_total = sum(point_buy_scores)
    if rolled_total > point_buy_total:
        return {AbilityMethod.ROLLED}
    if point_buy_total > rolled_total:
        return {AbilityMethod.POINT_BUY}
    return {AbilityMethod.ROLLED, AbilityMethod.POINT_BUY}
