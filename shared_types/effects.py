from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .conditions import ConditionType
from .d20 import D20RollMode
from .d20 import D20TestResult
from .encounter_models import GridPosition
from .models import Ability


class EffectResolutionBranch(str, Enum):
    SUCCESS = 'success'
    FAILURE = 'failure'
    PARTIAL_SUCCESS = 'partial-success'


class ForcedMovementMode(str, Enum):
    PUSH = 'push'
    PULL = 'pull'
    REPOSITION = 'reposition'


class ForcedMovementStopReason(str, Enum):
    COMPLETED = 'completed'
    BLOCKED_TERRAIN = 'blocked-terrain'
    BLOCKED_OCCUPANCY = 'blocked-occupancy'
    OUTSIDE_BATTLEFIELD = 'outside-battlefield'
    NO_PROGRESS = 'no-progress'
    ENTERED_UNSUPPORTED_SPACE = 'entered-unsupported-space'
    ENTERED_LIQUID = 'entered-liquid'


@dataclass(frozen=True)
class ResolutionContext:
    effect_id: str
    source_actor_id: str | None
    target_actor_id: str
    reason: str


@dataclass(frozen=True)
class SaveRequest:
    context: ResolutionContext
    ability: Ability
    dc: int
    flat_modifier: int = 0
    partial_success_margin: int | None = None
    roll_mode: D20RollMode = D20RollMode.NORMAL


@dataclass(frozen=True)
class CheckRequest:
    context: ResolutionContext
    ability: Ability
    dc: int
    skill_name: str | None = None
    flat_modifier: int = 0
    partial_success_margin: int | None = None
    roll_mode: D20RollMode = D20RollMode.NORMAL
    requires_sight: bool = False
    requires_hearing: bool = False
    interacting_with_actor_id: str | None = None


@dataclass(frozen=True)
class SaveResolution:
    request: SaveRequest
    result: D20TestResult
    branch: EffectResolutionBranch


@dataclass(frozen=True)
class CheckResolution:
    request: CheckRequest
    result: D20TestResult
    branch: EffectResolutionBranch


@dataclass(frozen=True)
class DisplacementVector:
    dx: int
    dy: int
    dz: int = 0


@dataclass(frozen=True)
class ForcedMovementEffect:
    context: ResolutionContext
    mode: ForcedMovementMode
    distance_ft: int
    vector: DisplacementVector | None = None
    destination: GridPosition | None = None


@dataclass(frozen=True)
class ForcedMovementResult:
    effect: ForcedMovementEffect
    path: tuple[GridPosition, ...]
    final_position: GridPosition
    moved_distance_ft: int
    stop_reason: ForcedMovementStopReason
    entered_liquid: bool
    caused_fall: bool


@dataclass(frozen=True)
class DamageEffect:
    dice_count: int
    die_faces: int
    bonus: int
    damage_type: str


@dataclass(frozen=True)
class ConditionApplication:
    condition_type: ConditionType
    source_label: str | None = None
    source_effect_id: str | None = None
    source_actor_id: str | None = None
    charmer_actor_id: str | None = None
    fear_source_actor_id: str | None = None


@dataclass(frozen=True)
class EffectOutcome:
    damage: DamageEffect | None = None
    conditions: tuple[ConditionApplication, ...] = ()
    forced_movement: ForcedMovementEffect | None = None
    damage_divisor: int = 1


@dataclass(frozen=True)
class HazardResolutionRequest:
    context: ResolutionContext
    save_request: SaveRequest | None = None
    check_request: CheckRequest | None = None
    success_outcome: EffectOutcome | None = None
    failure_outcome: EffectOutcome | None = None
    partial_success_outcome: EffectOutcome | None = None


@dataclass(frozen=True)
class HazardResolutionResult:
    request: HazardResolutionRequest
    branch: EffectResolutionBranch | None
    save_resolution: SaveResolution | None = None
    check_resolution: CheckResolution | None = None
    forced_movement_result: ForcedMovementResult | None = None


@dataclass(frozen=True)
class LiquidEntryMitigationChoice:
    attempt: bool
    ability: Ability
    skill_name: str
    dc: int = 15


@dataclass(frozen=True)
class LiquidEntryMitigationResolution:
    used_reaction: bool
    success: bool
    damage_before: int
    damage_after: int
    check_resolution: CheckResolution | None = None

