from __future__ import annotations

import copy
from shared_types.battlefield import MovementIntentMode, MovementPreviewOutcome
from shared_types.conditions import ConditionType
from shared_types.capabilities import CapabilityKind, TargetSelectionKind
from shared_types.encounter_models import (
    AttackUsageKind,
    CombatActionType,
    EncounterState,
    GridPosition,
    PendingAttackState,
    ReadyResponseKind,
    RuntimeCapabilityState,
    RuntimeSpellState,
    ReactionOption,
    RuntimeActorState,
)
from shared_types.models import ChoiceView
from shared_types.errors import EncounterValidationError

from .battlefield import BattlefieldRules
from .conditions import can_take_reactions, has_condition


_battlefield_rules = BattlefieldRules()


_MONSTER_CAPABILITY_KINDS = frozenset({CapabilityKind.MONSTER_ACTION, CapabilityKind.MONSTER_TRAIT})
_FEATURE_CAPABILITY_KINDS = frozenset({CapabilityKind.CLASS_FEATURE, CapabilityKind.SPECIES_TRAIT, CapabilityKind.FEAT})
_ITEM_CAPABILITY_KINDS = frozenset({CapabilityKind.ITEM})


def _spell_choice(spell) -> ChoiceView:
    uses = spell.remaining_uses if spell.remaining_uses is not None else 'at-will'
    return ChoiceView(option_id=spell.option_id, label=spell.name, detail=f"{spell.action_cost}; uses {uses}")



def _capability_choice(capability) -> ChoiceView:
    uses = capability.remaining_uses if capability.remaining_uses is not None else 'at-will'
    return ChoiceView(option_id=capability.option_id, label=capability.name, detail=f"{capability.action_cost}; uses {uses}")



def _runtime_capability_choices(
    actor: RuntimeActorState,
    *,
    action_cost: str,
    kinds: frozenset[CapabilityKind] | None = None,
) -> tuple[ChoiceView, ...]:
    return tuple(
        _capability_choice(capability)
        for capability in actor.capabilities.values()
        if (
            capability.action_cost == action_cost
            or (action_cost == 'bonus' and capability.action_cost == 'bonus-action')
        )
        and (capability.remaining_uses is None or capability.remaining_uses > 0)
        and (kinds is None or capability.kind in kinds)
    )



def action_spell_choices(actor: RuntimeActorState) -> tuple[ChoiceView, ...]:
    return tuple(
        _spell_choice(spell)
        for spell in actor.spells.values()
        if spell.action_cost == 'action' and (spell.remaining_uses is None or spell.remaining_uses > 0)
    )



def feature_action_choices(actor: RuntimeActorState) -> tuple[ChoiceView, ...]:
    return _runtime_capability_choices(actor, action_cost='action', kinds=_FEATURE_CAPABILITY_KINDS | _MONSTER_CAPABILITY_KINDS)



def item_action_choices(actor: RuntimeActorState) -> tuple[ChoiceView, ...]:
    return _runtime_capability_choices(actor, action_cost='action', kinds=_ITEM_CAPABILITY_KINDS)



def bonus_action_choices(actor: RuntimeActorState) -> tuple[ChoiceView, ...]:
    if not actor.bonus_action_available:
        return ()
    spell_choices = tuple(
        _spell_choice(spell)
        for spell in actor.spells.values()
        if spell.action_cost in {'bonus', 'bonus-action'} and (spell.remaining_uses is None or spell.remaining_uses > 0)
    )
    capability_choices = _runtime_capability_choices(actor, action_cost='bonus')
    return spell_choices + capability_choices



def available_standard_action_choices(actor: RuntimeActorState) -> tuple[ChoiceView, ...]:
    return (
        ChoiceView(option_id='attack', label='Attack', detail='action'),
        ChoiceView(option_id='dash', label='Dash', detail='action'),
        ChoiceView(option_id='disengage', label='Disengage', detail='action'),
        ChoiceView(option_id='dodge', label='Dodge', detail='action'),
        ChoiceView(option_id='help', label='Help', detail='action'),
        ChoiceView(option_id='hide', label='Hide', detail='action'),
        ChoiceView(option_id='ready', label='Ready', detail='action'),
        ChoiceView(option_id='search', label='Search', detail='action'),
        ChoiceView(option_id='study', label='Study', detail='action'),
        ChoiceView(option_id='utilize', label='Utilize', detail='action'),
        ChoiceView(option_id='grapple', label='Grapple', detail='action'),
        ChoiceView(option_id='shove', label='Shove', detail='action'),
    )



def _blocks_opportunity_attacks(state: EncounterState, actor_id: str) -> bool:
    return any(actor_id in effect.target_actor_ids and effect.definition.blocks_opportunity_attacks for effect in state.active_effects.values())


def discover_leave_reach_reactions(
    state: EncounterState,
    *,
    moving_actor_id: str,
    from_position: GridPosition,
    to_position: GridPosition,
    path: tuple[GridPosition, ...] | None = None,
) -> tuple[ReactionOption, ...]:
    moving_actor = state.actors[moving_actor_id]
    options: list[ReactionOption] = []
    if moving_actor.disengage_active or _blocks_opportunity_attacks(state, moving_actor_id):
        return ()
    trigger_path = path or (to_position,)
    for actor in state.actors.values():
        if actor.actor_id == moving_actor_id or actor.side == moving_actor.side:
            continue
        if not actor.reaction_available or not actor.is_conscious or not can_take_reactions(actor):
            continue
        for attack in actor.attacks.values():
            if attack.source_item_id is not None:
                held_items = list(actor.held_item_ids)
                if attack.source_item_id not in held_items:
                    continue
                if attack.required_hand_count >= 2:
                    held_items.remove(attack.source_item_id)
                    if actor.worn_shield_item_id is not None or held_items:
                        continue
            if attack.attack_kind.value.startswith('melee') and _battlefield_rules.detect_leaving_reach_triggers(actor, from_position=from_position, path=trigger_path, reach_ft=(attack.reach_ft or 5)):
                options.append(
                    ReactionOption(
                        option_id=f'opportunity:{actor.actor_id}:{attack.attack_id}',
                        actor_id=actor.actor_id,
                        action_type=CombatActionType.OPPORTUNITY_ATTACK,
                        label=f'Opportunity Attack ({attack.name})',
                        detail=f'against {moving_actor.name}',
                        attack_id=attack.attack_id,
                        target_id=moving_actor_id,
                    )
                )
    return tuple(options)



def discover_hit_reactions(
    state: EncounterState,
    *,
    target_id: str,
) -> tuple[ReactionOption, ...]:
    actor = state.actors[target_id]
    if not actor.reaction_available or not actor.is_conscious or not can_take_reactions(actor):
        return ()
    options: list[ReactionOption] = []
    for spell in actor.spells.values():
        capability_id = (spell.capability.capability_id if spell.capability is not None else None)
        if capability_id == 'shield' and spell.action_cost == 'reaction' and (spell.remaining_uses is None or spell.remaining_uses > 0):
            options.append(
                ReactionOption(
                    option_id=f'shield:{actor.actor_id}:{spell.option_id}',
                    actor_id=actor.actor_id,
                    action_type=CombatActionType.SHIELD,
                    label='Shield',
                    detail='reaction spell',
                    spell_id=spell.option_id,
                    target_id=target_id,
                )
            )
    return tuple(options)


def discover_damage_reactions(
    state: EncounterState,
    *,
    target_id: str,
    source_actor_id: str,
) -> tuple[ReactionOption, ...]:
    actor = state.actors[target_id]
    source = state.actors.get(source_actor_id)
    if source is None:
        return ()
    if not actor.reaction_available or not actor.is_conscious or not can_take_reactions(actor):
        return ()
    if actor.side == source.side:
        return ()
    if _battlefield_rules.get_distance3d(actor.position, source.position) > 60:
        return ()
    if not _battlefield_rules.has_line_of_sight_to_position(state, actor, source.position):
        return ()
    options: list[ReactionOption] = []
    for spell in actor.spells.values():
        capability_id = (spell.capability.capability_id if spell.capability is not None else None)
        if capability_id == 'hellish-rebuke' and spell.action_cost == 'reaction' and (spell.remaining_uses is None or spell.remaining_uses > 0):
            options.append(
                ReactionOption(
                    option_id=f'hellish-rebuke:{actor.actor_id}:{spell.option_id}',
                    actor_id=actor.actor_id,
                    action_type=CombatActionType.MAGIC,
                    label='Hellish Rebuke',
                    detail=f'against {source.name}',
                    spell_id=spell.option_id,
                    target_id=source_actor_id,
                    consumes_reaction=True,
                    resource_to_spend='reaction',
                )
            )
    return tuple(options)


def discover_fall_reactions(
    state: EncounterState,
    *,
    falling_actor_id: str,
    from_position: GridPosition,
) -> tuple[ReactionOption, ...]:
    falling_actor = state.actors[falling_actor_id]
    options: list[ReactionOption] = []
    for actor in state.actors.values():
        if actor.actor_id == falling_actor_id:
            continue
        if not actor.reaction_available or not actor.is_conscious or not can_take_reactions(actor):
            continue
        if _battlefield_rules.get_distance3d(actor.position, from_position) > 60:
            continue
        if not _battlefield_rules.has_line_of_sight_to_position(state, actor, from_position):
            continue
        for spell in actor.spells.values():
            capability_id = (spell.capability.capability_id if spell.capability is not None else None)
            if capability_id == 'feather-fall' and spell.action_cost == 'reaction' and (spell.remaining_uses is None or spell.remaining_uses > 0):
                options.append(
                    ReactionOption(
                        option_id=f'feather-fall:{actor.actor_id}:{spell.option_id}:{falling_actor_id}',
                        actor_id=actor.actor_id,
                        action_type=CombatActionType.MAGIC,
                        label='Feather Fall',
                        detail=f'protect {falling_actor.name}',
                        spell_id=spell.option_id,
                        target_id=falling_actor_id,
                        consumes_reaction=True,
                        resource_to_spend='reaction',
                    )
                )
    return tuple(options)



def _sneak_attack_available_this_turn(state: EncounterState, actor: RuntimeActorState) -> bool:
    if state.phase != state.phase.IN_PROGRESS:
        return actor.last_sneak_attack_round_number is None
    return not (
        actor.last_sneak_attack_round_number == state.round_number
        and actor.last_sneak_attack_turn_actor_id == state.active_actor_id
    )


def _sneak_attack_has_adjacent_ally(state: EncounterState, *, actor: RuntimeActorState, target: RuntimeActorState) -> bool:
    for ally in state.actors.values():
        if ally.actor_id == actor.actor_id or ally.side != actor.side or ally.is_dead or not ally.is_conscious:
            continue
        if has_condition(ally, ConditionType.INCAPACITATED):
            continue
        if _battlefield_rules.get_distance3d(ally.position, target.position) <= 5:
            return True
    return False


def _pending_attack_is_finesse_attack(actor: RuntimeActorState, pending_attack: PendingAttackState) -> bool:
    attack = actor.attacks.get(pending_attack.attack_id)
    return attack is not None and attack.is_finesse


def _sneak_attack_qualifies(state: EncounterState, *, actor: RuntimeActorState, target: RuntimeActorState, pending_attack: PendingAttackState) -> bool:
    if actor.character_record is None:
        return False
    if 'Sneak Attack' not in actor.character_record.class_feature_names:
        return False
    if not _sneak_attack_available_this_turn(state, actor):
        return False
    if pending_attack.attack_usage_kind != AttackUsageKind.WEAPON_RANGED and not _pending_attack_is_finesse_attack(actor, pending_attack):
        return False
    if pending_attack.had_advantage and not pending_attack.had_disadvantage:
        return True
    if pending_attack.had_disadvantage:
        return False
    return _sneak_attack_has_adjacent_ally(state, actor=actor, target=target)


def discover_post_hit_reactions(
    state: EncounterState,
    *,
    pending_attack: PendingAttackState,
) -> tuple[ReactionOption, ...]:
    actor = state.actors[pending_attack.actor_id]
    target = state.actors.get(pending_attack.target_id)
    if target is None or target.is_dead:
        return ()
    options: list[ReactionOption] = []
    if _sneak_attack_qualifies(state, actor=actor, target=target, pending_attack=pending_attack):
        options.append(
            ReactionOption(
                option_id=f'sneak-attack:{actor.actor_id}:{pending_attack.attack_id}:{target.actor_id}',
                actor_id=actor.actor_id,
                action_type=CombatActionType.FEATURE,
                label='Sneak Attack',
                detail=f'against {target.name}',
                capability_id='sneak-attack',
                target_id=target.actor_id,
                consumes_reaction=False,
                resource_to_spend=None,
            )
        )
    for spell in actor.spells.values():
        capability_id = (spell.capability.capability_id if spell.capability is not None else None)
        if spell.remaining_uses is not None and spell.remaining_uses <= 0:
            continue
        if capability_id in {'divine-smite', 'ensnaring-strike', 'searing-smite', 'thunderous-smite', 'wrathful-smite'}:
            if not actor.bonus_action_available:
                continue
            if pending_attack.attack_kind != pending_attack.attack_kind.RANGED and (pending_attack.source_item_id is not None or pending_attack.attack_id == 'unarmed-strike' or pending_attack.attack_usage_kind == AttackUsageKind.WEAPON_MELEE):
                label = {
                    'divine-smite': 'Divine Smite',
                    'ensnaring-strike': 'Ensnaring Strike',
                    'searing-smite': 'Searing Smite',
                    'thunderous-smite': 'Thunderous Smite',
                    'wrathful-smite': 'Wrathful Smite',
                }[capability_id]
                options.append(
                    ReactionOption(
                        option_id=f'{capability_id}:{actor.actor_id}:{spell.option_id}',
                        actor_id=actor.actor_id,
                        action_type=CombatActionType.MAGIC,
                        label=label,
                        detail=f'against {target.name}',
                        spell_id=spell.option_id,
                        target_id=target.actor_id,
                        consumes_reaction=False,
                        resource_to_spend='bonus',
                    )
                )
        if capability_id == 'hail-of-thorns':
            if not actor.bonus_action_available:
                continue
            if pending_attack.attack_usage_kind == AttackUsageKind.WEAPON_RANGED:
                options.append(
                    ReactionOption(
                        option_id=f'hail-of-thorns:{actor.actor_id}:{spell.option_id}',
                        actor_id=actor.actor_id,
                        action_type=CombatActionType.MAGIC,
                        label='Hail of Thorns',
                        detail=f'around {target.name}',
                        spell_id=spell.option_id,
                        target_id=target.actor_id,
                        consumes_reaction=False,
                        resource_to_spend='bonus',
                    )
                )
    return tuple(options)


def _ready_creature_target_is_legal(state: EncounterState, *, actor: RuntimeActorState, target: RuntimeActorState, range_ft: int | None, requires_target_to_be_seen: bool, requires_line_of_effect: bool) -> bool:
    if target.is_dead:
        return False
    if range_ft is not None and _battlefield_rules.get_distance3d(actor.position, target.position) > range_ft:
        return False
    if requires_target_to_be_seen and not _battlefield_rules.has_line_of_sight_to_position(state, actor, target.position):
        return False
    if requires_line_of_effect and not _battlefield_rules.has_line_of_effect_to_position(state, actor, target.position):
        return False
    return True


def discover_ready_reactions(
    state: EncounterState,
    *,
    trigger_actor_id: str,
) -> tuple[ReactionOption, ...]:
    trigger_actor = state.actors[trigger_actor_id]
    options: list[ReactionOption] = []
    for actor in state.actors.values():
        readied_action = actor.readied_action
        if readied_action is None:
            continue
        if not actor.reaction_available or not actor.is_conscious or not can_take_reactions(actor):
            continue
        if readied_action.trigger.trigger_actor_id != trigger_actor_id:
            continue
        if readied_action.response.response_kind == ReadyResponseKind.ATTACK:
            attack_id = readied_action.response.attack_id
            if attack_id is None:
                continue
            attack = actor.attacks.get(attack_id)
            if attack is None:
                continue
            if attack.source_item_id is not None:
                held_items = list(actor.held_item_ids)
                if attack.source_item_id not in held_items:
                    continue
                if attack.required_hand_count >= 2:
                    held_items.remove(attack.source_item_id)
                    if actor.worn_shield_item_id is not None or held_items:
                        continue
            try:
                legality = _battlefield_rules.attack_legality(state, actor, trigger_actor, attack)
            except EncounterValidationError:
                continue
            if not legality.has_line_of_sight or not legality.has_line_of_effect:
                continue
            options.append(
                ReactionOption(
                    option_id=f'ready:{actor.actor_id}',
                    actor_id=actor.actor_id,
                    action_type=CombatActionType.READY,
                    label=f'Readied Attack ({attack.name})',
                    detail=f'against {trigger_actor.name}',
                    attack_id=attack.attack_id,
                    target_id=trigger_actor_id,
                )
            )
            continue
        if readied_action.response.response_kind == ReadyResponseKind.SPELL:
            spell_id = readied_action.response.spell_id
            spell: RuntimeSpellState | None = actor.spells.get(spell_id or '')
            if spell is None or spell.capability is None:
                continue
            if spell.capability.targeting.selection_kind != TargetSelectionKind.CREATURE:
                continue
            if not _ready_creature_target_is_legal(
                state,
                actor=actor,
                target=trigger_actor,
                range_ft=spell.capability.targeting.range_ft,
                requires_target_to_be_seen=spell.capability.targeting.requires_target_to_be_seen,
                requires_line_of_effect=spell.capability.targeting.requires_line_of_effect,
            ):
                continue
            options.append(
                ReactionOption(
                    option_id=f'ready:{actor.actor_id}',
                    actor_id=actor.actor_id,
                    action_type=CombatActionType.READY,
                    label=f'Readied Spell ({spell.name})',
                    detail=f'against {trigger_actor.name}',
                    spell_id=spell.option_id,
                    target_id=trigger_actor_id,
                )
            )
            continue
        if readied_action.response.response_kind == ReadyResponseKind.CAPABILITY:
            capability_id = readied_action.response.capability_id
            runtime_capability: RuntimeCapabilityState | None = actor.capabilities.get(capability_id or '')
            capability = runtime_capability.capability if runtime_capability is not None else None
            if capability is None or capability.targeting.selection_kind != TargetSelectionKind.CREATURE:
                continue
            if not _ready_creature_target_is_legal(
                state,
                actor=actor,
                target=trigger_actor,
                range_ft=capability.targeting.range_ft,
                requires_target_to_be_seen=capability.targeting.requires_target_to_be_seen,
                requires_line_of_effect=capability.targeting.requires_line_of_effect,
            ):
                continue
            options.append(
                ReactionOption(
                    option_id=f'ready:{actor.actor_id}',
                    actor_id=actor.actor_id,
                    action_type=CombatActionType.READY,
                    label=f'Readied {capability.name}',
                    detail=f'against {trigger_actor.name}',
                    target_id=trigger_actor_id,
                )
            )
            continue
        if readied_action.response.response_kind == ReadyResponseKind.MOVE:
            destination = readied_action.response.destination
            if destination is None:
                continue
            preview_actor = copy.deepcopy(actor)
            preview_actor.movement_spent_ft = 0
            preview_actor.remaining_movement_ft = preview_actor.max_path_speed_ft
            preview = _battlefield_rules.preview_move(
                state,
                preview_actor,
                destination,
                movement_intent_mode=readied_action.response.movement_intent_mode,
            )
            if preview.plan is None:
                continue
            if preview.outcome not in {
                MovementPreviewOutcome.REACHABLE_SAME_PLANE,
                MovementPreviewOutcome.REACHABLE_WITH_SLOPE,
                MovementPreviewOutcome.REACHABLE_WITH_CLIMB,
                MovementPreviewOutcome.REACHABLE_WITH_FLY,
            }:
                continue
            if not _battlefield_rules.has_line_of_sight_to_position(state, actor, trigger_actor.position):
                continue
            options.append(
                ReactionOption(
                    option_id=f'ready:{actor.actor_id}',
                    actor_id=actor.actor_id,
                    action_type=CombatActionType.READY,
                    label='Readied Move',
                    detail=f'toward ({destination.x},{destination.y},{destination.z}) after {trigger_actor.name} moves',
                    target_id=trigger_actor_id,
                )
            )
    return tuple(sorted(options, key=lambda option: (option.actor_id, option.option_id)))





