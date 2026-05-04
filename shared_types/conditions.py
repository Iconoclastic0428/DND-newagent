from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConditionType(str, Enum):
    BLINDED = 'blinded'
    CHARMED = 'charmed'
    DEAFENED = 'deafened'
    EXHAUSTION = 'exhaustion'
    FRIGHTENED = 'frightened'
    GRAPPLED = 'grappled'
    INCAPACITATED = 'incapacitated'
    INVISIBLE = 'invisible'
    PARALYZED = 'paralyzed'
    PETRIFIED = 'petrified'
    POISONED = 'poisoned'
    PRONE = 'prone'
    RESTRAINED = 'restrained'
    STUNNED = 'stunned'
    UNCONSCIOUS = 'unconscious'


class ConditionStackingPolicy(str, Enum):
    NON_STACKING = 'non-stacking'
    CUMULATIVE = 'cumulative'


class ConditionDurationType(str, Enum):
    UNTIL_REMOVED = 'until-removed'
    START_OF_TURN = 'start-of-turn'
    END_OF_TURN = 'end-of-turn'
    ROUND_COUNT = 'round-count'


@dataclass(frozen=True)
class ConditionDuration:
    duration_type: ConditionDurationType = ConditionDurationType.UNTIL_REMOVED
    rounds: int | None = None
    actor_id: str | None = None


@dataclass(frozen=True)
class ConditionDefinition:
    condition_type: ConditionType
    stacking_policy: ConditionStackingPolicy
    includes: tuple[ConditionType, ...] = ()


@dataclass(frozen=True)
class ConditionInstance:
    instance_id: str
    condition_type: ConditionType
    source_actor_id: str | None = None
    source_effect_id: str | None = None
    source_label: str | None = None
    duration: ConditionDuration | None = None
    charmer_actor_id: str | None = None
    fear_source_actor_id: str | None = None
    grappler_actor_id: str | None = None
    suppressed: bool = False


CONDITION_DEFINITIONS: dict[ConditionType, ConditionDefinition] = {
    ConditionType.BLINDED: ConditionDefinition(condition_type=ConditionType.BLINDED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.CHARMED: ConditionDefinition(condition_type=ConditionType.CHARMED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.DEAFENED: ConditionDefinition(condition_type=ConditionType.DEAFENED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.EXHAUSTION: ConditionDefinition(condition_type=ConditionType.EXHAUSTION, stacking_policy=ConditionStackingPolicy.CUMULATIVE),
    ConditionType.FRIGHTENED: ConditionDefinition(condition_type=ConditionType.FRIGHTENED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.GRAPPLED: ConditionDefinition(condition_type=ConditionType.GRAPPLED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.INCAPACITATED: ConditionDefinition(condition_type=ConditionType.INCAPACITATED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.INVISIBLE: ConditionDefinition(condition_type=ConditionType.INVISIBLE, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.PARALYZED: ConditionDefinition(condition_type=ConditionType.PARALYZED, stacking_policy=ConditionStackingPolicy.NON_STACKING, includes=(ConditionType.INCAPACITATED,)),
    ConditionType.PETRIFIED: ConditionDefinition(condition_type=ConditionType.PETRIFIED, stacking_policy=ConditionStackingPolicy.NON_STACKING, includes=(ConditionType.INCAPACITATED,)),
    ConditionType.POISONED: ConditionDefinition(condition_type=ConditionType.POISONED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.PRONE: ConditionDefinition(condition_type=ConditionType.PRONE, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.RESTRAINED: ConditionDefinition(condition_type=ConditionType.RESTRAINED, stacking_policy=ConditionStackingPolicy.NON_STACKING),
    ConditionType.STUNNED: ConditionDefinition(condition_type=ConditionType.STUNNED, stacking_policy=ConditionStackingPolicy.NON_STACKING, includes=(ConditionType.INCAPACITATED,)),
    ConditionType.UNCONSCIOUS: ConditionDefinition(condition_type=ConditionType.UNCONSCIOUS, stacking_policy=ConditionStackingPolicy.NON_STACKING, includes=(ConditionType.INCAPACITATED, ConditionType.PRONE)),
}


def expand_condition_types(condition_types: set[ConditionType] | frozenset[ConditionType]) -> frozenset[ConditionType]:
    expanded = set(condition_types)
    pending = list(condition_types)
    while pending:
        current = pending.pop()
        definition = CONDITION_DEFINITIONS[current]
        for included in definition.includes:
            if included not in expanded:
                expanded.add(included)
                pending.append(included)
    return frozenset(expanded)


def parse_condition_type(raw_value: str) -> ConditionType | None:
    normalized = raw_value.strip().lower()
    for condition_type in ConditionType:
        if condition_type.value == normalized:
            return condition_type
    return None
