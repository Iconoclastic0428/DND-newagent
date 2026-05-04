from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Ability


class D20TestType(str, Enum):
    ATTACK = 'attack'
    SAVING_THROW = 'saving-throw'
    ABILITY_CHECK = 'ability-check'
    DEATH_SAVE = 'death-save'


class D20RollMode(str, Enum):
    NORMAL = 'normal'
    ADVANTAGE = 'advantage'
    DISADVANTAGE = 'disadvantage'


@dataclass(frozen=True)
class D20TestRequest:
    request_id: str
    test_type: D20TestType
    actor_id: str
    ability: Ability | None = None
    ability_modifier: int = 0
    proficiency_bonus: int = 0
    proficient: bool = False
    flat_modifier: int = 0
    roll_mode: D20RollMode = D20RollMode.NORMAL
    dc: int | None = None
    auto_fail: bool = False


@dataclass(frozen=True)
class D20TestResult:
    request_id: str
    test_type: D20TestType
    actor_id: str
    rolls: tuple[int, ...]
    selected_roll: int
    total_modifier: int
    total: int
    roll_mode: D20RollMode
    success: bool | None
    auto_fail: bool
    critical_success: bool
    critical_failure: bool
