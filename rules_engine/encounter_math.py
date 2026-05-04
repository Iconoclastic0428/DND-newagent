from __future__ import annotations

import math
import random

from shared_types.encounter_models import GridPosition


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def grid_distance_ft(origin: GridPosition, destination: GridPosition) -> int:
    horizontal_dx = abs(destination.x - origin.x)
    horizontal_dy = abs(destination.y - origin.y)
    vertical_steps = math.ceil(abs(destination.z - origin.z) / 5)
    return max(horizontal_dx, horizontal_dy, vertical_steps) * 5


def horizontal_distance_ft(origin: GridPosition, destination: GridPosition) -> int:
    return max(abs(destination.x - origin.x), abs(destination.y - origin.y)) * 5


def vertical_distance_ft(origin: GridPosition, destination: GridPosition) -> int:
    return abs(destination.z - origin.z)


def roll_d20(
    rng: random.Random,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
) -> tuple[tuple[int, ...], int]:
    if advantage and disadvantage:
        roll = rng.randint(1, 20)
        return (roll,), roll
    if advantage:
        rolls = (rng.randint(1, 20), rng.randint(1, 20))
        return rolls, max(rolls)
    if disadvantage:
        rolls = (rng.randint(1, 20), rng.randint(1, 20))
        return rolls, min(rolls)
    roll = rng.randint(1, 20)
    return (roll,), roll


def roll_damage(rng: random.Random, *, dice_count: int, die_faces: int, bonus: int) -> tuple[tuple[int, ...], int]:
    if dice_count <= 0 or die_faces <= 0:
        return (), max(0, bonus)
    rolls = tuple(rng.randint(1, die_faces) for _ in range(dice_count))
    return rolls, max(0, sum(rolls) + bonus)
