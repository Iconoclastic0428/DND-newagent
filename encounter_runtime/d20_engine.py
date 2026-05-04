from __future__ import annotations

from dataclasses import dataclass

from shared_types.d20 import D20RollMode, D20TestRequest, D20TestResult

from rules_engine.encounter_math import roll_d20
from rules_engine.rng import seeded_random


@dataclass(frozen=True)
class D20Resolution:
    result: D20TestResult
    random_counter_used: int


class D20TestEngine:
    def __init__(self, *, seed: str) -> None:
        self.seed = seed

    def resolve(self, request: D20TestRequest, *, random_counter: int) -> D20Resolution:
        rng = seeded_random(self.seed, random_counter)
        advantage = request.roll_mode == D20RollMode.ADVANTAGE
        disadvantage = request.roll_mode == D20RollMode.DISADVANTAGE
        rolls, selected_roll = roll_d20(rng, advantage=advantage, disadvantage=disadvantage)
        total_modifier = request.ability_modifier + (request.proficiency_bonus if request.proficient else 0) + request.flat_modifier
        critical_success = request.test_type.value == 'attack' and selected_roll == 20 and not request.auto_fail
        critical_failure = request.test_type.value == 'attack' and selected_roll == 1
        total = 0 if request.auto_fail else selected_roll + total_modifier
        success = None if request.dc is None else (False if request.auto_fail else total >= request.dc)
        result = D20TestResult(
            request_id=request.request_id,
            test_type=request.test_type,
            actor_id=request.actor_id,
            rolls=rolls,
            selected_roll=selected_roll,
            total_modifier=total_modifier,
            total=total,
            roll_mode=request.roll_mode,
            success=success,
            auto_fail=request.auto_fail,
            critical_success=critical_success,
            critical_failure=critical_failure,
        )
        return D20Resolution(result=result, random_counter_used=random_counter)


def merge_roll_mode(*, advantage: bool = False, disadvantage: bool = False) -> D20RollMode:
    if advantage and disadvantage:
        return D20RollMode.NORMAL
    if advantage:
        return D20RollMode.ADVANTAGE
    if disadvantage:
        return D20RollMode.DISADVANTAGE
    return D20RollMode.NORMAL
