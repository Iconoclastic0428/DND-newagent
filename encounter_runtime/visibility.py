from __future__ import annotations

from typing import Iterable

from shared_types.battlefield import CoverLevel
from shared_types.conditions import ConditionType
from shared_types.encounter_models import EncounterState, GridPosition, RuntimeActorState
from shared_types.visibility import (
    LightLevel,
    ObscurementLevel,
    ObserverVisibilityState,
    VisibilityAssessment,
)


_BATTLEFIELD_RULES = None


def _battlefield_rules():
    global _BATTLEFIELD_RULES
    if _BATTLEFIELD_RULES is None:
        from .battlefield import BattlefieldRules
        _BATTLEFIELD_RULES = BattlefieldRules()
    return _BATTLEFIELD_RULES


def _condition_state(actor: RuntimeActorState):
    from .conditions import get_condition_state
    return get_condition_state(actor)


def _suppresses_invisible_benefits(state: EncounterState, actor_id: str) -> bool:
    return any(actor_id in effect.target_actor_ids and effect.definition.suppress_invisible_benefits for effect in state.active_effects.values())


def _light_priority(level: LightLevel) -> int:
    return {
        LightLevel.DARKNESS: 0,
        LightLevel.DIM: 1,
        LightLevel.BRIGHT: 2,
    }[level]


def _position_within_radius(origin: GridPosition, position: GridPosition, radius_ft: int) -> bool:
    return _battlefield_rules().get_distance3d(origin, position) <= radius_ft


def _dynamic_light_level_at_position(state: EncounterState, position: GridPosition) -> LightLevel | None:
    best: LightLevel | None = None
    for effect in state.active_effects.values():
        if effect.definition.bright_light_radius_ft <= 0 and effect.definition.dim_light_radius_ft <= 0:
            continue
        anchors: list[GridPosition] = []
        if effect.target_actor_ids:
            anchors.extend(state.actors[target_id].position for target_id in effect.target_actor_ids if target_id in state.actors)
        elif effect.origin_point is not None:
            anchors.append(effect.origin_point)
        else:
            source = state.actors.get(effect.source_actor_id)
            if source is not None:
                anchors.append(source.position)
        for anchor in anchors:
            if effect.definition.bright_light_radius_ft > 0 and _position_within_radius(anchor, position, effect.definition.bright_light_radius_ft):
                return LightLevel.BRIGHT
            if effect.definition.dim_light_radius_ft > 0 and _position_within_radius(anchor, position, effect.definition.dim_light_radius_ft):
                if best is None or _light_priority(LightLevel.DIM) > _light_priority(best):
                    best = LightLevel.DIM
    for area in state.persistent_areas.values():
        if area.definition.bright_light_radius_ft > 0 and _position_within_radius(area.origin, position, area.definition.bright_light_radius_ft):
            return LightLevel.BRIGHT
        if area.definition.dim_light_radius_ft > 0 and _position_within_radius(area.origin, position, area.definition.dim_light_radius_ft):
            if best is None or _light_priority(LightLevel.DIM) > _light_priority(best):
                best = LightLevel.DIM
    return best




def _dynamic_obscurement_at_position(state: EncounterState, position: GridPosition) -> ObscurementLevel | None:
    from .persistent_effects import persistent_area_contains_position

    best: ObscurementLevel | None = None
    for area in state.persistent_areas.values():
        if not persistent_area_contains_position(area, position):
            continue
        level = area.definition.obscurement_level
        if area.definition.blocks_vision and level is None:
            level = ObscurementLevel.HEAVY
        if level is None:
            continue
        if best is None or level.value == ObscurementLevel.HEAVY.value or (best != ObscurementLevel.HEAVY and level != ObscurementLevel.NONE):
            best = level
    return best

def passive_perception(actor: RuntimeActorState) -> int:
    return actor.passive_perception


def _observer_has_darkvision_to_position(observer: RuntimeActorState, position: GridPosition) -> bool:
    return observer.darkvision_radius_ft > 0 and _position_within_radius(observer.position, position, observer.darkvision_radius_ft)


def _observer_has_nonvisual_precision(observer: RuntimeActorState, position: GridPosition) -> bool:
    if observer.blindsight_radius_ft > 0 and _position_within_radius(observer.position, position, observer.blindsight_radius_ft):
        return True
    if observer.truesight_radius_ft > 0 and _position_within_radius(observer.position, position, observer.truesight_radius_ft):
        return True
    return False


def target_light_level(state: EncounterState, target: RuntimeActorState) -> LightLevel:
    tile = _battlefield_rules().get_tile(state.battlefield, target.position.x, target.position.y)
    dynamic = _dynamic_light_level_at_position(state, target.position)
    if dynamic is None or _light_priority(tile.light_level) >= _light_priority(dynamic):
        return tile.light_level
    return dynamic


def target_obscurement(state: EncounterState, target: RuntimeActorState) -> ObscurementLevel:
    tile = _battlefield_rules().get_tile(state.battlefield, target.position.x, target.position.y)
    dynamic = _dynamic_obscurement_at_position(state, target.position)
    if dynamic is None:
        return tile.obscurement
    if tile.obscurement == ObscurementLevel.HEAVY or dynamic == ObscurementLevel.HEAVY:
        return ObscurementLevel.HEAVY
    if tile.obscurement != ObscurementLevel.NONE or dynamic != ObscurementLevel.NONE:
        return ObscurementLevel.LIGHT
    return ObscurementLevel.NONE


def can_observer_see_position(state: EncounterState, observer: RuntimeActorState, position: GridPosition) -> bool:
    observer_state = _condition_state(observer)
    if ConditionType.BLINDED in observer_state.effective_types:
        return False
    if not _battlefield_rules().has_line_of_sight_to_position(state, observer, position):
        return False
    tile = _battlefield_rules().get_tile(state.battlefield, position.x, position.y)
    light_level = _dynamic_light_level_at_position(state, position)
    if light_level is None or _light_priority(tile.light_level) >= _light_priority(light_level):
        light_level = tile.light_level
    if light_level == LightLevel.DARKNESS and not _observer_has_darkvision_to_position(observer, position):
        return False
    obscurement = _dynamic_obscurement_at_position(state, position)
    if obscurement is None:
        obscurement = tile.obscurement
    elif tile.obscurement == ObscurementLevel.HEAVY or obscurement == ObscurementLevel.HEAVY:
        obscurement = ObscurementLevel.HEAVY
    elif tile.obscurement != ObscurementLevel.NONE or obscurement != ObscurementLevel.NONE:
        obscurement = ObscurementLevel.LIGHT
    if obscurement == ObscurementLevel.HEAVY:
        return False
    return True


def assess_visibility(state: EncounterState, observer: RuntimeActorState, target: RuntimeActorState) -> VisibilityAssessment:
    observer_state = _condition_state(observer)
    target_state = _condition_state(target)
    line_of_sight = _battlefield_rules().has_line_of_sight(state, observer, target)
    line_of_effect = _battlefield_rules().has_line_of_effect(state, observer, target)
    light_level = target_light_level(state, target)
    obscurement = target_obscurement(state, target)
    hidden_from_observer = target.hidden and observer.actor_id in target.hidden_from_actor_ids

    if hidden_from_observer:
        return VisibilityAssessment(
            observer_id=observer.actor_id,
            target_id=target.actor_id,
            visibility_state=ObserverVisibilityState.HIDDEN,
            can_see_target=False,
            knows_target_location=False,
            line_of_sight=line_of_sight,
            line_of_effect=line_of_effect,
            target_light_level=light_level,
            target_obscurement=obscurement,
            detail='The target is hidden from this observer.',
        )

    if ConditionType.BLINDED in observer_state.effective_types:
        return VisibilityAssessment(
            observer_id=observer.actor_id,
            target_id=target.actor_id,
            visibility_state=ObserverVisibilityState.UNSEEN,
            can_see_target=False,
            knows_target_location=True,
            line_of_sight=line_of_sight,
            line_of_effect=line_of_effect,
            target_light_level=light_level,
            target_obscurement=obscurement,
            detail='The observer is blinded.',
        )

    if not line_of_sight:
        return VisibilityAssessment(
            observer_id=observer.actor_id,
            target_id=target.actor_id,
            visibility_state=ObserverVisibilityState.HIDDEN,
            can_see_target=False,
            knows_target_location=False,
            line_of_sight=False,
            line_of_effect=line_of_effect,
            target_light_level=light_level,
            target_obscurement=obscurement,
            detail='Line of sight is blocked.',
        )

    if ConditionType.INVISIBLE in target_state.effective_types and not _suppresses_invisible_benefits(state, target.actor_id) and not observer.can_see_invisible:
        return VisibilityAssessment(
            observer_id=observer.actor_id,
            target_id=target.actor_id,
            visibility_state=ObserverVisibilityState.UNSEEN,
            can_see_target=False,
            knows_target_location=True,
            line_of_sight=True,
            line_of_effect=line_of_effect,
            target_light_level=light_level,
            target_obscurement=obscurement,
            detail='The target is invisible to this observer.',
        )

    if light_level == LightLevel.DARKNESS and not _observer_has_darkvision_to_position(observer, target.position):
        return VisibilityAssessment(
            observer_id=observer.actor_id,
            target_id=target.actor_id,
            visibility_state=ObserverVisibilityState.UNSEEN,
            can_see_target=False,
            knows_target_location=True,
            line_of_sight=True,
            line_of_effect=line_of_effect,
            target_light_level=light_level,
            target_obscurement=obscurement,
            detail='The target is in darkness.',
        )

    if obscurement == ObscurementLevel.HEAVY:
        return VisibilityAssessment(
            observer_id=observer.actor_id,
            target_id=target.actor_id,
            visibility_state=ObserverVisibilityState.UNSEEN,
            can_see_target=False,
            knows_target_location=True,
            line_of_sight=True,
            line_of_effect=line_of_effect,
            target_light_level=light_level,
            target_obscurement=obscurement,
            detail='The target is heavily obscured.',
        )

    return VisibilityAssessment(
        observer_id=observer.actor_id,
        target_id=target.actor_id,
        visibility_state=ObserverVisibilityState.VISIBLE,
        can_see_target=True,
        knows_target_location=True,
        line_of_sight=True,
        line_of_effect=line_of_effect,
        target_light_level=light_level,
        target_obscurement=obscurement,
        detail=None,
    )


def can_observer_see_target(state: EncounterState, observer: RuntimeActorState, target: RuntimeActorState) -> bool:
    return assess_visibility(state, observer, target).can_see_target


def hide_observers_after_stealth(state: EncounterState, actor: RuntimeActorState, *, stealth_total: int) -> tuple[frozenset[str], tuple[str, ...]]:
    hidden_from: set[str] = set()
    noticed_by: list[str] = []
    for observer in state.actors.values():
        if observer.actor_id == actor.actor_id or observer.side == actor.side or not observer.is_conscious:
            continue
        if passive_perception(observer) >= stealth_total:
            noticed_by.append(observer.actor_id)
            continue
        if not can_actor_hide_from_observer(state, actor, observer):
            noticed_by.append(observer.actor_id)
            continue
        hidden_from.add(observer.actor_id)
    return frozenset(hidden_from), tuple(noticed_by)


def refresh_hidden_observers(state: EncounterState, actor: RuntimeActorState) -> tuple[frozenset[str], tuple[str, ...]]:
    stealth_total = actor.stealth_check_total
    if stealth_total is None:
        return frozenset(), ()
    hidden_from: set[str] = set()
    revealed_to: list[str] = []
    for observer in state.actors.values():
        if observer.actor_id == actor.actor_id or observer.side == actor.side or not observer.is_conscious:
            continue
        if passive_perception(observer) >= stealth_total or not can_actor_hide_from_observer(state, actor, observer):
            if observer.actor_id in actor.hidden_from_actor_ids:
                revealed_to.append(observer.actor_id)
            continue
        hidden_from.add(observer.actor_id)
    return frozenset(hidden_from), tuple(revealed_to)


def can_actor_hide_from_observer(state: EncounterState, actor: RuntimeActorState, observer: RuntimeActorState) -> bool:
    if not observer.is_conscious:
        return True
    observer_state = _condition_state(observer)
    target_state = _condition_state(actor)
    if ConditionType.BLINDED in observer_state.effective_types:
        return True
    if ConditionType.INVISIBLE in target_state.effective_types and not _suppresses_invisible_benefits(state, target.actor_id) and not observer.can_see_invisible:
        return True
    if target_light_level(state, actor) != LightLevel.BRIGHT:
        return True
    if tile.obscurement != ObscurementLevel.NONE:
        return True
    if not _battlefield_rules.has_line_of_sight(state, observer, actor):
        return True
    cover = _battlefield_rules().get_cover(state, observer, actor)
    return cover != CoverLevel.NONE


def passive_perception_for_actor(actor: RuntimeActorState) -> int:
    return passive_perception(actor)


def supports_hiding_from_observer(state: EncounterState, actor: RuntimeActorState, observer: RuntimeActorState) -> bool:
    return can_actor_hide_from_observer(state, actor, observer)


def controller_visibility_state(state: EncounterState, observer_actor_ids: Iterable[str], target: RuntimeActorState) -> ObserverVisibilityState:
    observer_ids = tuple(dict.fromkeys(observer_actor_ids))
    if target.actor_id in observer_ids:
        return ObserverVisibilityState.VISIBLE
    aggregate = ObserverVisibilityState.HIDDEN
    for observer_id in observer_ids:
        observer = state.actors.get(observer_id)
        if observer is None or not observer.is_conscious:
            continue
        candidate = assess_visibility(state, observer, target).visibility_state
        if candidate == ObserverVisibilityState.VISIBLE:
            return ObserverVisibilityState.VISIBLE
        if candidate == ObserverVisibilityState.UNSEEN:
            aggregate = ObserverVisibilityState.UNSEEN
    return aggregate


def controller_can_see_position(state: EncounterState, observer_actor_ids: Iterable[str], position: GridPosition) -> bool:
    for observer_id in dict.fromkeys(observer_actor_ids):
        observer = state.actors.get(observer_id)
        if observer is None or not observer.is_conscious:
            continue
        if observer.position == position or can_observer_see_position(state, observer, position):
            return True
    return False
