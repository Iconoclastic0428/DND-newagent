from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from shared_types.conditions import (
    CONDITION_DEFINITIONS,
    ConditionInstance,
    ConditionType,
    expand_condition_types,
)
from shared_types.encounter_models import EncounterState, RuntimeActorState
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from shared_types.visibility import ObserverVisibilityState

from rules_engine.encounter_math import grid_distance_ft

from .visibility import assess_visibility


_SOCIAL_SKILLS = frozenset({'Deception', 'Intimidation', 'Performance', 'Persuasion'})


@dataclass(frozen=True)
class ConditionStateView:
    active_instances: tuple[ConditionInstance, ...]
    active_types: frozenset[ConditionType]
    effective_types: frozenset[ConditionType]
    exhaustion_level: int
    charmer_actor_ids: frozenset[str]
    fear_source_actor_ids: frozenset[str]
    grappler_actor_ids: frozenset[str]
    speed_is_zero: bool
    speed_cannot_increase: bool
    weight_multiplier: int
    aging_suspended: bool
    unaware_of_surroundings: bool
    concealed_with_equipment: bool


@dataclass(frozen=True)
class D20ModifierState:
    modifier: int = 0
    advantage: bool = False
    disadvantage: bool = False
    auto_fail: bool = False
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttackRollModifierState(D20ModifierState):
    critical_on_hit: bool = False


@dataclass(frozen=True)
class TargetingVisibilityLegality:
    legal: bool
    reason: str | None = None


@dataclass(frozen=True)
class ConditionMutationResult:
    condition_instances: tuple[ConditionInstance, ...]
    concentration_broken: bool = False
    defeated_by_exhaustion: bool = False


@dataclass(frozen=True)
class DamageResolution:
    final_damage: int
    resisted: bool = False
    immune: bool = False


@dataclass(frozen=True)
class ConditionRemovalResult:
    condition_instances: tuple[ConditionInstance, ...]
    added_instances: tuple[ConditionInstance, ...] = ()


def get_condition_state(actor: RuntimeActorState) -> ConditionStateView:
    active_instances = tuple(instance for instance in actor.condition_instances if not instance.suppressed)
    active_types = frozenset(instance.condition_type for instance in active_instances)
    effective_types = expand_condition_types(active_types)
    exhaustion_level = sum(1 for instance in active_instances if instance.condition_type == ConditionType.EXHAUSTION)
    charmer_actor_ids = frozenset(instance.charmer_actor_id for instance in active_instances if instance.charmer_actor_id)
    fear_source_actor_ids = frozenset(instance.fear_source_actor_id for instance in active_instances if instance.fear_source_actor_id)
    grappler_actor_ids = frozenset(instance.grappler_actor_id for instance in active_instances if instance.grappler_actor_id)
    speed_is_zero = bool(
        {
            ConditionType.GRAPPLED,
            ConditionType.PARALYZED,
            ConditionType.PETRIFIED,
            ConditionType.RESTRAINED,
            ConditionType.UNCONSCIOUS,
        }
        & effective_types
    )
    speed_cannot_increase = speed_is_zero
    if exhaustion_level > 0 and max(0, actor.speed_ft - (5 * exhaustion_level)) <= 0:
        speed_is_zero = True
    return ConditionStateView(
        active_instances=active_instances,
        active_types=active_types,
        effective_types=effective_types,
        exhaustion_level=exhaustion_level,
        charmer_actor_ids=charmer_actor_ids,
        fear_source_actor_ids=fear_source_actor_ids,
        grappler_actor_ids=grappler_actor_ids,
        speed_is_zero=speed_is_zero,
        speed_cannot_increase=speed_cannot_increase,
        weight_multiplier=10 if ConditionType.PETRIFIED in effective_types else 1,
        aging_suspended=ConditionType.PETRIFIED in effective_types,
        unaware_of_surroundings=ConditionType.UNCONSCIOUS in effective_types,
        concealed_with_equipment=ConditionType.INVISIBLE in effective_types,
    )


def has_condition(actor: RuntimeActorState, condition_type: ConditionType) -> bool:
    return condition_type in get_condition_state(actor).effective_types


def get_effective_speed(actor: RuntimeActorState) -> int:
    state = get_condition_state(actor)
    if state.speed_is_zero:
        return 0
    base_speed = actor.speed_ft + actor.speed_bonus_ft
    if actor.speed_override_ft is not None:
        base_speed = min(base_speed, actor.speed_override_ft)
    return max(0, base_speed - (5 * state.exhaustion_level))


def can_take_actions(actor: RuntimeActorState) -> bool:
    return ConditionType.INCAPACITATED not in get_condition_state(actor).effective_types


def can_take_bonus_actions(actor: RuntimeActorState) -> bool:
    return can_take_actions(actor)


def can_take_reactions(actor: RuntimeActorState) -> bool:
    return not actor.cannot_take_reactions and ConditionType.INCAPACITATED not in get_condition_state(actor).effective_types


def can_speak(actor: RuntimeActorState) -> bool:
    return ConditionType.INCAPACITATED not in get_condition_state(actor).effective_types


def can_observer_see_target(
    observer: RuntimeActorState,
    target: RuntimeActorState,
    *,
    encounter_state: EncounterState | None = None,
) -> bool:
    if encounter_state is not None:
        return assess_visibility(encounter_state, observer, target).can_see_target
    observer_state = get_condition_state(observer)
    target_state = get_condition_state(target)
    if ConditionType.BLINDED in observer_state.effective_types:
        return False
    if ConditionType.INVISIBLE in target_state.effective_types and not observer.can_see_invisible:
        return False
    return True


def get_targeting_visibility_legality(
    actor: RuntimeActorState,
    target: RuntimeActorState,
    *,
    requires_target_to_be_seen: bool,
    encounter_state: EncounterState | None = None,
) -> TargetingVisibilityLegality:
    if not requires_target_to_be_seen:
        return TargetingVisibilityLegality(legal=True)
    if encounter_state is not None:
        assessment = assess_visibility(encounter_state, actor, target)
        if assessment.visibility_state == ObserverVisibilityState.VISIBLE:
            return TargetingVisibilityLegality(legal=True)
        return TargetingVisibilityLegality(legal=False, reason=assessment.detail)
    if can_observer_see_target(actor, target):
        return TargetingVisibilityLegality(legal=True)
    return TargetingVisibilityLegality(legal=False, reason='The target cannot currently be seen by the acting actor.')


def validate_hostile_targeting(
    actor: RuntimeActorState,
    target: RuntimeActorState,
    *,
    is_damaging: bool,
    is_magical: bool,
) -> None:
    target_actor_ids = get_condition_state(actor).charmer_actor_ids
    if target.actor_id in target_actor_ids and (not is_magical or is_damaging):
        if is_magical:
            raise EncounterValidationError('A charmed actor cannot target the charmer with damaging magical effects.')
        raise EncounterValidationError('A charmed actor cannot attack the charmer.')


def get_initiative_modifiers(actor: RuntimeActorState) -> D20ModifierState:
    state = get_condition_state(actor)
    reasons: list[str] = []
    advantage = ConditionType.INVISIBLE in state.effective_types
    disadvantage = ConditionType.INCAPACITATED in state.effective_types or actor.surprised
    if advantage:
        reasons.append('invisible')
    if ConditionType.INCAPACITATED in state.effective_types:
        reasons.append('incapacitated')
    if actor.surprised:
        reasons.append('surprised')
    modifier = -(2 * state.exhaustion_level)
    if modifier:
        reasons.append('exhaustion')
    return D20ModifierState(modifier=modifier, advantage=advantage, disadvantage=disadvantage, reasons=tuple(reasons))


def _attacker_has_nonvisual_precision(attacker: RuntimeActorState, target: RuntimeActorState, *, distance_ft: int) -> bool:
    if attacker.blindsight_radius_ft > 0 and distance_ft <= attacker.blindsight_radius_ft:
        return True
    if attacker.truesight_radius_ft > 0 and distance_ft <= attacker.truesight_radius_ft:
        return True
    return False


def get_attack_roll_modifiers(
    attacker: RuntimeActorState,
    target: RuntimeActorState,
    *,
    distance_ft: int,
    encounter_state: EncounterState | None = None,
) -> AttackRollModifierState:
    attacker_state = get_condition_state(attacker)
    target_state = get_condition_state(target)
    advantage_reasons: list[str] = []
    disadvantage_reasons: list[str] = []

    if ConditionType.BLINDED in attacker_state.effective_types:
        disadvantage_reasons.append('blinded-attacker')
    if ConditionType.BLINDED in target_state.effective_types:
        advantage_reasons.append('blinded-target')
    if target.dodge_active:
        disadvantage_reasons.append('dodge')
    if ConditionType.POISONED in attacker_state.effective_types:
        disadvantage_reasons.append('poisoned')
    if ConditionType.PRONE in attacker_state.effective_types:
        disadvantage_reasons.append('prone-attacker')
    if ConditionType.RESTRAINED in attacker_state.effective_types:
        disadvantage_reasons.append('restrained-attacker')
    if ConditionType.RESTRAINED in target_state.effective_types:
        advantage_reasons.append('restrained-target')
    if ConditionType.PARALYZED in target_state.effective_types:
        advantage_reasons.append('paralyzed-target')
    if ConditionType.PETRIFIED in target_state.effective_types:
        advantage_reasons.append('petrified-target')
    if ConditionType.STUNNED in target_state.effective_types:
        advantage_reasons.append('stunned-target')
    if ConditionType.UNCONSCIOUS in target_state.effective_types:
        advantage_reasons.append('unconscious-target')
    if encounter_state is not None:
        target_visibility = assess_visibility(encounter_state, attacker, target)
        attacker_visibility = assess_visibility(encounter_state, target, attacker)
        if any(
            target.actor_id in effect.target_actor_ids
            and effect.definition.attackers_rely_on_sight_have_disadvantage
            and not _attacker_has_nonvisual_precision(attacker, target, distance_ft=distance_ft)
            for effect in encounter_state.active_effects.values()
        ):
            disadvantage_reasons.append('blurred-target')
        if target_visibility.visibility_state != ObserverVisibilityState.VISIBLE:
            disadvantage_reasons.append('unseen-target')
        if attacker_visibility.visibility_state != ObserverVisibilityState.VISIBLE:
            advantage_reasons.append('unseen-attacker')
    else:
        if ConditionType.INVISIBLE in target_state.effective_types and not can_observer_see_target(attacker, target):
            disadvantage_reasons.append('invisible-target')
        if ConditionType.INVISIBLE in attacker_state.effective_types and not can_observer_see_target(target, attacker):
            advantage_reasons.append('invisible-attacker')
    if ConditionType.PRONE in target_state.effective_types:
        if distance_ft <= 5:
            advantage_reasons.append('prone-target-adjacent')
        else:
            disadvantage_reasons.append('prone-target-ranged')
    if ConditionType.GRAPPLED in attacker_state.effective_types and attacker_state.grappler_actor_ids and target.actor_id not in attacker_state.grappler_actor_ids:
        disadvantage_reasons.append('grappled-other-target')
    if encounter_state is not None and _fear_source_visible_to_actor(attacker, encounter_state):
        if ConditionType.FRIGHTENED in attacker_state.effective_types:
            disadvantage_reasons.append('frightened')
    modifier = -(2 * attacker_state.exhaustion_level)
    if modifier:
        disadvantage_reasons.append('exhaustion')
    return AttackRollModifierState(
        modifier=modifier,
        advantage=bool(advantage_reasons),
        disadvantage=bool(disadvantage_reasons),
        reasons=tuple(advantage_reasons + disadvantage_reasons),
        critical_on_hit=(distance_ft <= 5 and ({ConditionType.PARALYZED, ConditionType.UNCONSCIOUS} & target_state.effective_types) != set()),
    )


def get_saving_throw_modifiers_or_auto_fail(actor: RuntimeActorState, ability: Ability) -> D20ModifierState:
    state = get_condition_state(actor)
    auto_fail = ability in {Ability.STR, Ability.DEX} and bool({ConditionType.PARALYZED, ConditionType.PETRIFIED, ConditionType.STUNNED, ConditionType.UNCONSCIOUS} & state.effective_types)
    reasons: list[str] = []
    if auto_fail:
        reasons.append('condition-auto-fail')
    modifier = -(2 * state.exhaustion_level)
    if modifier:
        reasons.append('exhaustion')
    advantage = ability in actor.saving_throw_advantage_abilities
    disadvantage = False
    if advantage:
        reasons.append('feature-advantage')
    if ability == Ability.DEX and ConditionType.RESTRAINED in state.effective_types:
        reasons.append('restrained-disadvantage')
        disadvantage = True
    return D20ModifierState(modifier=modifier, advantage=advantage, disadvantage=disadvantage, auto_fail=auto_fail, reasons=tuple(reasons))


def get_ability_check_modifiers_or_auto_fail(
    actor: RuntimeActorState,
    ability: Ability,
    *,
    encounter_state: EncounterState | None = None,
    requires_sight: bool = False,
    requires_hearing: bool = False,
    interacting_with_actor_id: str | None = None,
    skill_name: str | None = None,
) -> D20ModifierState:
    state = get_condition_state(actor)
    reasons: list[str] = []
    auto_fail = False
    if requires_sight and ConditionType.BLINDED in state.effective_types:
        auto_fail = True
        reasons.append('blinded-sight-check')
    if requires_hearing and ConditionType.DEAFENED in state.effective_types:
        auto_fail = True
        reasons.append('deafened-hearing-check')
    advantage = ability in actor.ability_check_advantage_abilities
    disadvantage = ability in actor.ability_check_disadvantage_abilities
    if advantage:
        reasons.append('feature-advantage')
    if disadvantage:
        reasons.append('feature-disadvantage')
    if ConditionType.POISONED in state.effective_types:
        disadvantage = True
        reasons.append('poisoned')
    if encounter_state is not None and ConditionType.FRIGHTENED in state.effective_types and _fear_source_visible_to_actor(actor, encounter_state):
        disadvantage = True
        reasons.append('frightened')
    if interacting_with_actor_id is not None and ability == Ability.CHA and skill_name in _SOCIAL_SKILLS:
        interacting_actor = encounter_state.actors.get(interacting_with_actor_id) if encounter_state is not None else None
        if interacting_actor is not None and actor.actor_id in get_condition_state(interacting_actor).charmer_actor_ids:
            advantage = True
            reasons.append('charmed-social')
    if encounter_state is not None and interacting_with_actor_id is not None and skill_name is not None:
        for effect in encounter_state.active_effects.values():
            if actor.actor_id not in effect.target_actor_ids or not effect.definition.marked_target_skill_advantage_names:
                continue
            metadata = dict(effect.metadata)
            if metadata.get('marked-target-id') != interacting_with_actor_id:
                continue
            if skill_name in effect.definition.marked_target_skill_advantage_names:
                advantage = True
                reasons.append('marked-target-skill')
    modifier = -(2 * state.exhaustion_level)
    if modifier:
        reasons.append('exhaustion')
    return D20ModifierState(modifier=modifier, advantage=advantage, disadvantage=disadvantage, auto_fail=auto_fail, reasons=tuple(reasons))


def add_condition(actor: RuntimeActorState, condition_instance: ConditionInstance) -> ConditionMutationResult:
    if is_immune_to_condition(actor, condition_instance.condition_type):
        raise EncounterValidationError(f'{actor.actor_id} is immune to the {condition_instance.condition_type.value} condition.')
    existing = list(actor.condition_instances)
    if condition_instance.condition_type == ConditionType.EXHAUSTION:
        existing.append(condition_instance)
    else:
        replaced = False
        for index, current in enumerate(existing):
            if current.condition_type != condition_instance.condition_type:
                continue
            if _same_condition_source(current, condition_instance):
                existing[index] = condition_instance
                replaced = True
                break
        if not replaced:
            existing.append(condition_instance)
    updated_instances = tuple(existing)
    effective_state = _state_from_instances(actor, updated_instances)
    return ConditionMutationResult(
        condition_instances=updated_instances,
        concentration_broken=(ConditionType.INCAPACITATED in effective_state.effective_types and actor.concentrating_effect_id is not None),
        defeated_by_exhaustion=effective_state.exhaustion_level >= 6,
    )


def remove_condition(
    actor: RuntimeActorState,
    *,
    condition_type: ConditionType | None = None,
    instance_id: str | None = None,
) -> ConditionRemovalResult:
    if condition_type is None and instance_id is None:
        raise EncounterValidationError('Removing a condition requires a condition type or an instance id.')
    remaining: list[ConditionInstance] = []
    removed_unconscious = False
    removed_any = False
    for instance in actor.condition_instances:
        matches_type = condition_type is not None and instance.condition_type == condition_type
        matches_instance = instance_id is not None and instance.instance_id == instance_id
        if matches_type or matches_instance:
            removed_any = True
            if instance.condition_type == ConditionType.UNCONSCIOUS:
                removed_unconscious = True
            continue
        remaining.append(instance)
    if not removed_any:
        return ConditionRemovalResult(condition_instances=actor.condition_instances)
    added_instances: tuple[ConditionInstance, ...] = ()
    remaining_tuple = tuple(remaining)
    if removed_unconscious and ConditionType.PRONE not in _state_from_instances(actor, remaining_tuple).effective_types:
        prone_instance = ConditionInstance(
            instance_id=f'prone-after-unconscious:{actor.actor_id}',
            condition_type=ConditionType.PRONE,
            source_label='unconscious-ended',
        )
        remaining_tuple = remaining_tuple + (prone_instance,)
        added_instances = (prone_instance,)
    return ConditionRemovalResult(condition_instances=remaining_tuple, added_instances=added_instances)


def is_immune_to_condition(actor: RuntimeActorState, condition_type: ConditionType) -> bool:
    if condition_type in actor.condition_immunities:
        return True
    state = get_condition_state(actor)
    return condition_type == ConditionType.POISONED and ConditionType.PETRIFIED in state.effective_types


def get_dragged_targets(encounter_state: EncounterState, grappler_actor_id: str) -> tuple[RuntimeActorState, ...]:
    dragged: list[RuntimeActorState] = []
    for actor in encounter_state.actors.values():
        for instance in actor.condition_instances:
            if not instance.suppressed and instance.condition_type == ConditionType.GRAPPLED and instance.grappler_actor_id == grappler_actor_id:
                dragged.append(actor)
                break
    return tuple(dragged)


def apply_damage_modifiers(target: RuntimeActorState, damage_total: int, damage_type: str) -> DamageResolution:
    state = get_condition_state(target)
    if damage_type in target.damage_immunities:
        return DamageResolution(final_damage=0, immune=True)
    resisted = False
    final_damage = damage_total
    if damage_type in target.damage_resistances or ConditionType.PETRIFIED in state.effective_types:
        final_damage = damage_total // 2
        resisted = True
    return DamageResolution(final_damage=final_damage, resisted=resisted)


def _fear_source_visible_to_actor(actor: RuntimeActorState, encounter_state: EncounterState) -> bool:
    state = get_condition_state(actor)
    if ConditionType.FRIGHTENED not in state.effective_types:
        return False
    for source_actor_id in state.fear_source_actor_ids:
        source = encounter_state.actors.get(source_actor_id)
        if source is None or not source.is_conscious:
            continue
        if can_observer_see_target(actor, source, encounter_state=encounter_state):
            return True
    return False


def validate_frightened_movement(actor: RuntimeActorState, encounter_state: EncounterState, destination) -> None:
    actor_state = get_condition_state(actor)
    if ConditionType.FRIGHTENED not in actor_state.effective_types:
        return
    for source_actor_id in actor_state.fear_source_actor_ids:
        source = encounter_state.actors.get(source_actor_id)
        if source is None or not source.is_conscious:
            continue
        if not can_observer_see_target(actor, source, encounter_state=encounter_state):
            continue
        current_distance = grid_distance_ft(actor.position, source.position)
        next_distance = grid_distance_ft(destination, source.position)
        if next_distance < current_distance:
            raise EncounterValidationError('A frightened actor cannot willingly move closer to the source of fear while it is in line of sight.')


def _same_condition_source(left: ConditionInstance, right: ConditionInstance) -> bool:
    return (
        left.condition_type == right.condition_type
        and left.source_actor_id == right.source_actor_id
        and left.source_effect_id == right.source_effect_id
        and left.charmer_actor_id == right.charmer_actor_id
        and left.fear_source_actor_id == right.fear_source_actor_id
        and left.grappler_actor_id == right.grappler_actor_id
    )


def _state_from_instances(actor: RuntimeActorState, instances: Iterable[ConditionInstance]) -> ConditionStateView:
    clone = replace(actor, condition_instances=tuple(instances))
    return get_condition_state(clone)


