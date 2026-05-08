from __future__ import annotations

import copy
import math
from dataclasses import replace
from typing import TYPE_CHECKING, Mapping

from rules_engine.encounter_math import grid_distance_ft, roll_damage
from rules_engine.rng import seeded_random
from shared_types.battlefield import RelocationType, TraversalMode
from shared_types.capabilities import ActiveEffectDefinition, AlarmTriggerEffectDef, AlarmWardEffectDef, AreaOriginMode, AreaShape, AttackBonusSource, AttackExecutionKind, AttackRollGateEffect, CapabilityDefinition, CapabilityKind, ChainingSpellAttackEffectDef, CheckGateEffect, ChosenAbilityCheckAdvantageEffectDef, ChosenDamageReductionEffectDef, ChosenSkillBonusEffectDef, ChosenWeaponEnchantmentEffectDef, CommandWordEffectDef, CompositeEffect, ConditionalCreatureTypeDamageEffectDef, ConditionEffectDef, ConditionRemovalEffectDef, CreateOrDestroyWaterEffectDef, CreateTerrainEffectDef, CreatedObjectDefinition, DamageEffectDef, DashEffectDef, DetectionScanEffectDef, DetectionSenseKind, FriendsEffectDef, ForcedReactionMoveEffectDef, GrantInventoryItemEffectDef, GroupSaveGateEffectDef, HeldConjurationEffectDef, HeldConjurationKind, InformationPayloadDefinition, InformationPayloadKind, InformationShareMode, InstantWeaponStrikeEffectDef, ItemInspectionEffectDef, MarkTargetEffectDef, MissingHitPointsDamageEffectDef, DurationAnchor, EffectDefinition, EffectDurationType, ForcedMovementEffectDef, ForcedMovementMode as CapabilityForcedMovementMode, ForcedMovementVectorMode, HealingBonusSource, HealingEffectDef, SpendHitDiceHealingEffectDef, IllusionActualProperties, IllusionApparentProperties, IllusionDefinition, IllusionModality, IllusionRevealPolicy, IllusionSubtype, IllusionTemplateId, OngoingTriggerDefinition, ParameterizedActiveEffectDef, ParameterizedConditionEffectDef, ParameterizedDamageEffectDef, ParameterizedIllusionEffectDef, ParameterizedTargetCountGateEffectDef, PersistentAreaDefinition, PersistentObserverFilter, PersistentObserverMode, PurifyConsumablesEffectDef, RecursiveSpellAttackEffectDef, SaveDcSource, SaveGateEffect, StabilizeEffectDef, StartActiveEffectDef, SummonCompanionEffectDef, SummonedCreatureDefinition, TargetAffinity, TargetRadiusSaveEffectDef, TargetSelectionKind, TargetingSpec, TeleportEffectDef, TemporaryHitPointsEffectDef, TriggerActorScope, TriggerTiming, ZoneTickDefinition
from shared_types.conditions import ConditionType
from shared_types.models import Ability, slugify
from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType
from shared_types.effects import CheckRequest, ConditionApplication, DisplacementVector, ForcedMovementEffect, ForcedMovementMode, ResolutionContext, SaveRequest
from shared_types.equipment import EnvironmentObjectAction, ObjectInteractionCostMode, ObjectInteractionKind
from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent, ActiveEffectTickedEvent, AreaResolvedEvent, ArmorClassAdjustedEvent, AttackHitEvent, AttackMissedEvent, AttackRolledEvent, AttackRollRequestedEvent, ActionEffectEvent, CapabilityDeclaredEvent, CapabilityHitEvent, CapabilityMissedEvent, ConcentrationEndedEvent, ConcentrationStartedEvent, ConditionAddedEvent, ConditionRemovedEvent, ConsumablesPurifiedEvent, CreatedCreatureRemovedEvent, CreatedCreatureSpawnedEvent, CreatedObjectRemovedEvent, CreatedObjectSpawnedEvent, D20TestRolledEvent, DamageAppliedEvent, DamageRolledEvent, DetectionPayloadProducedEvent, DivinationPayloadProducedEvent, ForcedMovementAppliedEvent, HealingAppliedEvent, HitPointDieSpentEvent, HitPointMaximumAdjustedEvent, IllusionCreatedEvent, InventoryItemReplacedEvent, ItemGrantedEvent, ItemIdentifiedEvent, PersistentAreaCreatedEvent, PersistentAreaEndedEvent, PersistentAreaTickedEvent, PersistentEffectEndedEvent, PersistentEffectStartedEvent, PositionChangedEvent, RelocationResolvedEvent, ResourceSpentEvent, SpellCastEvent, StabilizedEvent, TargetsResolvedEvent, TeleportDeclaredEvent, TeleportResolvedEvent, TemporaryHitPointsAppliedEvent, TerrainEffectCreatedEvent
from shared_types.encounter_models import ActiveEffectState, AttackKind, AttackProfile, CombatActionType, CreatedObjectState, EncounterState, GridPosition, IllusionObserverState, IllusionState, InformationalPayloadState, PersistentAreaState, PersistentEffectFamily, PersistentEffectState, RuntimeActorState, RuntimeCapabilityState, RuntimeSpellState, SummonedCreatureState, TimingEntryKind, TimingEntryState
from shared_types.errors import EncounterValidationError

from .persistent_effects import footprint_cells, persistent_area_contains_position, rectangular_cells
from .conditions import get_effective_speed, get_targeting_visibility_legality, remove_condition, validate_hostile_targeting
from .equipment import actor_is_proficient_with_weapon, is_item_held, item_attack_profiles, item_is_weapon
from .d20_engine import merge_roll_mode

if TYPE_CHECKING:
    from .kernel import EncounterKernel


_ATTACK_KIND_MAP = {
    AttackExecutionKind.MELEE_WEAPON: AttackKind.MELEE,
    AttackExecutionKind.RANGED_WEAPON: AttackKind.RANGED,
    AttackExecutionKind.MELEE_SPELL: AttackKind.MELEE,
    AttackExecutionKind.RANGED_SPELL: AttackKind.RANGED,
}


class EncounterEffectExecutor:
    def __init__(self, *, kernel: 'EncounterKernel') -> None:
        self.kernel = kernel

    def execute_capability(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        capability: CapabilityDefinition,
        target_id: str | None = None,
        point: GridPosition | None = None,
        spell: RuntimeSpellState | None = None,
        runtime_capability: RuntimeCapabilityState | None = None,
        spend_spell_resource: bool = True,
        parameters: Mapping[str, str] | None = None,
        event_action_cost: str | None = None,
        emit_spell_cast_event: bool = True,
    ) -> list[object]:
        work = copy.deepcopy(state)
        events: list[object] = []
        declared_events: list[object] = []
        action_cost = event_action_cost or (spell.action_cost if spell is not None else capability.action_cost)
        if spell is not None and emit_spell_cast_event:
            remaining_uses = spell.remaining_uses
            resource_pool_id = None
            resource_pool_current_after = None
            if spend_spell_resource:
                remaining_uses = (None if spell.remaining_uses is None else spell.remaining_uses - 1)
                resource_pool_id = spell.resource_pool_id
                if resource_pool_id is not None:
                    pool = actor.resource_pools.get(resource_pool_id)
                    if pool is None:
                        raise EncounterValidationError(f'Spell {spell.option_id!r} references missing resource pool {resource_pool_id!r}.')
                    resource_pool_current_after = pool.current - 1
            declared_events.append(
                SpellCastEvent(
                    actor_id=actor.actor_id,
                    spell_id=spell.option_id,
                    action_cost=action_cost,
                    from_position=actor.position,
                    to_position=(point if capability.targeting.selection_kind == TargetSelectionKind.POINT else None),
                    target_id=target_id,
                    remaining_uses=remaining_uses,
                    resource_pool_id=resource_pool_id,
                    resource_pool_current_after=resource_pool_current_after,
                )
            )
        remaining_uses = None
        runtime_option_id = None
        if runtime_capability is not None:
            runtime_option_id = runtime_capability.option_id
            remaining_uses = None if runtime_capability.remaining_uses is None else runtime_capability.remaining_uses - 1
        declared_events.append(
            CapabilityDeclaredEvent(
                actor_id=actor.actor_id,
                capability_id=capability.capability_id,
                capability_name=capability.name,
                action_cost=action_cost,
                target_id=target_id,
                point=point,
                runtime_option_id=runtime_option_id,
                remaining_uses=remaining_uses,
            )
        )
        self._emit(work, events, declared_events)
        if isinstance(capability.effect, (HeldConjurationEffectDef, InstantWeaponStrikeEffectDef, RecursiveSpellAttackEffectDef)):
            raw_target_ids = ((target_id,) if target_id is not None else ())
            self._execute_effect(work, events, source_actor_id=actor.actor_id, capability=capability, effect=capability.effect, target_ids=raw_target_ids, point=point, active_effect_id=None, critical_hit=False, parameters=(parameters or {}))
            return events
        delivery_proxy_actor = self._touch_delivery_proxy_actor(work, caster=work.actors[actor.actor_id], capability=capability, parameters=(parameters or {}))
        if delivery_proxy_actor is not None:
            if not delivery_proxy_actor.reaction_available:
                raise EncounterValidationError('Your familiar has already used its reaction and cannot deliver this spell.')
            self._emit(work, events, [ResourceSpentEvent(actor_id=delivery_proxy_actor.actor_id, resource='reaction', reason='familiar-touch-delivery')])
        target_ids, resolved_point, target_events = self._resolve_targets(work, actor=work.actors[actor.actor_id], capability=capability, target_id=target_id, point=point, parameters=(parameters or {}), origin_actor=delivery_proxy_actor)
        self._emit(work, events, target_events)
        self._execute_effect(work, events, source_actor_id=actor.actor_id, capability=capability, effect=capability.effect, target_ids=target_ids, point=resolved_point, active_effect_id=None, critical_hit=False, parameters=(parameters or {}))
        return events

    def execute_spell(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        spell: RuntimeSpellState,
        target_id: str | None = None,
        point: GridPosition | None = None,
        spend_spell_resource: bool = True,
        parameters: Mapping[str, str] | None = None,
        event_action_cost: str | None = None,
        emit_spell_cast_event: bool = True,
    ) -> list[object]:
        if spell.capability is None:
            raise EncounterValidationError('That spell does not have a supported executable capability in this slice.')
        return self.execute_capability(
            state,
            actor=actor,
            capability=spell.capability,
            target_id=target_id,
            point=point,
            spell=spell,
            spend_spell_resource=spend_spell_resource,
            parameters=parameters,
            event_action_cost=event_action_cost,
            emit_spell_cast_event=emit_spell_cast_event,
        )

    def resolve_turn_boundary(self, state: EncounterState, *, actor_id: str, timing: TriggerTiming) -> list[object]:
        work = copy.deepcopy(state)
        events: list[object] = []
        for effect_id in list(work.active_effects):
            effect = work.active_effects.get(effect_id)
            if effect is None:
                continue
            if self._effect_expires_at_boundary(work, effect, actor_id=actor_id, timing=timing):
                self._end_active_effect(work, events, effect_id=effect_id, reason=f'{timing.value}-expiry')
                continue
            for trigger in effect.definition.ongoing_triggers:
                if trigger.timing != timing:
                    continue
                for trigger_actor_id in self._trigger_targets(effect, actor_id=actor_id, scope=trigger.actor_scope):
                    self._emit(work, events, [ActiveEffectTickedEvent(effect_instance_id=effect.effect_instance_id, actor_id=trigger_actor_id, timing=timing, detail=effect.name)])
                    self._resolve_ongoing_trigger(work, events, effect=effect, trigger=trigger, trigger_actor_id=trigger_actor_id)
        return events

    def collect_turn_boundary_entries(self, state: EncounterState, *, actor_id: str, timing: TriggerTiming) -> tuple[TimingEntryState, ...]:
        entries: list[TimingEntryState] = []
        for effect_id in list(state.active_effects):
            effect = state.active_effects.get(effect_id)
            if effect is None:
                continue
            if self._effect_expires_at_boundary(state, effect, actor_id=actor_id, timing=timing):
                entries.append(
                    TimingEntryState(
                        entry_id=f'{timing.value}:expire:{effect_id}',
                        actor_id=actor_id,
                        phase=timing,
                        kind=TimingEntryKind.ACTIVE_EFFECT_EXPIRE,
                        label=f'Expire {effect.name}',
                        effect_instance_id=effect_id,
                    )
                )
                continue
            for trigger_index, trigger in enumerate(effect.definition.ongoing_triggers):
                if trigger.timing != timing:
                    continue
                for trigger_actor_id in self._trigger_targets(effect, actor_id=actor_id, scope=trigger.actor_scope):
                    entries.append(
                        TimingEntryState(
                            entry_id=f'{timing.value}:trigger:{effect_id}:{trigger_index}:{trigger_actor_id}',
                            actor_id=actor_id,
                            phase=timing,
                            kind=TimingEntryKind.ACTIVE_EFFECT_TRIGGER,
                            label=f'{effect.name}',
                            effect_instance_id=effect_id,
                            trigger_index=trigger_index,
                            trigger_actor_id=trigger_actor_id,
                        )
                    )
        for area_id, area in state.persistent_areas.items():
            for trigger_index, trigger in enumerate(area.definition.tick_effects):
                if trigger.timing != timing:
                    continue
                entries.append(
                    TimingEntryState(
                        entry_id=f'{timing.value}:area:{area_id}:{trigger_index}:{actor_id}',
                        actor_id=actor_id,
                        phase=timing,
                        kind=TimingEntryKind.PERSISTENT_AREA_TICK,
                        label=area.definition.name,
                        effect_instance_id=area_id,
                        trigger_index=trigger_index,
                        trigger_actor_id=actor_id,
                    )
                )
        return tuple(entries)

    def resolve_turn_boundary_entry(self, state: EncounterState, entry: TimingEntryState) -> list[object]:
        work = copy.deepcopy(state)
        events: list[object] = []
        if entry.kind == TimingEntryKind.ACTIVE_EFFECT_EXPIRE:
            if entry.effect_instance_id is None:
                raise EncounterValidationError('Boundary expiry entry is missing an effect id.')
            self._end_active_effect(work, events, effect_id=entry.effect_instance_id, reason=f'{entry.phase.value}-expiry')
            return events
        if entry.kind == TimingEntryKind.ACTIVE_EFFECT_TRIGGER:
            if entry.effect_instance_id is None or entry.trigger_index is None or entry.trigger_actor_id is None:
                raise EncounterValidationError('Boundary trigger entry is missing required trigger metadata.')
            effect = work.active_effects.get(entry.effect_instance_id)
            if effect is None:
                return []
            if entry.trigger_index >= len(effect.definition.ongoing_triggers):
                raise EncounterValidationError('Boundary trigger entry references a missing ongoing trigger.')
            trigger = effect.definition.ongoing_triggers[entry.trigger_index]
            self._emit(work, events, [ActiveEffectTickedEvent(effect_instance_id=effect.effect_instance_id, actor_id=entry.trigger_actor_id, timing=entry.phase, detail=effect.name)])
            self._resolve_ongoing_trigger(work, events, effect=effect, trigger=trigger, trigger_actor_id=entry.trigger_actor_id)
            return events
        if entry.kind == TimingEntryKind.PERSISTENT_AREA_TICK:
            if entry.effect_instance_id is None or entry.trigger_index is None:
                raise EncounterValidationError('Persistent-area timing entry is missing required metadata.')
            area = work.persistent_areas.get(entry.effect_instance_id)
            if area is None:
                return []
            if entry.trigger_index >= len(area.definition.tick_effects):
                raise EncounterValidationError('Persistent-area timing entry references a missing tick definition.')
            trigger = area.definition.tick_effects[entry.trigger_index]
            trigger_actor_id = entry.trigger_actor_id or entry.actor_id
            trigger_actor = work.actors.get(trigger_actor_id)
            actor_ids = (trigger_actor_id,) if trigger_actor is not None and persistent_area_contains_position(area, trigger_actor.position) else ()
            self._emit(work, events, [PersistentAreaTickedEvent(area_id=area.area_id, timing=entry.phase, actor_ids=actor_ids)])
            for target_actor_id in actor_ids:
                for child in trigger.effects:
                    self._execute_effect(
                        work,
                        events,
                        source_actor_id=area.persistent.source_actor_id,
                        capability=CapabilityDefinition(
                            capability_id=area.persistent.source_capability_id,
                            name=area.definition.name,
                            kind=CapabilityKind.SPELL,
                            source='PERSISTENT',
                            action_cost='none',
                            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE),
                            effect=child,
                        ),
                        effect=child,
                        target_ids=(target_actor_id,),
                        point=area.origin,
                        active_effect_id=area.persistent.source_effect_id,
                        critical_hit=False,
                        parameters={},
                    )
            return events
        raise EncounterValidationError('Unsupported turn-boundary entry kind for the effect executor.')

    def end_active_effect(self, state: EncounterState, *, effect_id: str, reason: str) -> list[object]:
        work = copy.deepcopy(state)
        events: list[object] = []
        self._end_active_effect(work, events, effect_id=effect_id, reason=reason)
        return events

    def _split_parameter_values(self, raw_value: str) -> tuple[str, ...]:
        parts: list[str] = []
        for piece in raw_value.replace(',', '\n').splitlines():
            value = piece.strip()
            if value:
                parts.append(value)
        return tuple(parts)

    def _touch_delivery_proxy_actor(
        self,
        state: EncounterState,
        *,
        caster: RuntimeActorState,
        capability: CapabilityDefinition,
        parameters: Mapping[str, str],
    ) -> RuntimeActorState | None:
        proxy_id = parameters.get('through', '').strip()
        if not proxy_id:
            return None
        spec = capability.targeting
        if spec.selection_kind != TargetSelectionKind.CREATURE:
            raise EncounterValidationError('This spell cannot be delivered through a familiar.')
        if spec.range_ft is None or spec.range_ft > 5:
            raise EncounterValidationError('Only touch-range creature spells can be delivered through a familiar.')
        proxy = state.actors.get(proxy_id)
        if proxy is None:
            raise EncounterValidationError('The chosen delivery actor is not available.')
        if not proxy.is_conscious:
            raise EncounterValidationError('The chosen delivery actor is not conscious.')
        if proxy.summon_owner_actor_id != caster.actor_id:
            raise EncounterValidationError('The chosen delivery actor is not your familiar.')
        familiar_link = next(
            (
                summon
                for summon in state.summoned_creatures.values()
                if summon.linked_actor_id == proxy.actor_id
                and summon.persistent.source_actor_id == caster.actor_id
                and 'familiar' in set(summon.definition.semantic_tags)
            ),
            None,
        )
        if familiar_link is None:
            raise EncounterValidationError('The chosen delivery actor is not a familiar you control.')
        if self.kernel.battlefield_rules.get_distance3d(caster.position, proxy.position) > 100:
            raise EncounterValidationError('The familiar is too far away to share senses and deliver the spell.')
        return proxy

    def _creature_target_ids(self, state: EncounterState, *, actor: RuntimeActorState, capability: CapabilityDefinition, target_id: str | None, parameters: Mapping[str, str]) -> tuple[str, ...]:
        spec = capability.targeting
        target_ids: list[str] = []
        if target_id is not None:
            target_ids.append(target_id)
        for key in ('target', 'targets'):
            raw_value = parameters.get(key, '')
            if raw_value:
                target_ids.extend(self._split_parameter_values(raw_value))
        if not target_ids:
            raise EncounterValidationError('This capability requires a target actor id.')
        unique_target_ids = tuple(dict.fromkeys(target_ids))
        if spec.max_targets is not None and len(unique_target_ids) > spec.max_targets:
            raise EncounterValidationError(f'This capability supports at most {spec.max_targets} target(s).')
        resolved_targets = []
        for candidate_id in unique_target_ids:
            target = self.kernel._require_target(state, candidate_id)
            self._validate_creature_target(state, actor=actor, target=target, capability=capability)
            resolved_targets.append(target.actor_id)
        return tuple(resolved_targets)

    def _resolve_targets(self, state: EncounterState, *, actor: RuntimeActorState, capability: CapabilityDefinition, target_id: str | None, point: GridPosition | None, parameters: Mapping[str, str], origin_actor: RuntimeActorState | None = None) -> tuple[tuple[str, ...], GridPosition | None, list[object]]:
        target_origin = origin_actor or actor
        spec = capability.targeting
        if spec.selection_kind == TargetSelectionKind.SELF:
            return (actor.actor_id,), actor.position, [TargetsResolvedEvent(actor_id=actor.actor_id, capability_id=capability.capability_id, target_ids=(actor.actor_id,))]
        if spec.selection_kind == TargetSelectionKind.CREATURE:
            target_ids = self._creature_target_ids(state, actor=target_origin, capability=capability, target_id=target_id, parameters=parameters)
            return target_ids, None, [TargetsResolvedEvent(actor_id=actor.actor_id, capability_id=capability.capability_id, target_ids=target_ids)]
        if spec.selection_kind == TargetSelectionKind.POINT:
            if point is None:
                raise EncounterValidationError('This capability requires a deterministic point in space.')
            self._validate_point_target(state, actor=target_origin, point=point, spec=spec)
            return (), point, [TargetsResolvedEvent(actor_id=actor.actor_id, capability_id=capability.capability_id, target_ids=())]
        if spec.selection_kind != TargetSelectionKind.AREA or spec.area_shape is None or spec.area_size_ft is None:
            raise EncounterValidationError('Unsupported capability target definition.')
        target_ids, origin = self._resolve_area_targets(state, actor=target_origin, capability=capability, target_id=target_id, point=point, parameters=parameters)
        return target_ids, origin, [AreaResolvedEvent(actor_id=actor.actor_id, capability_id=capability.capability_id, area_shape=spec.area_shape, origin=origin, size_ft=spec.area_size_ft, target_ids=target_ids), TargetsResolvedEvent(actor_id=actor.actor_id, capability_id=capability.capability_id, target_ids=target_ids)]

    def _validate_creature_target(self, state: EncounterState, *, actor: RuntimeActorState, target: RuntimeActorState, capability: CapabilityDefinition) -> None:
        spec = capability.targeting
        if target.is_dead:
            raise EncounterValidationError('The chosen target is already dead.')
        if not self._matches_affinity(actor, target, spec.affinity):
            raise EncounterValidationError('The target does not satisfy the capability target filter.')
        visibility = get_targeting_visibility_legality(actor, target, requires_target_to_be_seen=spec.requires_target_to_be_seen, encounter_state=state)
        if not visibility.legal:
            raise EncounterValidationError(visibility.reason or 'The target cannot currently be seen.')
        if spec.requires_line_of_effect and not self.kernel.battlefield_rules.has_line_of_effect_to_position(state, actor, target.position):
            raise EncounterValidationError('The target is blocked from line of effect.')
        if spec.range_ft is not None and grid_distance_ft(actor.position, target.position) > spec.range_ft:
            raise EncounterValidationError('Target is out of capability range.')
        if spec.creature_type_filter is not None and target.creature_type.lower() != spec.creature_type_filter.lower():
            raise EncounterValidationError('The target does not match the required creature type for this capability.')
        if capability.capability_id == 'mage-armor' and target.worn_armor_item_id is not None:
            raise EncounterValidationError('Mage Armor requires an unarmored willing creature.')
        if capability.kind == CapabilityKind.SPELL:
            validate_hostile_targeting(actor, target, is_damaging=self._effect_is_damaging(capability.effect), is_magical=True)

    def _validate_point_target(self, state: EncounterState, *, actor: RuntimeActorState, point: GridPosition, spec: TargetingSpec) -> None:
        if spec.range_ft is not None and grid_distance_ft(actor.position, point) > spec.range_ft:
            raise EncounterValidationError('The chosen point is out of capability range.')
        if spec.point_must_be_visible and not self.kernel.battlefield_rules.has_line_of_sight_to_position(state, actor, point):
            raise EncounterValidationError('The chosen point cannot be seen from the acting actor.')
        if spec.requires_line_of_effect and not self.kernel.battlefield_rules.has_line_of_effect_to_position(state, actor, point):
            raise EncounterValidationError('The chosen point is blocked from line of effect.')
        if spec.requires_unoccupied_point:
            volume = actor.occupied_volume.__class__(point.x, point.y, point.z, height_ft=actor.occupied_height_ft)
            if not self.kernel.battlefield_rules.is_volume_occupiable(state, volume, actor, ignore_actor_id=actor.actor_id):
                raise EncounterValidationError('The chosen point is occupied or blocked.')

    def _resolve_area_targets(self, state: EncounterState, *, actor: RuntimeActorState, capability: CapabilityDefinition, target_id: str | None, point: GridPosition | None, parameters: Mapping[str, str]) -> tuple[tuple[str, ...], GridPosition]:
        spec = capability.targeting
        if spec.area_origin_mode == AreaOriginMode.SELECTED_POINT:
            if point is None:
                raise EncounterValidationError('This area capability requires a point in space.')
            self._validate_point_target(state, actor=actor, point=point, spec=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=spec.range_ft, requires_line_of_effect=spec.requires_line_of_effect, point_must_be_visible=spec.point_must_be_visible))
            origin = point
        elif spec.area_origin_mode == AreaOriginMode.TARGET:
            creature_targets = self._creature_target_ids(state, actor=actor, capability=CapabilityDefinition(capability_id=capability.capability_id, name=capability.name, kind=capability.kind, source=capability.source, action_cost=capability.action_cost, targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=spec.range_ft, affinity=spec.affinity, requires_target_to_be_seen=spec.requires_target_to_be_seen, requires_line_of_effect=spec.requires_line_of_effect), effect=capability.effect), target_id=target_id, parameters=parameters)
            if len(creature_targets) != 1:
                raise EncounterValidationError('This area capability requires exactly one anchor target.')
            origin = self.kernel._require_target(state, creature_targets[0]).position
        else:
            if spec.area_origin_mode == AreaOriginMode.SOURCE_DIRECTION and point is None:
                raise EncounterValidationError('This directional area capability requires a direction point.')
            origin = actor.position
        target_ids: list[str] = []
        for target in state.actors.values():
            if not self._matches_affinity(actor, target, spec.affinity):
                continue
            visibility = get_targeting_visibility_legality(actor, target, requires_target_to_be_seen=spec.requires_target_to_be_seen, encounter_state=state)
            if not visibility.legal:
                continue
            if spec.area_shape == AreaShape.SPHERE and self.kernel.battlefield_rules.get_distance3d(target.position, origin) <= spec.area_size_ft:
                target_ids.append(target.actor_id)
            elif spec.area_shape == AreaShape.LINE and point is not None and self._within_line(actor.position, point, target.position, spec.area_size_ft):
                target_ids.append(target.actor_id)
            elif spec.area_shape == AreaShape.CONE and point is not None and self._within_cone(actor.position, point, target.position, spec.area_size_ft):
                target_ids.append(target.actor_id)
            elif spec.area_shape == AreaShape.CUBE:
                include = self._within_cube(origin, target.position, spec.area_size_ft)
                if spec.area_origin_mode == AreaOriginMode.SOURCE_DIRECTION and point is not None:
                    include = self._within_directional_cube(actor.position, point, target.position, spec.area_size_ft)
                if include:
                    target_ids.append(target.actor_id)
        return tuple(target_ids), origin

    def _coords(self, pos: GridPosition) -> tuple[float, float, float]:
        return float(pos.x * 5), float(pos.y * 5), float(pos.z)

    def _within_cube(self, origin: GridPosition, target: GridPosition, size_ft: int) -> bool:
        half = size_ft // 2
        return abs((target.x - origin.x) * 5) <= half and abs((target.y - origin.y) * 5) <= half and abs(target.z - origin.z) <= half

    def _within_directional_cube(self, source: GridPosition, point: GridPosition, target: GridPosition, size_ft: int) -> bool:
        cells = max(1, size_ft // 5)
        if abs(point.x - source.x) >= abs(point.y - source.y):
            step = 1 if point.x >= source.x else -1
            xr = range(source.x + (1 if step > 0 else -cells), source.x + (cells + 1 if step > 0 else 0))
            yr = range(source.y - cells // 2, source.y + cells // 2 + 1)
            return target.x in xr and target.y in yr and abs(target.z - source.z) <= size_ft
        step = 1 if point.y >= source.y else -1
        yr = range(source.y + (1 if step > 0 else -cells), source.y + (cells + 1 if step > 0 else 0))
        xr = range(source.x - cells // 2, source.x + cells // 2 + 1)
        return target.y in yr and target.x in xr and abs(target.z - source.z) <= size_ft

    def _within_line(self, source: GridPosition, point: GridPosition, target: GridPosition, length_ft: int) -> bool:
        sx, sy, sz = self._coords(source); px, py, pz = self._coords(point); tx, ty, tz = self._coords(target)
        vx, vy, vz = px - sx, py - sy, pz - sz
        wx, wy, wz = tx - sx, ty - sy, tz - sz
        mag = math.sqrt(vx * vx + vy * vy + vz * vz)
        if mag == 0:
            return False
        ux, uy, uz = vx / mag, vy / mag, vz / mag
        proj = wx * ux + wy * uy + wz * uz
        if proj < 0 or proj > length_ft:
            return False
        perp_sq = max(0.0, (wx * wx + wy * wy + wz * wz) - proj * proj)
        return math.sqrt(perp_sq) <= 2.5

    def _within_cone(self, source: GridPosition, point: GridPosition, target: GridPosition, length_ft: int) -> bool:
        sx, sy, sz = self._coords(source); px, py, pz = self._coords(point); tx, ty, tz = self._coords(target)
        vx, vy, vz = px - sx, py - sy, pz - sz
        wx, wy, wz = tx - sx, ty - sy, tz - sz
        vmag = math.sqrt(vx * vx + vy * vy + vz * vz); wmag = math.sqrt(wx * wx + wy * wy + wz * wz)
        if vmag == 0 or wmag == 0 or wmag > length_ft:
            return False
        return (vx * wx + vy * wy + vz * wz) / (vmag * wmag) >= math.cos(math.radians(45))
    def _execute_effect(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, effect: EffectDefinition, target_ids: tuple[str, ...], point: GridPosition | None, active_effect_id: str | None, critical_hit: bool, parameters: Mapping[str, str]) -> None:
        if isinstance(effect, CompositeEffect):
            for child in effect.effects:
                self._execute_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=child, target_ids=target_ids, point=point, active_effect_id=active_effect_id, critical_hit=critical_hit, parameters=parameters)
            return
        if isinstance(effect, DamageEffectDef):
            for target_id in target_ids:
                self._apply_damage(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=effect, critical_hit=critical_hit)
            return
        if isinstance(effect, ParameterizedDamageEffectDef):
            for target_id in target_ids:
                self._apply_parameterized_damage(state, events, source_actor_id=source_actor_id, target_id=target_id, capability=capability, effect=effect, critical_hit=critical_hit, parameters=parameters, active_effect_id=active_effect_id)
            return
        if isinstance(effect, ParameterizedTargetCountGateEffectDef):
            self._apply_parameterized_target_count_gate(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, parameters=parameters, active_effect_id=active_effect_id)
            return
        if isinstance(effect, MissingHitPointsDamageEffectDef):
            for target_id in target_ids:
                self._apply_missing_hit_points_damage(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=effect)
            return
        if isinstance(effect, HealingEffectDef):
            for target_id in target_ids:
                self._apply_healing(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=effect)
            return
        if isinstance(effect, SpendHitDiceHealingEffectDef):
            self._apply_spend_hit_dice_healing(state, events, source_actor_id=source_actor_id, target_ids=target_ids, effect=effect, parameters=parameters)
            return
        if isinstance(effect, TemporaryHitPointsEffectDef):
            for target_id in target_ids:
                self._apply_temporary_hit_points(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=effect)
            return
        if isinstance(effect, StabilizeEffectDef):
            for target_id in target_ids:
                self._apply_stabilize(state, events, source_actor_id=source_actor_id, target_id=target_id)
            return
        if isinstance(effect, DashEffectDef):
            self._apply_dash_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, use_bonus_action_speed=effect.use_bonus_action_speed)
            return
        if isinstance(effect, CommandWordEffectDef):
            self._apply_command_word(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, DetectionScanEffectDef):
            self._apply_detection_scan(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, AlarmWardEffectDef):
            self._apply_alarm_ward(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, AlarmTriggerEffectDef):
            for target_id in target_ids:
                self._apply_alarm_trigger_notice(state, events, source_actor_id=source_actor_id, target_id=target_id, capability=capability, point=point, effect=effect)
            return
        if isinstance(effect, ForcedReactionMoveEffectDef):
            for target_id in target_ids:
                self._apply_forced_reaction_move(state, events, source_actor_id=source_actor_id, target_id=target_id, capability=capability, effect=effect)
            return
        if isinstance(effect, ConditionEffectDef):
            for target_id in target_ids:
                app = ConditionApplication(
                    condition_type=effect.condition_type,
                    source_label=effect.source_label or capability.name,
                    source_effect_id=active_effect_id,
                    source_actor_id=source_actor_id,
                    charmer_actor_id=(source_actor_id if effect.condition_type == ConditionType.CHARMED else None),
                    fear_source_actor_id=(source_actor_id if effect.condition_type == ConditionType.FRIGHTENED else None),
                )
                self._emit(state, events, [self.kernel._condition_added_event_from_application(target_actor_id=target_id, application=app)])
            return
        if isinstance(effect, ParameterizedConditionEffectDef):
            self._apply_parameterized_condition(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ForcedMovementEffectDef):
            for target_id in target_ids:
                self._apply_forced_movement(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=effect, capability=capability)
            return
        if isinstance(effect, TeleportEffectDef):
            self._apply_teleport(state, events, source_actor_id=source_actor_id, capability=capability, effect=effect, point=point)
            return
        if isinstance(effect, CreateTerrainEffectDef):
            self._create_terrain_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=effect, point=point)
            return
        if isinstance(effect, AttackRollGateEffect):
            if len(target_ids) != 1:
                raise EncounterValidationError('Attack-roll effects require exactly one target.')
            hit, critical = self._apply_attack_gate(state, events, source_actor_id=source_actor_id, target_id=target_ids[0], capability=capability, gate=effect)
            for child in (effect.on_hit if hit else effect.on_miss):
                self._execute_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=child, target_ids=target_ids, point=point, active_effect_id=active_effect_id, critical_hit=critical, parameters=parameters)
            return
        if isinstance(effect, TargetRadiusSaveEffectDef):
            self._apply_target_radius_save(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, point=point, active_effect_id=active_effect_id, parameters=parameters)
            return
        if isinstance(effect, SaveGateEffect):
            if len(effect.on_failure) == 1 and not effect.on_success and not effect.on_partial_success:
                only_failure = effect.on_failure[0]
                if isinstance(only_failure, ParameterizedConditionEffectDef):
                    self._apply_group_parameterized_condition_save_gate(
                        state,
                        events,
                        source_actor_id=source_actor_id,
                        target_ids=target_ids,
                        capability=capability,
                        gate=effect,
                        point=point,
                        condition_effect=only_failure,
                        parameters=parameters,
                    )
                    return
                if isinstance(only_failure, StartActiveEffectDef) and only_failure.split_targets_individually:
                    self._apply_group_start_active_effect_save_gate(
                        state,
                        events,
                        source_actor_id=source_actor_id,
                        target_ids=target_ids,
                        capability=capability,
                        gate=effect,
                        point=point,
                        start_effect=only_failure,
                        parameters=parameters,
                    )
                    return
            for target_id in target_ids:
                self._apply_save_gate(state, events, source_actor_id=source_actor_id, target_id=target_id, capability=capability, gate=effect, point=point, active_effect_id=active_effect_id, parameters=parameters)
            return
        if isinstance(effect, GroupSaveGateEffectDef):
            self._apply_group_save_gate(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, gate=effect, point=point, parameters=parameters)
            return
        if isinstance(effect, CheckGateEffect):
            for target_id in target_ids:
                self._apply_check_gate(state, events, source_actor_id=source_actor_id, target_id=target_id, capability=capability, gate=effect, point=point, active_effect_id=active_effect_id)
            return
        if isinstance(effect, StartActiveEffectDef):
            self._apply_start_active_effect_def(
                state,
                events,
                source_actor_id=source_actor_id,
                capability=capability,
                target_ids=target_ids,
                point=point,
                effect=effect,
            )
            return
        if isinstance(effect, ParameterizedActiveEffectDef):
            self._apply_parameterized_active_effect(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, GrantInventoryItemEffectDef):
            self._apply_grant_inventory_item(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, effect=effect)
            return
        if isinstance(effect, MarkTargetEffectDef):
            self._apply_mark_target_effect(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, SummonCompanionEffectDef):
            self._apply_summon_companion(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ItemInspectionEffectDef):
            self._apply_item_inspection(state, events, source_actor_id=source_actor_id, capability=capability, effect=effect, parameters=parameters)
            return
        if isinstance(effect, CreateOrDestroyWaterEffectDef):
            self._apply_create_or_destroy_water(state, events, source_actor_id=source_actor_id, capability=capability, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, PurifyConsumablesEffectDef):
            self._apply_purify_consumables(state, events, source_actor_id=source_actor_id, capability=capability, point=point)
            return
        if isinstance(effect, ChosenSkillBonusEffectDef):
            self._apply_chosen_skill_bonus(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ChosenAbilityCheckAdvantageEffectDef):
            self._apply_chosen_ability_check_advantage(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ConditionRemovalEffectDef):
            self._apply_condition_removal(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ChosenDamageReductionEffectDef):
            self._apply_chosen_damage_reduction(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ChosenWeaponEnchantmentEffectDef):
            self._apply_chosen_weapon_enchantment(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ParameterizedIllusionEffectDef):
            self._apply_parameterized_illusion(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, HeldConjurationEffectDef):
            self._apply_held_conjuration(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, point=point, effect=effect, parameters=parameters)
            return
        if isinstance(effect, InstantWeaponStrikeEffectDef):
            self._apply_instant_weapon_strike(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, parameters=parameters)
            return
        if isinstance(effect, RecursiveSpellAttackEffectDef):
            self._apply_recursive_spell_attack(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ChainingSpellAttackEffectDef):
            self._apply_chaining_spell_attack(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect, parameters=parameters)
            return
        if isinstance(effect, ConditionalCreatureTypeDamageEffectDef):
            for target_id in target_ids:
                self._apply_conditional_creature_type_damage(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=effect)
            return
        if isinstance(effect, FriendsEffectDef):
            self._apply_friends(state, events, source_actor_id=source_actor_id, capability=capability, target_ids=target_ids, effect=effect)
            return
        raise EncounterValidationError('Unsupported effect definition.')

    def _required_parameter(self, parameters: Mapping[str, str], key: str, *, label: str | None = None) -> str:
        value = parameters.get(key)
        if value is None or not str(value).strip():
            requirement = label or key
            raise EncounterValidationError(f'This capability requires --{key} to specify {requirement}.')
        return str(value).strip()

    def _cantrip_damage_dice_count(self, actor_level: int) -> int:
        if actor_level >= 17:
            return 4
        if actor_level >= 11:
            return 3
        if actor_level >= 5:
            return 2
        return 1

    def _scaled_weapon_damage(self, effect: ChosenWeaponEnchantmentEffectDef, *, actor_level: int) -> tuple[int | None, int | None]:
        if effect.scaled_damage_tiers:
            selected_count = effect.damage_dice_count
            selected_faces = effect.damage_die_faces
            for minimum_level, dice_count, die_faces in sorted(effect.scaled_damage_tiers, key=lambda item: item[0]):
                if actor_level >= minimum_level:
                    selected_count = dice_count
                    selected_faces = die_faces
            return selected_count, selected_faces
        return effect.damage_dice_count, effect.damage_die_faces

    def _apply_chosen_skill_bonus(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: ChosenSkillBonusEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        chosen = self._required_parameter(parameters, effect.skill_parameter_key, label='a skill').casefold()
        allowed = {name.casefold(): name for name in effect.allowed_skill_names}
        if chosen not in allowed:
            allowed_labels = ', '.join(sorted(effect.allowed_skill_names))
            raise EncounterValidationError(f'Invalid skill for this capability. Choose one of: {allowed_labels}.')
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            ability_check_bonus_skill_name=allowed[chosen],
            ability_check_bonus=effect.bonus,
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, definition=definition, point=point)

    def _apply_chosen_ability_check_advantage(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: ChosenAbilityCheckAdvantageEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        metadata: list[tuple[str, str]] = []
        if effect.per_target_ability_parameter_key and len(target_ids) > 1:
            raw_map = parameters.get(effect.per_target_ability_parameter_key, '').strip()
            if not raw_map:
                raise EncounterValidationError(
                    f'This capability requires --{effect.per_target_ability_parameter_key} actor-id:ability mappings for multiple targets.'
                )
            chosen_map: dict[str, Ability] = {}
            for piece in self._split_parameter_values(raw_map):
                actor_part, separator, ability_part = piece.partition(':')
                if not separator:
                    raise EncounterValidationError(
                        f'Invalid --{effect.per_target_ability_parameter_key} entry {piece!r}; use actor-id:ability.'
                    )
                actor_key = actor_part.strip()
                if actor_key not in target_ids:
                    raise EncounterValidationError(
                        f'Invalid --{effect.per_target_ability_parameter_key} target {actor_key!r} for this capability.'
                    )
                chosen_ability = self._parse_ability_parameter(ability_part.strip())
                if effect.allowed_abilities and chosen_ability not in effect.allowed_abilities:
                    allowed_labels = ', '.join(ability.value for ability in effect.allowed_abilities)
                    raise EncounterValidationError(f'Invalid ability for this capability. Choose one of: {allowed_labels}.')
                chosen_map[actor_key] = chosen_ability
            missing_targets = [target_id for target_id in target_ids if target_id not in chosen_map]
            if missing_targets:
                raise EncounterValidationError(
                    f'--{effect.per_target_ability_parameter_key} is missing choices for: {", ".join(missing_targets)}.'
                )
            metadata = [(f'ability-advantage:{target_id}', ability.value) for target_id, ability in chosen_map.items()]
            definition = ActiveEffectDefinition(
                name=effect.name,
                duration=effect.duration,
                concentration=effect.concentration,
            )
            self._start_active_effect(
                state,
                events,
                source_actor_id=source_actor_id,
                target_ids=target_ids,
                capability=capability,
                definition=definition,
                point=point,
                metadata=tuple(metadata),
            )
            return
        chosen = self._required_parameter(parameters, effect.ability_parameter_key, label='an ability')
        chosen_ability = self._parse_ability_parameter(chosen)
        if effect.allowed_abilities and chosen_ability not in effect.allowed_abilities:
            allowed_labels = ', '.join(ability.value for ability in effect.allowed_abilities)
            raise EncounterValidationError(f'Invalid ability for this capability. Choose one of: {allowed_labels}.')
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            ability_check_advantage_abilities=(chosen_ability,),
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, definition=definition, point=point)

    def _apply_condition_removal(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        effect: ConditionRemovalEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        requested = parameters.get(effect.condition_parameter_key, '').strip().casefold()
        for target_id in target_ids:
            target = self.kernel._require_target(state, target_id)
            allowed = effect.allowed_condition_types or (ConditionType.BLINDED, ConditionType.DEAFENED, ConditionType.PARALYZED, ConditionType.POISONED)
            chosen_condition: ConditionType | None = None
            if requested:
                try:
                    requested_condition = ConditionType(requested)
                except ValueError as exc:
                    allowed_labels = ', '.join(condition.value for condition in allowed)
                    raise EncounterValidationError(f'Invalid condition for this capability. Choose one of: {allowed_labels}.') from exc
                if requested_condition not in allowed:
                    allowed_labels = ', '.join(condition.value for condition in allowed)
                    raise EncounterValidationError(f'Invalid condition for this capability. Choose one of: {allowed_labels}.')
                chosen_condition = requested_condition
            else:
                for candidate in allowed:
                    if any(instance.condition_type == candidate and not instance.suppressed for instance in target.condition_instances):
                        chosen_condition = candidate
                        break
            if chosen_condition is None:
                allowed_labels = ', '.join(condition.value for condition in allowed)
                raise EncounterValidationError(f'No removable condition is currently affecting the target. Choose one of: {allowed_labels}.')
            removal = remove_condition(target, condition_type=chosen_condition)
            if removal.condition_instances == target.condition_instances:
                raise EncounterValidationError(f'The target is not currently affected by the {chosen_condition.value} condition.')
            self._emit(state, events, [ConditionRemovedEvent(actor_id=target.actor_id, condition_type=chosen_condition)])
            for added_instance in removal.added_instances:
                self._emit(state, events, [ConditionAddedEvent(actor_id=target.actor_id, instance=added_instance)])

    def _illusion_from_template(self, template: IllusionTemplateId, *, label: str, description: str) -> IllusionDefinition:
        semantic = tuple(tag for tag in (label.casefold().replace(' ', '-'), 'minor-illusion') if tag)
        if template == IllusionTemplateId.MINOR_SOUND_SOURCE:
            return IllusionDefinition(
                template_id=template,
                subtype=IllusionSubtype.SMALL_SENSORY,
                modality=IllusionModality.AUDITORY,
                display_name=label,
                display_description=description,
                semantic_tags=semantic + ('sound',),
                reveal_policies=(IllusionRevealPolicy.ON_STUDY_SUCCESS,),
            )
        apparent_blocker = template in {IllusionTemplateId.MINOR_VISUAL_BARRIER, IllusionTemplateId.MINOR_VISUAL_DOOR}
        apparent_door = template == IllusionTemplateId.MINOR_VISUAL_DOOR
        category = 'sign' if template == IllusionTemplateId.MINOR_VISUAL_SIGN_OR_SIGIL else 'object'
        return IllusionDefinition(
            template_id=template,
            subtype=IllusionSubtype.SMALL_STATIC_VISUAL,
            modality=IllusionModality.VISUAL,
            display_name=label,
            display_description=description,
            semantic_tags=semantic,
            apparent_properties=IllusionApparentProperties(
                apparent_blocker=apparent_blocker,
                apparent_door=apparent_door,
                apparent_object_category=category,
            ),
            actual_properties=IllusionActualProperties(),
            reveal_policies=(IllusionRevealPolicy.ON_STUDY_SUCCESS, IllusionRevealPolicy.ON_PHYSICAL_INTERACTION),
        )

    def _apply_parameterized_illusion(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: ParameterizedIllusionEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        template_value = self._required_parameter(parameters, effect.template_parameter_key, label='an illusion template')
        try:
            template = IllusionTemplateId(template_value)
        except ValueError as exc:
            allowed = ', '.join(template_id.value for template_id in effect.allowed_templates)
            raise EncounterValidationError(f'Invalid illusion template. Choose one of: {allowed}.') from exc
        if template not in effect.allowed_templates:
            allowed = ', '.join(template_id.value for template_id in effect.allowed_templates)
            raise EncounterValidationError(f'Invalid illusion template. Choose one of: {allowed}.')
        label = parameters.get(effect.label_parameter_key, '').strip() or ('Sound' if template == IllusionTemplateId.MINOR_SOUND_SOURCE else 'Minor Illusion')
        description = parameters.get(effect.description_parameter_key, '').strip() or label
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            replace_existing_same_name_from_source=True,
            illusions=(self._illusion_from_template(template, label=label, description=description),),
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, definition=definition, point=point)

    def _apply_parameterized_active_effect(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: ParameterizedActiveEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        metadata: list[tuple[str, str]] = list(effect.extra_metadata)
        for key in effect.required_metadata_parameter_keys:
            metadata.append((key, self._required_parameter(parameters, key, label=key)))
        for key in effect.metadata_parameter_keys:
            value = parameters.get(key)
            if value is not None and str(value).strip():
                metadata.append((key, str(value).strip()))
        resolved_active_effect = effect.active_effect
        if effect.slot_level_parameter_key is not None and effect.bonus_max_hit_points_per_slot_level:
            slot_level = self._slot_level_from_parameters(
                state,
                parameters,
                active_effect_id=None,
                parameter_key=effect.slot_level_parameter_key,
                default=effect.base_slot_level,
            )
            slot_steps = max(0, slot_level - effect.base_slot_level)
            resolved_active_effect = replace(
                effect.active_effect,
                max_hit_points_bonus=(
                    effect.active_effect.max_hit_points_bonus
                    + slot_steps * effect.bonus_max_hit_points_per_slot_level
                ),
            )
        self._start_active_effect(
            state,
            events,
            source_actor_id=source_actor_id,
            target_ids=target_ids,
            capability=capability,
            definition=resolved_active_effect,
            point=point,
            metadata=tuple(metadata),
        )

    def _apply_grant_inventory_item(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_ids: tuple[str, ...], capability: CapabilityDefinition, effect: GrantInventoryItemEffectDef) -> None:
        recipients = target_ids or (source_actor_id,)
        for target_id in recipients:
            self._emit(state, events, [ItemGrantedEvent(actor_id=target_id, item_id=effect.item_id, quantity=effect.quantity, reason=capability.name)])

    def _skills_for_ability(self, ability: Ability) -> tuple[str, ...]:
        mapping = {
            Ability.STR: ('Athletics',),
            Ability.DEX: ('Acrobatics', 'Sleight of Hand', 'Stealth'),
            Ability.CON: (),
            Ability.INT: ('Arcana', 'History', 'Investigation', 'Nature', 'Religion'),
            Ability.WIS: ('Animal Handling', 'Insight', 'Medicine', 'Perception', 'Survival'),
            Ability.CHA: ('Deception', 'Intimidation', 'Performance', 'Persuasion'),
        }
        return mapping.get(ability, ())

    def _parse_ability_parameter(self, raw_value: str) -> Ability:
        normalized = raw_value.strip().casefold()
        aliases = {
            'str': Ability.STR,
            'strength': Ability.STR,
            'dex': Ability.DEX,
            'dexterity': Ability.DEX,
            'con': Ability.CON,
            'constitution': Ability.CON,
            'int': Ability.INT,
            'intelligence': Ability.INT,
            'wis': Ability.WIS,
            'wisdom': Ability.WIS,
            'cha': Ability.CHA,
            'charisma': Ability.CHA,
        }
        ability = aliases.get(normalized)
        if ability is None:
            raise EncounterValidationError(f'Invalid ability value: {raw_value}.')
        return ability

    def _apply_mark_target_effect(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], point: GridPosition | None, effect: MarkTargetEffectDef, parameters: Mapping[str, str]) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('Marked-target effects require exactly one target.')
        mode = parameters.get('mode', '').strip().casefold()
        existing = self._existing_source_effect(state, source_actor_id=source_actor_id, name=effect.name)
        if mode == 'transfer':
            if existing is None:
                raise EncounterValidationError(f'{effect.name} cannot be transferred because it is not currently active.')
            existing_metadata = dict(existing.metadata)
            prior_target_id = existing_metadata.get('marked-target-id')
            if prior_target_id is None or prior_target_id not in state.actors:
                raise EncounterValidationError(f'{effect.name} cannot be transferred because its current marked target is missing.')
            if state.actors[prior_target_id].current_hit_points > 0:
                raise EncounterValidationError(f'{effect.name} can only be transferred after the current marked target drops to 0 HP.')
        metadata = [('marked-target-id', target_ids[0])]
        chosen_ability: Ability | None = None
        if effect.ability_parameter_key is not None:
            if mode == 'transfer' and existing is not None:
                existing_metadata = dict(existing.metadata)
                carried_value = existing_metadata.get('marked-ability')
                if carried_value is not None:
                    chosen_ability = Ability(carried_value)
                else:
                    raise EncounterValidationError(f'{effect.name} cannot be transferred because the original chosen ability is missing.')
            else:
                chosen_value = self._required_parameter(parameters, effect.ability_parameter_key, label='an ability')
                try:
                    chosen_ability = self._parse_ability_parameter(chosen_value)
                except EncounterValidationError as exc:
                    allowed = ', '.join(ability.value for ability in effect.allowed_abilities)
                    raise EncounterValidationError(f'Invalid ability for this spell. Choose one of: {allowed}.') from exc
                if effect.allowed_abilities and chosen_ability not in effect.allowed_abilities:
                    allowed = ', '.join(ability.value for ability in effect.allowed_abilities)
                    raise EncounterValidationError(f'Invalid ability for this spell. Choose one of: {allowed}.')
            metadata.append(('marked-ability', chosen_ability.value))
        self._start_active_effect(
            state,
            events,
            source_actor_id=source_actor_id,
            target_ids=(source_actor_id,),
            capability=capability,
            definition=ActiveEffectDefinition(
                name=effect.name,
                duration=effect.duration,
                concentration=effect.concentration,
                replace_existing_same_name_from_source=effect.replace_existing_same_name_from_source,
                ability_check_disadvantage_abilities=((chosen_ability,) if chosen_ability is not None else ()),
                marked_target_bonus_damage=effect.bonus_damage,
                marked_target_skill_advantage_names=effect.track_skill_names,
            ),
            point=point,
            metadata=tuple(metadata),
        )

    def _apply_summon_companion(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], point: GridPosition | None, effect: SummonCompanionEffectDef, parameters: Mapping[str, str]) -> None:
        raw_form = parameters.get(effect.form_parameter_key, '').strip()
        if raw_form:
            form = raw_form
        elif effect.summon_kind == 'familiar':
            raise EncounterValidationError('This spell requires a summoned form.')
        else:
            form = effect.summon_kind
        metadata: list[tuple[str, str]] = [(effect.form_parameter_key, form)]
        for key in ('type', 'description', 'material'):
            value = parameters.get(key, '').strip()
            if value:
                metadata.append((key, value))
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            replace_existing_same_name_from_source=True,
            summoned_creatures=(SummonedCreatureDefinition(summon_name=form, statblock_reference=form, semantic_tags=(effect.summon_kind, slugify(form))),),
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(source_actor_id,), capability=capability, definition=definition, point=point, metadata=tuple(metadata))

    def _apply_item_inspection(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, effect: ItemInspectionEffectDef, parameters: Mapping[str, str]) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        item_value = self._required_parameter(parameters, effect.item_parameter_key, label='an item')
        requested = slugify(item_value)
        item = None
        for item_id, quantity in actor.carried_item_counts.items():
            if quantity <= 0:
                continue
            candidate = self.kernel.item_catalog.get(item_id)
            if candidate is None:
                continue
            if requested in {slugify(candidate.record_id), slugify(candidate.name)}:
                item = candidate
                break
        if item is None:
            raise EncounterValidationError('The acting actor is not carrying that item.')
        detail_lines = [
            f'Name: {item.name}',
            f'Source: {item.source}',
            f"Magical: {'yes' if item.is_magical else 'no'}",
            f"Tags: {', '.join(item.tags) if item.tags else 'none'}",
        ]
        if item.weapon_category is not None:
            detail_lines.append(f'Weapon: {item.weapon_category}; {item.weapon_damage_dice_count}d{item.weapon_damage_die_faces} {item.weapon_damage_type}')
        if item.armor_category is not None:
            detail_lines.append(f'Armor: {item.armor_category.value}; AC {item.armor_base_ac}')
        if effect.mark_identified and item.is_magical:
            self._emit(state, events, [ItemIdentifiedEvent(actor_id=source_actor_id, item_id=item.record_id, reason=capability.name)])
        self._emit_information_scan(state, events, source_actor_id=source_actor_id, capability=capability, title=effect.name, detail_lines=tuple(detail_lines), kind=InformationPayloadKind.DIVINATION)

    def _apply_create_or_destroy_water(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, point: GridPosition | None, effect: CreateOrDestroyWaterEffectDef, parameters: Mapping[str, str]) -> None:
        mode = parameters.get(effect.mode_parameter_key, '').strip().casefold() or 'create'
        if mode not in {'create', 'destroy'}:
            raise EncounterValidationError('Create or Destroy Water requires --mode create or --mode destroy.')
        container = parameters.get(effect.container_parameter_key, '').strip()
        if container:
            action = 'create up to 10 gallons of clean water in' if mode == 'create' else 'destroy up to 10 gallons of water in'
            self._emit_information_scan(
                state,
                events,
                source_actor_id=source_actor_id,
                capability=capability,
                title='Create or Destroy Water',
                detail_lines=(f'{action} the open container {container}.',),
                kind=InformationPayloadKind.DIVINATION,
            )
            return
        if point is None:
            raise EncounterValidationError('Create or Destroy Water requires a point unless --container is used.')
        if mode == 'create':
            self._emit_information_scan(
                state,
                events,
                source_actor_id=source_actor_id,
                capability=capability,
                title='Create or Destroy Water',
                detail_lines=(
                    'Rain falls in a 30-foot cube centered on the chosen point.',
                    'Exposed flames in the area are extinguished.',
                ),
                kind=InformationPayloadKind.DIVINATION,
            )
            return
        cleared_fog = False
        for active in tuple(state.active_effects.values()):
            if active.name != 'Fog Cloud':
                continue
            overlapping = False
            for area in state.persistent_areas.values():
                if area.persistent.source_effect_id != active.effect_instance_id:
                    continue
                if persistent_area_contains_position(area, point):
                    overlapping = True
                    break
            if not overlapping:
                continue
            cleared_fog = True
            for follow_up in self.end_active_effect(state, effect_id=active.effect_instance_id, reason='create-or-destroy-water-destroy'):
                events.append(follow_up)
        detail_lines = (
            'Destroyed water or cleared fog in a 30-foot cube centered on the chosen point.',
            'Fog in the chosen area was cleared.' if cleared_fog else 'No qualifying fog effect was present in the chosen area.',
        )
        self._emit_information_scan(state, events, source_actor_id=source_actor_id, capability=capability, title='Create or Destroy Water', detail_lines=detail_lines, kind=InformationPayloadKind.DIVINATION)

    def _apply_purify_consumables(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, point: GridPosition | None) -> None:
        origin = point or self.kernel._require_actor(state, source_actor_id).position
        lines: list[str] = []
        purified_by_actor: dict[str, list[str]] = {}
        poison_tags = {'poison', 'poisoned', 'rotted', 'rotten'}
        for actor in state.actors.values():
            if self.kernel.battlefield_rules.get_distance3d(actor.position, origin) > 5:
                continue
            replacements: list[tuple[str, str, int]] = []
            for item_id, quantity in tuple(actor.carried_item_counts.items()):
                if quantity <= 0:
                    continue
                item = self.kernel.item_catalog.get(item_id)
                if item is None or item.is_magical:
                    continue
                tags = {tag.casefold() for tag in item.tags}
                if not ({'food', 'drink'} & tags):
                    continue
                if not (poison_tags & tags):
                    continue
                purified_item_id = f'purified-{item.record_id}'
                if purified_item_id not in self.kernel.item_catalog:
                    clean_tags = tuple(tag for tag in item.tags if tag.casefold() not in poison_tags)
                    self.kernel.item_catalog[purified_item_id] = replace(item, record_id=purified_item_id, tags=clean_tags)
                replacements.append((item_id, purified_item_id, quantity))
                lines.append(f'{actor.name}: purified {item.name} x{quantity}.')
                purified_by_actor.setdefault(actor.actor_id, []).append(purified_item_id)
            for old_item_id, new_item_id, quantity in replacements:
                self._emit(state, events, [InventoryItemReplacedEvent(actor_id=actor.actor_id, old_item_id=old_item_id, new_item_id=new_item_id, quantity=quantity, reason=capability.name)])
        for actor_id, item_ids in purified_by_actor.items():
            self._emit(state, events, [ConsumablesPurifiedEvent(actor_id=actor_id, item_ids=tuple(dict.fromkeys(item_ids)), reason=capability.name)])
        if not lines:
            lines = ['No nonmagical poisoned or rotten food or drink was found in range.']
        self._emit_information_scan(state, events, source_actor_id=source_actor_id, capability=capability, title='Purify Food and Drink', detail_lines=tuple(lines), kind=InformationPayloadKind.DIVINATION)

    def _apply_target_radius_save(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], effect: TargetRadiusSaveEffectDef, point: GridPosition | None, active_effect_id: str | None, parameters: Mapping[str, str]) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('Target-radius effects require exactly one primary target.')
        primary = self.kernel._require_target(state, target_ids[0])
        actor_ids = []
        for actor in state.actors.values():
            if not effect.include_primary_target and actor.actor_id == primary.actor_id:
                continue
            if self.kernel.battlefield_rules.get_distance3d(actor.position, primary.position) <= effect.radius_ft:
                actor_ids.append(actor.actor_id)
        gate = SaveGateEffect(ability=effect.ability, dc_source=effect.dc_source, flat_dc=effect.flat_dc, on_success=effect.on_success, on_failure=effect.on_failure)
        for actor_id in tuple(dict.fromkeys(actor_ids)):
            self._apply_save_gate(state, events, source_actor_id=source_actor_id, target_id=actor_id, capability=capability, gate=gate, point=primary.position, active_effect_id=active_effect_id, parameters=parameters)

    def _existing_source_effect(self, state: EncounterState, *, source_actor_id: str, name: str) -> ActiveEffectState | None:
        matches = [
            effect
            for effect in state.active_effects.values()
            if effect.source_actor_id == source_actor_id and effect.name == name
        ]
        return matches[-1] if matches else None

    def _select_item_for_effect(
        self,
        actor: RuntimeActorState,
        *,
        parameter_key: str,
        parameters: Mapping[str, str],
        allowed_item_ids: tuple[str, ...] = (),
        allowed_name_fragments: tuple[str, ...] = (),
        require_weapon: bool = True,
        require_melee: bool = False,
        require_held: bool = True,
    ):
        item_catalog = self.kernel.item_catalog
        candidates = []
        for item_id, quantity in actor.carried_item_counts.items():
            if quantity <= 0:
                continue
            item = item_catalog.get(item_id)
            if item is None:
                continue
            if require_weapon and not item_is_weapon(item):
                continue
            if require_melee and item.weapon_kind != 'melee':
                continue
            if require_held and not is_item_held(actor, item_id, item_catalog):
                continue
            if allowed_item_ids and item.record_id not in allowed_item_ids:
                continue
            if allowed_name_fragments:
                label = f'{item.record_id} {item.name}'.casefold()
                if not any(fragment.casefold() in label for fragment in allowed_name_fragments):
                    continue
            candidates.append(item)
        requested = parameters.get(parameter_key, '').strip()
        if requested:
            requested_key = requested.casefold()
            for item in candidates:
                if item.record_id.casefold() == requested_key or item.name.casefold() == requested_key:
                    return item
            raise EncounterValidationError(f'No legal item matched --{parameter_key} {requested}.')
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise EncounterValidationError(f'No legal item is available for --{parameter_key}.')
        labels = ', '.join(sorted(item.record_id for item in candidates))
        raise EncounterValidationError(f'This spell requires --{parameter_key} because multiple legal items are available: {labels}.')

    def _parameterized_damage_type(self, parameters: Mapping[str, str], *, parameter_key: str | None, allowed_damage_types: tuple[str, ...], default: str) -> str:
        if parameter_key is None:
            return default
        chosen = parameters.get(parameter_key, '').strip().casefold()
        if not chosen:
            return default
        if chosen in {'weapon', 'normal'}:
            return default
        allowed = {value.casefold(): value for value in allowed_damage_types}
        if chosen not in allowed:
            labels = ', '.join(allowed_damage_types)
            raise EncounterValidationError(f'Invalid damage type. Choose one of: {labels}.')
        if allowed[chosen].casefold() == 'weapon':
            return default
        return allowed[chosen]

    def _slot_level_from_parameters(self, state: EncounterState, parameters: Mapping[str, str], *, active_effect_id: str | None, parameter_key: str = 'slot-level', default: int = 2) -> int:
        raw_value = parameters.get(parameter_key, '').strip()
        if not raw_value and active_effect_id is not None:
            active_effect = state.active_effects.get(active_effect_id)
            if active_effect is not None:
                for key, value in active_effect.metadata:
                    if key.casefold() == parameter_key.casefold():
                        raw_value = value.strip()
                        break
        if not raw_value:
            return default
        try:
            slot_level = int(raw_value)
        except ValueError as exc:
            raise EncounterValidationError(f'{parameter_key} must be an integer.') from exc
        if slot_level < 1:
            raise EncounterValidationError(f'{parameter_key} must be at least 1.')
        return slot_level

    def _apply_start_active_effect_def(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: StartActiveEffectDef,
    ) -> None:
        if not effect.split_targets_individually or len(target_ids) <= 1:
            self._start_active_effect(
                state,
                events,
                source_actor_id=source_actor_id,
                target_ids=target_ids,
                capability=capability,
                definition=effect.active_effect,
                point=point,
            )
            return
        child_definition = replace(
            effect.active_effect,
            concentration=False,
            replace_existing_same_name_from_source=False,
        )
        if effect.active_effect.concentration:
            anchor_name = effect.concentration_anchor_name or f"{effect.active_effect.name} (anchor)"
            child_definition = replace(child_definition, end_when_source_effect_name_missing=anchor_name)
            anchor_definition = ActiveEffectDefinition(
                name=anchor_name,
                duration=replace(effect.active_effect.duration, anchor=DurationAnchor.SOURCE),
                concentration=True,
                replace_existing_same_name_from_source=True,
            )
            self._start_active_effect(
                state,
                events,
                source_actor_id=source_actor_id,
                target_ids=(),
                capability=capability,
                definition=anchor_definition,
                point=point,
            )
        for target_id in target_ids:
            self._start_active_effect(
                state,
                events,
                source_actor_id=source_actor_id,
                target_ids=(target_id,),
                capability=capability,
                definition=child_definition,
                point=point,
            )

    def _apply_parameterized_condition(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], effect: ParameterizedConditionEffectDef, parameters: Mapping[str, str]) -> None:
        chosen = self._required_parameter(parameters, effect.condition_parameter_key, label='a condition').strip().casefold()
        condition_aliases = {
            'blind': ConditionType.BLINDED,
            'blindness': ConditionType.BLINDED,
            'blinded': ConditionType.BLINDED,
            'deaf': ConditionType.DEAFENED,
            'deafness': ConditionType.DEAFENED,
            'deafened': ConditionType.DEAFENED,
        }
        if chosen in condition_aliases:
            condition_type = condition_aliases[chosen]
        else:
            allowed = {value.value.casefold(): value for value in effect.allowed_condition_types}
            if chosen not in allowed:
                labels = ', '.join(condition.value for condition in effect.allowed_condition_types)
                raise EncounterValidationError(f'Invalid condition. Choose one of: {labels}.')
            condition_type = allowed[chosen]
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            replace_existing_same_name_from_source=effect.replace_existing_same_name_from_source,
            on_start=(ConditionEffectDef(condition_type=condition_type, source_label=(effect.source_label or effect.name)),),
            ongoing_triggers=effect.ongoing_triggers,
        )
        if effect.split_targets_individually and len(target_ids) > 1:
            child_definition = replace(
                definition,
                concentration=False,
                replace_existing_same_name_from_source=False,
            )
            if effect.concentration:
                anchor_name = effect.concentration_anchor_name or f"{effect.name} (anchor)"
                child_definition = replace(child_definition, end_when_source_effect_name_missing=anchor_name)
                anchor_definition = ActiveEffectDefinition(
                    name=anchor_name,
                    duration=replace(effect.duration, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    replace_existing_same_name_from_source=True,
                )
                self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(), capability=capability, definition=anchor_definition, point=None)
            for target_id in target_ids:
                self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(target_id,), capability=capability, definition=child_definition, point=None)
            return
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, definition=definition, point=None)

    def _apply_parameterized_damage(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, capability: CapabilityDefinition, effect: ParameterizedDamageEffectDef, critical_hit: bool, parameters: Mapping[str, str], active_effect_id: str | None) -> None:
        slot_level = self._slot_level_from_parameters(state, parameters, active_effect_id=active_effect_id, parameter_key=effect.slot_level_parameter_key, default=effect.base_slot_level)
        slot_steps = max(0, slot_level - effect.base_slot_level)
        damage_effect = DamageEffectDef(
            dice_count=effect.base_dice_count + slot_steps * effect.bonus_dice_per_slot_level,
            die_faces=effect.die_faces + slot_steps * effect.bonus_die_faces_per_slot_level,
            bonus=effect.bonus + slot_steps * effect.bonus_per_slot_level,
            damage_type=effect.damage_type,
            damage_divisor=effect.damage_divisor,
            double_dice_on_critical_hit=effect.double_dice_on_critical_hit,
        )
        self._apply_damage(state, events, source_actor_id=source_actor_id, target_id=target_id, effect=damage_effect, critical_hit=critical_hit)

    def _apply_parameterized_target_count_gate(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], effect: ParameterizedTargetCountGateEffectDef, parameters: Mapping[str, str], active_effect_id: str | None) -> None:
        slot_level = self._slot_level_from_parameters(state, parameters, active_effect_id=active_effect_id, parameter_key=effect.slot_level_parameter_key, default=effect.base_slot_level)
        allowed_targets = effect.base_target_count + max(0, slot_level - effect.base_slot_level) * effect.targets_per_extra_slot_level
        if len(target_ids) > allowed_targets:
            raise EncounterValidationError(f'{capability.name} supports at most {allowed_targets} target(s) at slot level {slot_level}.')

    def _attack_profile_for_temporary_weapon_strike(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        target_id: str,
        item,
        attack_ability: Ability,
        damage_ability: Ability,
        damage_type_override: str | None,
    ) -> AttackProfile:
        target = self.kernel._require_target(state, target_id)
        distance_ft = self.kernel.battlefield_rules.get_distance3d(actor.position, target.position)
        candidates = [
            profile
            for profile in item_attack_profiles(actor, item, active_effects=state.active_effects)
            if profile.source_item_id == item.record_id and (
                (profile.attack_kind == AttackKind.MELEE and profile.reach_ft is not None and distance_ft <= profile.reach_ft)
                or (profile.attack_kind == AttackKind.RANGED and profile.range_ft is not None and distance_ft <= (profile.long_range_ft or profile.range_ft))
            )
        ]
        if not candidates:
            raise EncounterValidationError('The chosen weapon cannot currently reach that target.')
        candidates.sort(key=lambda profile: (0 if profile.attack_kind == AttackKind.MELEE and distance_ft <= 5 else 1, profile.required_hand_count, -(profile.damage_die_faces or 0), -(profile.damage_dice_count or 0), profile.attack_id))
        base = candidates[0]
        proficiency_bonus = actor.proficiency_bonus if actor_is_proficient_with_weapon(actor, item) else 0
        return AttackProfile(
            attack_id=base.attack_id,
            name=base.name,
            attack_kind=base.attack_kind,
            to_hit_bonus=actor.ability_modifiers.get(attack_ability, 0) + proficiency_bonus,
            reach_ft=base.reach_ft,
            range_ft=base.range_ft,
            long_range_ft=base.long_range_ft,
            damage_dice_count=base.damage_dice_count,
            damage_die_faces=base.damage_die_faces,
            damage_bonus=actor.ability_modifiers.get(damage_ability, 0),
            damage_type=(damage_type_override or base.damage_type),
            source_item_id=base.source_item_id,
            attack_usage_kind=base.attack_usage_kind,
            ammunition_item_id=base.ammunition_item_id,
            required_hand_count=base.required_hand_count,
            loading=base.loading,
        )

    def _apply_attack_profile_gate(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        target_id: str,
        capability: CapabilityDefinition,
        attack: AttackProfile,
        magical: bool,
        damaging: bool,
    ) -> tuple[bool, bool]:
        actor = self.kernel._require_actor(state, source_actor_id)
        target = self.kernel._require_target(state, target_id)
        if damaging:
            validate_hostile_targeting(actor, target, is_damaging=True, is_magical=magical)
        legality = self.kernel.battlefield_rules.attack_legality(state, actor, target, attack)
        if not legality.has_line_of_sight:
            raise EncounterValidationError('The target cannot currently be seen by the acting actor.')
        if not legality.has_line_of_effect:
            raise EncounterValidationError('The target is blocked from line of effect.')
        modifiers = self.kernel._attack_modifier_state(state, actor, target, distance_ft=legality.distance_ft, long_range_disadvantage=legality.long_range_disadvantage)
        req = D20TestRequest(
            request_id=f'capability-attack:{capability.capability_id}:{source_actor_id}:{target_id}:{state.random_counter}',
            test_type=D20TestType.ATTACK,
            actor_id=source_actor_id,
            flat_modifier=attack.to_hit_bonus + modifiers['modifier'],
            roll_mode=merge_roll_mode(advantage=(modifiers['advantage'] or self._spell_attack_roll_advantage(state, actor_id=source_actor_id)), disadvantage=modifiers['disadvantage']),
            dc=target.effective_armor_class + legality.armor_class_bonus,
        )
        self._emit(state, events, list(modifiers.get('effect_events', ())) + [AttackRollRequestedEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target_id)])
        res = self.kernel.d20_engine.resolve(req, random_counter=state.random_counter)
        self._emit(state, events, [
            D20TestRolledEvent(actor_id=source_actor_id, result=res.result, random_counter_used=res.random_counter_used),
            AttackRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_id, attack_rolls=res.result.rolls, attack_total=res.result.total, random_counter_used=res.random_counter_used),
            *self.kernel._consume_next_incoming_attack_roll_effects(tuple(modifiers.get('consumed_incoming_attack_advantage_effect_ids', ()))),
        ])
        hit = self.kernel._attack_hits(res.result.total, target.effective_armor_class + legality.armor_class_bonus, res.result.selected_roll)
        self._emit(state, events, [CapabilityHitEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target_id), AttackHitEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_id)] if hit else [CapabilityMissedEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target_id), AttackMissedEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_id)])
        return hit, res.result.critical_success

    def _apply_chosen_damage_reduction(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: ChosenDamageReductionEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        chosen = self._required_parameter(parameters, effect.damage_type_parameter_key, label='a damage type').casefold()
        allowed = {value.casefold(): value for value in effect.allowed_damage_types}
        if chosen not in allowed:
            labels = ', '.join(effect.allowed_damage_types)
            raise EncounterValidationError(f'Invalid damage type for this capability. Choose one of: {labels}.')
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            damage_reduction_damage_types=(allowed[chosen],),
            damage_reduction_once_per_turn=effect.reduction,
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, definition=definition, point=point)

    def _apply_chosen_weapon_enchantment(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: ChosenWeaponEnchantmentEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        item_owner = actor
        if effect.select_item_from_target_actor:
            if len(target_ids) != 1:
                raise EncounterValidationError('This spell requires exactly one creature target when selecting a touched weapon.')
            item_owner = self.kernel._require_actor(state, target_ids[0])
        item = self._select_item_for_effect(
            item_owner,
            parameter_key=effect.item_parameter_key,
            parameters=parameters,
            allowed_item_ids=effect.allowed_item_ids,
            allowed_name_fragments=effect.allowed_name_fragments,
            require_weapon=effect.requires_weapon,
            require_melee=effect.requires_melee,
            require_held=effect.requires_held,
        )
        if item.is_magical:
            raise EncounterValidationError('Magic Weapon requires a nonmagical weapon.')
        damage_type = self._parameterized_damage_type(
            parameters,
            parameter_key=effect.damage_type_parameter_key,
            allowed_damage_types=effect.allowed_damage_types,
            default=(item.weapon_damage_type or 'bludgeoning'),
        )
        spellcasting_ability = effect.attack_ability or actor.spellcasting_ability
        damage_ability = effect.damage_ability or spellcasting_ability
        if (effect.attack_ability is not None or effect.damage_ability is not None) and (spellcasting_ability is None or damage_ability is None):
            raise EncounterValidationError('The acting actor lacks a spellcasting ability for this spell.')
        damage_dice_count, damage_die_faces = self._scaled_weapon_damage(effect, actor_level=actor.level)
        enchantment_bonus = effect.enchanted_attack_bonus
        if effect.scaled_enchanted_bonus_tiers:
            slot_level = self._slot_level_from_parameters(
                state,
                parameters,
                active_effect_id=None,
                parameter_key=(effect.slot_level_parameter_key or 'slot-level'),
                default=effect.base_slot_level,
            )
            for minimum_slot_level, bonus in sorted(effect.scaled_enchanted_bonus_tiers, key=lambda item: item[0]):
                if slot_level >= minimum_slot_level:
                    enchantment_bonus = bonus
        damage_bonus = effect.enchanted_damage_bonus
        if effect.scaled_enchanted_bonus_tiers and effect.enchanted_damage_bonus == effect.enchanted_attack_bonus:
            damage_bonus = enchantment_bonus
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            replace_existing_same_name_from_source=True,
            enchanted_item_id=item.record_id,
            enchanted_attack_ability=spellcasting_ability,
            enchanted_damage_ability=damage_ability,
            enchanted_damage_dice_count=damage_dice_count,
            enchanted_damage_die_faces=damage_die_faces,
            enchanted_damage_type_override=damage_type,
            enchanted_attack_bonus=enchantment_bonus,
            enchanted_damage_bonus=damage_bonus,
            end_when_enchanted_item_not_carried=effect.end_when_item_not_carried,
        )
        self._start_active_effect(
            state,
            events,
            source_actor_id=source_actor_id,
            target_ids=(item_owner.actor_id,),
            capability=capability,
            definition=definition,
            point=point,
        )

    def _recursive_damage_roll(self, state: EncounterState, *, die_faces: int, base_dice_count: int, extra_limit: int) -> tuple[tuple[int, ...], int]:
        rng = seeded_random(self.kernel.seed, state.random_counter)
        rolls: list[int] = []
        pending = base_dice_count
        extra_used = 0
        while pending > 0:
            roll = rng.randint(1, die_faces)
            rolls.append(roll)
            pending -= 1
            if roll == die_faces and extra_used < extra_limit:
                pending += 1
                extra_used += 1
        return tuple(rolls), sum(rolls)

    def _apply_recursive_spell_attack(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        effect: RecursiveSpellAttackEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('This spell requires exactly one target.')
        actor = self.kernel._require_actor(state, source_actor_id)
        damage_type = self._parameterized_damage_type(parameters, parameter_key=effect.damage_type_parameter_key, allowed_damage_types=effect.allowed_damage_types, default=effect.allowed_damage_types[0])
        base_dice_count = self._cantrip_damage_dice_count(actor.level) if effect.scale_with_cantrip_level else effect.base_dice_count
        attack = AttackProfile(
            attack_id=capability.capability_id,
            name=capability.name,
            attack_kind=AttackKind.RANGED if effect.attack_kind == AttackExecutionKind.RANGED_SPELL else AttackKind.MELEE,
            to_hit_bonus=(actor.spell_attack_bonus or 0),
            reach_ft=effect.reach_ft,
            range_ft=effect.range_ft,
            long_range_ft=effect.range_ft,
            damage_dice_count=base_dice_count,
            damage_die_faces=effect.damage_die_faces,
            damage_bonus=0,
            damage_type=damage_type,
        )
        hit, critical = self._apply_attack_profile_gate(state, events, source_actor_id=source_actor_id, target_id=target_ids[0], capability=capability, attack=attack, magical=effect.magical, damaging=effect.damaging)
        if not hit:
            return
        if actor.spellcasting_ability is None:
            raise EncounterValidationError('The acting actor lacks a spellcasting ability for this spell.')
        extra_limit = max(0, actor.ability_modifiers.get(actor.spellcasting_ability, 0))
        rolls, total = self._recursive_damage_roll(state, die_faces=effect.damage_die_faces, base_dice_count=base_dice_count * (2 if critical else 1), extra_limit=extra_limit)
        hp_after, temp_after, applied_damage_total, effect_events = self.kernel._damage_preview(state, self.kernel._require_target(state, target_ids[0]), total, damage_type=damage_type)
        self._emit(state, events, list(effect_events) + [DamageRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_ids[0], damage_rolls=rolls, damage_total=total, damage_type=damage_type, random_counter_used=state.random_counter), DamageAppliedEvent(source_actor_id=source_actor_id, target_id=target_ids[0], damage_total=total, applied_damage_total=applied_damage_total, target_hit_points_after=hp_after, target_temp_hit_points_after=temp_after, damage_type=damage_type, critical_hit=critical)])

    def _apply_instant_weapon_strike(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        effect: InstantWeaponStrikeEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('This spell requires exactly one target.')
        actor = self.kernel._require_actor(state, source_actor_id)
        item = self._select_item_for_effect(actor, parameter_key=effect.item_parameter_key, parameters=parameters, require_weapon=True, require_held=True)
        if effect.requires_proficiency and not actor_is_proficient_with_weapon(actor, item):
            raise EncounterValidationError('The acting actor is not proficient with the chosen weapon.')
        if item.cost_cp < 1:
            raise EncounterValidationError('The chosen weapon must be worth at least 1 CP.')
        spell_ability = effect.attack_ability or actor.spellcasting_ability
        if spell_ability is None:
            raise EncounterValidationError('The acting actor lacks a spellcasting ability for this spell.')
        damage_ability = effect.damage_ability or spell_ability
        attack = self._attack_profile_for_temporary_weapon_strike(
            state,
            actor=actor,
            target_id=target_ids[0],
            item=item,
            attack_ability=spell_ability,
            damage_ability=damage_ability,
            damage_type_override=self._parameterized_damage_type(parameters, parameter_key=effect.damage_type_parameter_key, allowed_damage_types=effect.allowed_damage_types, default=(item.weapon_damage_type or 'bludgeoning')),
        )
        hit, critical = self._apply_attack_profile_gate(state, events, source_actor_id=source_actor_id, target_id=target_ids[0], capability=capability, attack=attack, magical=True, damaging=True)
        if not hit:
            return
        damage_total = attack.damage_bonus
        damage_rolls: tuple[int, ...] = ()
        if attack.damage_dice_count > 0 and attack.damage_die_faces > 0:
            damage_rolls, damage_total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=attack.damage_dice_count * (2 if critical else 1), die_faces=attack.damage_die_faces, bonus=attack.damage_bonus)
        target = self.kernel._require_target(state, target_ids[0])
        hp_after, temp_after, applied_damage_total, effect_events = self.kernel._damage_preview(state, target, damage_total, damage_type=attack.damage_type)
        self._emit(state, events, list(effect_events) + [DamageRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_ids[0], damage_rolls=damage_rolls, damage_total=damage_total, damage_type=attack.damage_type, random_counter_used=state.random_counter), DamageAppliedEvent(source_actor_id=source_actor_id, target_id=target_ids[0], damage_total=damage_total, applied_damage_total=applied_damage_total, target_hit_points_after=hp_after, target_temp_hit_points_after=temp_after, damage_type=attack.damage_type, critical_hit=critical)])
        bonus_faces = effect.scaled_bonus_damage_die_faces
        if effect.scale_with_cantrip_level and bonus_faces is not None and actor.level >= 5:
            bonus_dice_count = self._cantrip_damage_dice_count(actor.level) - 1
            bonus_rolls, bonus_total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=bonus_dice_count * (2 if critical else 1), die_faces=bonus_faces, bonus=0)
            bonus_type = effect.scaled_bonus_damage_type or 'radiant'
            hp_after, temp_after, applied_damage_total, bonus_effect_events = self.kernel._damage_preview(state, target, bonus_total, damage_type=bonus_type)
            self._emit(state, events, list(bonus_effect_events) + [DamageRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_ids[0], damage_rolls=bonus_rolls, damage_total=bonus_total, damage_type=bonus_type, random_counter_used=state.random_counter), DamageAppliedEvent(source_actor_id=source_actor_id, target_id=target_ids[0], damage_total=bonus_total, applied_damage_total=applied_damage_total, target_hit_points_after=hp_after, target_temp_hit_points_after=temp_after, damage_type=bonus_type, critical_hit=critical)])

    def _apply_held_conjuration(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        point: GridPosition | None,
        effect: HeldConjurationEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        mode = parameters.get(effect.mode_parameter_key, '').strip().casefold()
        existing = self._existing_source_effect(state, source_actor_id=source_actor_id, name=effect.name)
        if effect.kind == HeldConjurationKind.PRODUCE_FLAME:
            throw_mode = mode == 'throw' or (not mode and bool(target_ids))
            if throw_mode:
                if existing is None:
                    raise EncounterValidationError('Produce Flame must already be active before it can be thrown.')
                if len(target_ids) != 1:
                    raise EncounterValidationError('Throwing Produce Flame requires exactly one target.')
                damage_dice_count = self._cantrip_damage_dice_count(actor.level) if effect.scale_with_cantrip_level else 1
                attack = AttackProfile(
                    attack_id=capability.capability_id,
                    name=capability.name,
                    attack_kind=AttackKind.RANGED,
                    to_hit_bonus=(actor.spell_attack_bonus or 0),
                    reach_ft=None,
                    range_ft=60,
                    long_range_ft=60,
                    damage_dice_count=damage_dice_count,
                    damage_die_faces=8,
                    damage_bonus=0,
                    damage_type='fire',
                )
                hit, critical = self._apply_attack_profile_gate(state, events, source_actor_id=source_actor_id, target_id=target_ids[0], capability=capability, attack=attack, magical=True, damaging=True)
                if hit:
                    damage_rolls, damage_total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=damage_dice_count * (2 if critical else 1), die_faces=8, bonus=0)
                    hp_after, temp_after, applied_damage_total, effect_events = self.kernel._damage_preview(state, self.kernel._require_target(state, target_ids[0]), damage_total, damage_type='fire')
                    self._emit(state, events, list(effect_events) + [DamageRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_ids[0], damage_rolls=damage_rolls, damage_total=damage_total, damage_type='fire', random_counter_used=state.random_counter), DamageAppliedEvent(source_actor_id=source_actor_id, target_id=target_ids[0], damage_total=damage_total, applied_damage_total=applied_damage_total, target_hit_points_after=hp_after, target_temp_hit_points_after=temp_after, damage_type='fire', critical_hit=critical)])
                self._end_active_effect(state, events, effect_id=existing.effect_instance_id, reason='produce-flame-thrown')
                return
            definition = ActiveEffectDefinition(
                name=effect.name,
                duration=effect.duration,
                concentration=effect.concentration,
                replace_existing_same_name_from_source=True,
                bright_light_radius_ft=20,
                dim_light_radius_ft=40,
            )
            self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(source_actor_id,), capability=capability, definition=definition, point=actor.position)
            return
        if effect.kind == HeldConjurationKind.DANCING_LIGHTS:
            if point is None:
                raise EncounterValidationError('Dancing Lights requires a point target.')
            if grid_distance_ft(actor.position, point) > 120:
                raise EncounterValidationError('Dancing Lights must stay within 120 feet of the caster.')
            form = parameters.get(effect.form_parameter_key, '').strip().casefold() or 'lights'
            if mode == 'move' and existing is None:
                raise EncounterValidationError('Dancing Lights can only be moved after it is already active.')
            existing_origin = None if existing is None else existing.origin_point
            if mode == 'move' and existing_origin is None:
                raise EncounterValidationError('Dancing Lights is missing its existing anchor point.')
            if mode == 'move' and existing_origin is not None and grid_distance_ft(existing_origin, point) > 60:
                raise EncounterValidationError('Dancing Lights can only move up to 60 feet with each command.')
            if form not in {'lights', 'humanoid'}:
                raise EncounterValidationError('Dancing Lights form must be `lights` or `humanoid`.')
            relative_origins = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)) if form == 'lights' else ((0, 0, 0),)
            definition = ActiveEffectDefinition(
                name=effect.name,
                duration=effect.duration,
                concentration=True,
                replace_existing_same_name_from_source=True,
                max_distance_from_source_ft=120,
                illusions=(
                    IllusionDefinition(
                        template_id=IllusionTemplateId.MEDIUM_SCENE_DRESSING_ILLUSION,
                        subtype=IllusionSubtype.ENVIRONMENTAL,
                        modality=IllusionModality.VISUAL,
                        display_name='Dancing Lights',
                        display_description=('A cluster of four torch-sized lights.' if form == 'lights' else 'A glowing Medium humanoid outline composed of light.'),
                        width_ft=(10 if form == 'lights' else 5),
                        depth_ft=(10 if form == 'lights' else 5),
                        height_ft=(5 if form == 'lights' else 10),
                        semantic_tags=('dancing-lights', form),
                    ),
                ),
                persistent_areas=(
                    PersistentAreaDefinition(
                        name='Dancing Lights',
                        area_shape=AreaShape.SPHERE,
                        area_size_ft=10,
                        semantic_tags=('dancing-lights',),
                        dim_light_radius_ft=10,
                        relative_origins=relative_origins,
                    ),
                ),
            )
            self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(source_actor_id,), capability=capability, definition=definition, point=point)
            return
        if effect.kind == HeldConjurationKind.MAGE_HAND:
            if mode in {'interact', 'command'}:
                if existing is None:
                    raise EncounterValidationError('Mage Hand must already exist before it can be commanded.')
                existing_origin = existing.origin_point
                if existing_origin is None:
                    raise EncounterValidationError('Mage Hand is missing its existing anchor point.')
                object_id = parameters.get('object', '').strip()
                action_raw = parameters.get(effect.action_parameter_key, '').strip().lower() or 'toggle'
                if not object_id:
                    raise EncounterValidationError('Mage Hand interaction requires --object.')
                try:
                    object_action = EnvironmentObjectAction(action_raw)
                except ValueError as exc:
                    raise EncounterValidationError('Mage Hand interaction requires a valid --action value.') from exc
                interaction_events = self.kernel._resolve_object_interaction_events(
                    state,
                    actor=actor,
                    interaction_kind=ObjectInteractionKind.USE_ENVIRONMENT_OBJECT,
                    cost_mode=ObjectInteractionCostMode.ATTACK,
                    object_id=object_id,
                    object_action=object_action,
                    origin_position=existing_origin,
                    reach_ft=5,
                )
                self._emit(state, events, interaction_events)
                return
            if point is None:
                raise EncounterValidationError('Mage Hand requires a point target.')
            if grid_distance_ft(actor.position, point) > 30:
                raise EncounterValidationError('Mage Hand must stay within 30 feet of the caster.')
            if mode == 'move' and existing is None:
                raise EncounterValidationError('Mage Hand can only be moved after it is already active.')
            existing_origin = None if existing is None else existing.origin_point
            if mode == 'move' and existing_origin is None:
                raise EncounterValidationError('Mage Hand is missing its existing anchor point.')
            if mode == 'move' and existing_origin is not None and grid_distance_ft(existing_origin, point) > 30:
                raise EncounterValidationError('Mage Hand can only move up to 30 feet with each command.')
            definition = ActiveEffectDefinition(
                name=effect.name,
                duration=effect.duration,
                concentration=effect.concentration,
                replace_existing_same_name_from_source=True,
                max_distance_from_source_ft=30,
                created_objects=(
                    CreatedObjectDefinition(
                        name='Mage Hand',
                        feature_type='mage-hand',
                        physical=False,
                        interaction_allowed=True,
                        semantic_tags=('mage-hand', 'spectral-hand'),
                        apparent_label='Mage Hand',
                    ),
                ),
            )
            self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(source_actor_id,), capability=capability, definition=definition, point=point)
            return
        raise EncounterValidationError('Unsupported held conjuration kind.')

    def _apply_friends(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        effect: FriendsEffectDef,
    ) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('Friends requires exactly one target.')
        actor = self.kernel._require_actor(state, source_actor_id)
        target = self.kernel._require_target(state, target_ids[0])
        label = target.creature_type.casefold()
        prior_cast_at = actor.friends_targeted_at_seconds.get(target.actor_id)
        auto_success = ('humanoid' not in label) or (prior_cast_at is not None and state.clock_seconds - prior_cast_at < 24 * 60 * 60)
        if auto_success:
            self._emit(state, events, [CapabilityMissedEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target.actor_id)])
            return
        req = SaveRequest(context=ResolutionContext(effect_id=capability.capability_id, source_actor_id=source_actor_id, target_actor_id=target.actor_id, reason=capability.name), ability=Ability.WIS, dc=(actor.spell_save_dc or 8 + actor.proficiency_bonus))
        resolution, save_events = self.kernel.resolve_save_consumer(state, req, apply=True)
        events.extend(save_events)
        if resolution.branch.value != 'failure':
            self._emit(state, events, [CapabilityMissedEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target.actor_id)])
            return
        definition = ActiveEffectDefinition(
            name=effect.name,
            duration=effect.duration,
            concentration=effect.concentration,
            replace_existing_same_name_from_source=True,
            information_payloads=(
                InformationPayloadDefinition(
                    kind=InformationPayloadKind.DETECTION,
                    title='Friends',
                    detail=f'{target.name} is under magical influence from {actor.name}. While the spell lasts, play the target as socially disposed toward the caster. When the effect ends, the target knows magic influenced them.',
                    tags=('friends', 'social-guidance'),
                    observer_filter=PersistentObserverFilter(observer_mode=PersistentObserverMode.ALL_VALID_OBSERVERS),
                    share_mode=InformationShareMode.DM_ONLY,
                ),
            ),
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(target.actor_id,), capability=capability, definition=definition, point=None)
        active_effect = self._existing_source_effect(state, source_actor_id=source_actor_id, name=effect.name)
        if active_effect is None:
            raise EncounterValidationError('Friends failed to start its active effect state.')
        self._emit(
            state,
            events,
            [
                ConditionAddedEvent(
                    actor_id=target.actor_id,
                    instance=self.kernel._make_condition_instance(
                        target_actor_id=target.actor_id,
                        condition_type=ConditionType.CHARMED,
                        source_actor_id=source_actor_id,
                        source_effect_id=active_effect.effect_instance_id,
                        source_label=capability.name,
                        charmer_actor_id=source_actor_id,
                    ),
                ),
                CapabilityHitEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target.actor_id),
            ],
        )
    def _apply_dash_effect(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_ids: tuple[str, ...], use_bonus_action_speed: bool) -> None:
        resolved_targets = target_ids or (source_actor_id,)
        for target_id in resolved_targets:
            target = self.kernel._require_actor(state, target_id)
            dash_speed = get_effective_speed(target)
            self._emit(
                state,
                events,
                [
                    ActionEffectEvent(
                        actor_id=target.actor_id,
                        action_type=CombatActionType.DASH,
                        remaining_movement_ft=target.remaining_movement_ft + dash_speed,
                        dash_bonus_ft=target.dash_bonus_ft + dash_speed,
                    )
                ],
            )

    def _apply_command_word(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], point: GridPosition | None, effect: CommandWordEffectDef, parameters: Mapping[str, str]) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('Command requires exactly one target.')
        command = self._required_parameter(parameters, effect.command_parameter_key, label='a command word').casefold()
        if command not in {value.casefold() for value in effect.allowed_commands}:
            labels = ', '.join(effect.allowed_commands)
            raise EncounterValidationError(f'Command requires one of: {labels}.')
        definition = ActiveEffectDefinition(
            name=f'Command:{command}',
            duration=effect.duration,
            replace_existing_same_name_from_source=True,
            ongoing_triggers=(
                OngoingTriggerDefinition(
                    timing=TriggerTiming.START_OF_TURN,
                    actor_scope=TriggerActorScope.EACH_TARGET,
                ),
            ),
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=target_ids, capability=capability, definition=definition, point=point)

    def _is_magical_effect(self, state: EncounterState, effect: ActiveEffectState) -> bool:
        source = state.actors.get(effect.source_actor_id)
        if source is None:
            return False
        return effect.capability_id in source.spells or any(spell.capability is not None and spell.capability.capability_id == effect.capability_id for spell in source.spells.values())

    def _magic_item_ids(self, actor: RuntimeActorState) -> tuple[str, ...]:
        item_ids = set(actor.carried_item_counts)
        item_ids.update(filter(None, (actor.main_hand_item_id, actor.off_hand_item_id, actor.equipped_armor_item_id, actor.worn_armor_item_id, actor.worn_shield_item_id)))
        magical = []
        for item_id in sorted(item_ids):
            item = self.kernel.item_catalog.get(item_id)
            if item is not None and item.is_magical:
                magical.append(item_id)
        return tuple(magical)

    def _detection_detail_lines(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        sense_kind: DetectionSenseKind,
        inspect_mode: bool,
        ignored_effect_ids: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        lines: list[str] = []
        for other in state.actors.values():
            if self.kernel.battlefield_rules.get_distance3d(actor.position, other.position) > 30:
                continue
            if sense_kind == DetectionSenseKind.MAGIC:
                magical_effects = sorted(
                    {
                        effect.name
                        for effect in state.active_effects.values()
                        if effect.effect_instance_id not in ignored_effect_ids
                        and other.actor_id in effect.target_actor_ids
                        and self._is_magical_effect(state, effect)
                    }
                )
                magical_items = [self.kernel.item_catalog[item_id].name for item_id in self._magic_item_ids(other) if item_id in self.kernel.item_catalog]
                if magical_effects or magical_items:
                    if inspect_mode:
                        parts: list[str] = []
                        if magical_effects:
                            parts.append(f'effects: {", ".join(magical_effects)}')
                        if magical_items:
                            parts.append(f'items: {", ".join(magical_items)}')
                        lines.append(f'{other.name}: ' + '; '.join(parts))
                    else:
                        lines.append(f'Magical presence detected near {other.name}.')
            elif sense_kind == DetectionSenseKind.POISON_AND_DISEASE:
                poisonous = any(attack.damage_type.casefold() == 'poison' for attack in other.attacks.values())
                poisoned = ConditionType.POISONED in {instance.condition_type for instance in other.condition_instances}
                diseased = any(
                    'disease' in effect.name.casefold()
                    for effect in state.active_effects.values()
                    if effect.effect_instance_id not in ignored_effect_ids
                    and other.actor_id in effect.target_actor_ids
                )
                if poisonous or poisoned or diseased:
                    parts: list[str] = []
                    if poisonous:
                        parts.append('poisonous creature')
                    if poisoned:
                        parts.append('poisoned')
                    if diseased:
                        parts.append('disease effect')
                    lines.append(f'{other.name}: ' + ', '.join(parts))
            elif sense_kind == DetectionSenseKind.EVIL_AND_GOOD:
                detected_types = {'aberration', 'celestial', 'elemental', 'fey', 'fiend', 'undead'}
                if other.creature_type.casefold() in detected_types:
                    lines.append(f'{other.name}: {other.creature_type}')
        if not lines:
            return ('Nothing relevant is detected in range.',)
        return tuple(lines)
    def _emit_information_scan(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, title: str, detail_lines: tuple[str, ...], kind: InformationPayloadKind = InformationPayloadKind.DETECTION) -> None:
        payload_id = f'{capability.capability_id}:{source_actor_id}:scan:{state.random_counter}:{len(events)}'
        persistent = PersistentEffectState(
            persistent_effect_id=payload_id,
            family=PersistentEffectFamily.INFORMATION_PAYLOAD,
            source_effect_id=payload_id,
            source_capability_id=capability.capability_id,
            source_actor_id=source_actor_id,
            owner_actor_id=source_actor_id,
            owner_controller_id=None,
            anchor_position=self.kernel._require_actor(state, source_actor_id).position,
            observer_mode=PersistentObserverMode.SELECTED_OBSERVERS,
            observer_actor_ids=(source_actor_id,),
        )
        payload = InformationalPayloadState(
            persistent=persistent,
            payload_id=payload_id,
            definition=InformationPayloadDefinition(
                kind=kind,
                title=title,
                detail='\n'.join(detail_lines),
                tags=(capability.capability_id,),
                observer_filter=PersistentObserverFilter(observer_mode=PersistentObserverMode.SELECTED_OBSERVERS, observer_actor_ids=(source_actor_id,)),
                share_mode=InformationShareMode.OBSERVER_ONLY,
            ),
        )
        event_type = DetectionPayloadProducedEvent if kind == InformationPayloadKind.DETECTION else DivinationPayloadProducedEvent
        self._emit(state, events, [event_type(payload=payload)])

    def _apply_detection_scan(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], point: GridPosition | None, effect: DetectionScanEffectDef, parameters: Mapping[str, str]) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        mode = parameters.get(effect.mode_parameter_key, '').strip().casefold() or 'cast'
        if mode not in {'cast', 'inspect'}:
            raise EncounterValidationError('Supported detection spell modes are `cast` and `inspect`.')
        existing = self._existing_source_effect(state, source_actor_id=source_actor_id, name=effect.name)
        if mode == 'inspect' and existing is None:
            raise EncounterValidationError('That spell must already be active before it can be inspected.')
        if mode == 'cast':
            definition = ActiveEffectDefinition(
                name=effect.name,
                duration=effect.duration,
                concentration=effect.concentration,
                replace_existing_same_name_from_source=True,
            )
            self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(source_actor_id,), capability=capability, definition=definition, point=actor.position)
        active_effect = self._existing_source_effect(state, source_actor_id=source_actor_id, name=effect.name)
        ignored_effect_ids = frozenset({active_effect.effect_instance_id}) if active_effect is not None else frozenset()
        detail_lines = self._detection_detail_lines(
            state,
            actor=actor,
            sense_kind=effect.sense_kind,
            inspect_mode=(mode == 'inspect'),
            ignored_effect_ids=ignored_effect_ids,
        )
        self._emit_information_scan(state, events, source_actor_id=source_actor_id, capability=capability, title=effect.name, detail_lines=detail_lines)

    def _apply_alarm_trigger_notice(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, capability: CapabilityDefinition, point: GridPosition | None, effect: AlarmTriggerEffectDef) -> None:
        intruder = self.kernel._require_actor(state, target_id)
        observer_actor_ids: tuple[str, ...]
        if effect.mode == 'audible' and point is not None:
            observer_actor_ids = tuple(
                actor.actor_id
                for actor in state.actors.values()
                if self.kernel.battlefield_rules.get_distance3d(actor.position, point) <= 60
            )
        else:
            observer_actor_ids = (source_actor_id,)
        payload_id = f'alarm-trigger:{source_actor_id}:{target_id}:{state.random_counter}:{len(events)}'
        persistent = PersistentEffectState(
            persistent_effect_id=payload_id,
            family=PersistentEffectFamily.INFORMATION_PAYLOAD,
            source_effect_id=payload_id,
            source_capability_id=capability.capability_id,
            source_actor_id=source_actor_id,
            owner_actor_id=source_actor_id,
            owner_controller_id=None,
            anchor_position=(point or intruder.position),
            observer_mode=PersistentObserverMode.SELECTED_OBSERVERS,
            observer_actor_ids=observer_actor_ids,
        )
        payload = InformationalPayloadState(
            persistent=persistent,
            payload_id=payload_id,
            definition=InformationPayloadDefinition(
                kind=InformationPayloadKind.DETECTION,
                title='Alarm Triggered',
                detail=f'{intruder.name} triggered the alarm ({effect.mode}) at ({(point or intruder.position).x},{(point or intruder.position).y},{(point or intruder.position).z}).',
                tags=('alarm', effect.mode),
                observer_filter=PersistentObserverFilter(observer_mode=PersistentObserverMode.SELECTED_OBSERVERS, observer_actor_ids=observer_actor_ids),
                share_mode=InformationShareMode.OBSERVER_ONLY,
            ),
        )
        self._emit(state, events, [DetectionPayloadProducedEvent(payload=payload)])

    def _apply_alarm_ward(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, target_ids: tuple[str, ...], point: GridPosition | None, effect: AlarmWardEffectDef, parameters: Mapping[str, str]) -> None:
        if point is None:
            raise EncounterValidationError('Alarm requires a point target for the warded area.')
        mode = parameters.get(effect.mode_parameter_key, '').strip().casefold() or 'mental'
        if mode not in {'mental', 'audible'}:
            raise EncounterValidationError('Alarm mode must be `mental` or `audible`.')
        form = parameters.get(effect.form_parameter_key, '').strip().casefold() or 'cube'
        if form not in {'cube', 'door', 'window'}:
            raise EncounterValidationError('Alarm form must be `cube`, `door`, or `window`.')
        raw_excluded = parameters.get(effect.exclude_parameter_key, '')
        excluded = tuple(dict.fromkeys(value.strip() for value in raw_excluded.replace(',', ' ').split() if value.strip())) + (source_actor_id,)
        area_size_ft = 20 if form == 'cube' else 5
        definition = ActiveEffectDefinition(
            name='Alarm',
            duration=effect.duration,
            replace_existing_same_name_from_source=True,
            persistent_areas=(
                PersistentAreaDefinition(
                    name='Alarm',
                    area_shape=AreaShape.CUBE,
                    area_size_ft=area_size_ft,
                    semantic_tags=tuple(['alarm', f'alarm-mode:{mode}', f'alarm-form:{form}', *[f'exclude:{actor_id}' for actor_id in excluded]]),
                    entry_effects=(AlarmTriggerEffectDef(mode=mode),),
                ),
            ),
        )
        self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=(source_actor_id,), capability=capability, definition=definition, point=point)
        self._emit_information_scan(state, events, source_actor_id=source_actor_id, capability=capability, title='Alarm', detail_lines=(f'Alarm ward established at ({point.x},{point.y},{point.z}) with {mode} alerting and {form} coverage.',))

    def _apply_forced_reaction_move(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, capability: CapabilityDefinition, effect: ForcedReactionMoveEffectDef) -> None:
        target = self.kernel._require_target(state, target_id)
        if effect.requires_reaction and (not target.reaction_available or not target.is_conscious):
            return
        if effect.requires_reaction:
            self._emit(state, events, [ResourceSpentEvent(actor_id=target.actor_id, resource='reaction', reason=capability.capability_id)])
        move_effect = ForcedMovementEffect(
            context=ResolutionContext(effect_id=capability.capability_id, source_actor_id=source_actor_id, target_actor_id=target.actor_id, reason=capability.name),
            mode=ForcedMovementMode.PUSH,
            distance_ft=(get_effective_speed(target) if effect.use_speed_ft else target.speed_ft),
        )
        result, forced_events = self.kernel.apply_forced_movement(state, move_effect, apply=False)
        self._emit(state, events, [*forced_events, ForcedMovementAppliedEvent(actor_id=source_actor_id, target_id=target.actor_id, final_position=result.final_position, moved_distance_ft=result.moved_distance_ft)])

    def _apply_command_trigger(self, state: EncounterState, events: list[object], *, effect: ActiveEffectState, trigger_actor_id: str) -> None:
        target = self.kernel._require_actor(state, trigger_actor_id)
        source = self.kernel._require_actor(state, effect.source_actor_id)
        command = effect.name.split(':', 1)[1].casefold() if ':' in effect.name else ''
        movement_to_spend = max(0, target.remaining_movement_ft)
        lock_events = [
            ResourceSpentEvent(actor_id=target.actor_id, resource='action', reason='command'),
            ResourceSpentEvent(actor_id=target.actor_id, resource='bonus', reason='command'),
            ResourceSpentEvent(actor_id=target.actor_id, resource='movement', reason='command', amount=movement_to_spend),
            ActionEffectEvent(actor_id=target.actor_id, action_type=CombatActionType.MAGIC, remaining_movement_ft=0, dash_bonus_ft=0),
        ]
        if command == 'grovel':
            self._emit(state, events, [self.kernel._condition_added_event_from_application(target_actor_id=target.actor_id, application=ConditionApplication(condition_type=ConditionType.PRONE, source_label='Command', source_effect_id=effect.effect_instance_id, source_actor_id=effect.source_actor_id)), *lock_events])
            return
        if command == 'halt':
            self._emit(state, events, lock_events)
            return
        if command == 'drop':
            drop_events: list[object] = []
            for item_id in tuple(target.held_item_ids):
                drop_events.extend(self.kernel._resolve_object_interaction_events(state, actor=target, interaction_kind=ObjectInteractionKind.DROP, cost_mode=ObjectInteractionCostMode.ATTACK, item_id=item_id, origin_position=target.position, reach_ft=0))
            self._emit(state, events, [*drop_events, *lock_events])
            return
        distance_ft = get_effective_speed(target)
        move_effect = ForcedMovementEffect(
            context=ResolutionContext(effect_id=effect.effect_instance_id, source_actor_id=effect.source_actor_id, target_actor_id=target.actor_id, reason='Command'),
            mode=(ForcedMovementMode.PULL if command == 'approach' else ForcedMovementMode.PUSH),
            distance_ft=distance_ft,
        )
        forced_result, forced_events = self.kernel.apply_forced_movement(state, move_effect, apply=False)
        self._emit(state, events, [*forced_events, ForcedMovementAppliedEvent(actor_id=effect.source_actor_id, target_id=target.actor_id, final_position=forced_result.final_position, moved_distance_ft=forced_result.moved_distance_ft), *lock_events])

    def _apply_damage(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, effect: DamageEffectDef, critical_hit: bool) -> None:
        source_actor = self.kernel._require_actor(state, source_actor_id)
        target = self.kernel._require_target(state, target_id)
        base_dice_count = self._cantrip_damage_dice_count(source_actor.level) if effect.scale_with_cantrip_level else effect.dice_count
        dice_count = base_dice_count * (2 if critical_hit and effect.double_dice_on_critical_hit else 1)
        rolls, total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=dice_count, die_faces=effect.die_faces, bonus=effect.bonus)
        if effect.damage_divisor > 1:
            total //= effect.damage_divisor
        hp_after, temp_after, applied_damage_total, effect_events = self.kernel._damage_preview(state, target, total, damage_type=effect.damage_type)
        self._emit(state, events, list(effect_events) + [DamageRolledEvent(actor_id=source_actor_id, attack_id=None, target_id=target_id, damage_rolls=rolls, damage_total=total, damage_type=effect.damage_type, random_counter_used=state.random_counter), DamageAppliedEvent(source_actor_id=source_actor_id, target_id=target_id, damage_total=total, applied_damage_total=applied_damage_total, target_hit_points_after=hp_after, target_temp_hit_points_after=temp_after, damage_type=effect.damage_type)])

    def _apply_missing_hit_points_damage(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, effect: MissingHitPointsDamageEffectDef) -> None:
        target = self.kernel._require_target(state, target_id)
        die_faces = effect.damaged_die_faces if target.current_hit_points < target.max_hit_points else effect.undamaged_die_faces
        self._apply_damage(
            state,
            events,
            source_actor_id=source_actor_id,
            target_id=target_id,
            effect=DamageEffectDef(dice_count=effect.dice_count, die_faces=die_faces, bonus=effect.bonus, damage_type=effect.damage_type, scale_with_cantrip_level=effect.scale_with_cantrip_level),
            critical_hit=False,
        )

    def _apply_healing(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, effect: HealingEffectDef) -> None:
        source = self.kernel._require_actor(state, source_actor_id)
        target = self.kernel._require_target(state, target_id)
        if self.kernel._healing_blocked(state, target.actor_id):
            raise EncounterValidationError('The target cannot regain hit points right now.')
        bonus = self._healing_bonus(source, effect)
        rolls, total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=effect.dice_count, die_faces=effect.die_faces, bonus=effect.bonus + bonus)
        self._emit(state, events, [DamageRolledEvent(actor_id=source_actor_id, attack_id=None, target_id=target_id, damage_rolls=rolls, damage_total=total, damage_type='healing', random_counter_used=state.random_counter), HealingAppliedEvent(source_actor_id=source_actor_id, target_id=target_id, healing_total=total, target_hit_points_after=min(target.max_hit_points, target.current_hit_points + total))])

    def _apply_spend_hit_dice_healing(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_ids: tuple[str, ...], effect: SpendHitDiceHealingEffectDef, parameters: Mapping[str, str]) -> None:
        target_id = target_ids[0] if target_ids else source_actor_id
        source = self.kernel._require_actor(state, source_actor_id)
        target = self.kernel._require_target(state, target_id)
        if target.actor_id != source_actor_id:
            raise EncounterValidationError('This capability can only spend the source actor\'s Hit Point Dice.')
        if target.remaining_hit_dice <= 0:
            raise EncounterValidationError('The actor has no Hit Point Dice remaining.')
        if target.current_hit_points >= target.max_hit_points:
            raise EncounterValidationError('The actor is already at maximum hit points.')
        requested = parameters.get(effect.count_parameter_key, '').strip()
        if not requested:
            raise EncounterValidationError(f'This capability requires --{effect.count_parameter_key} <count>.')
        try:
            requested_count = int(requested)
        except ValueError as exc:
            raise EncounterValidationError(f'Invalid --{effect.count_parameter_key} value: {requested!r}.') from exc
        slot_level = self._slot_level_from_parameters(
            state,
            parameters,
            active_effect_id=None,
            parameter_key=effect.slot_level_parameter_key,
            default=effect.base_slot_level,
        )
        effective_maximum_count = effect.maximum_count + max(0, slot_level - effect.base_slot_level) * effect.bonus_maximum_count_per_slot_level
        if requested_count < effect.minimum_count or requested_count > effective_maximum_count:
            raise EncounterValidationError(f'This capability requires {effect.minimum_count}-{effective_maximum_count} Hit Point Dice.')
        if requested_count > target.remaining_hit_dice:
            raise EncounterValidationError('The actor does not have that many unused Hit Point Dice.')
        constitution_modifier = target.ability_modifiers.get(Ability.CON, 0) if effect.apply_constitution_modifier_per_die else 0
        bonus = self._healing_bonus(source, effect)
        current_hit_points = target.current_hit_points
        remaining_hit_dice = target.remaining_hit_dice
        total_from_dice = 0
        random_counter = state.random_counter
        spent_count = 0
        for _ in range(requested_count):
            if not effect.spend_all_requested_dice and current_hit_points >= target.max_hit_points:
                break
            roll = seeded_random(self.kernel.seed, random_counter).randint(1, target.hit_die_faces)
            hit_points_from_die = max(1, roll + constitution_modifier) if effect.apply_constitution_modifier_per_die else roll
            total_from_dice += hit_points_from_die
            if not effect.spend_all_requested_dice:
                current_hit_points = min(target.max_hit_points, current_hit_points + hit_points_from_die)
            remaining_hit_dice -= 1
            spent_count += 1
            self._emit(state, events, [HitPointDieSpentEvent(actor_id=target.actor_id, die_faces=target.hit_die_faces, roll=roll, constitution_modifier=constitution_modifier, hit_points_gained=hit_points_from_die, remaining_hit_dice=remaining_hit_dice, random_counter_used=random_counter)])
            random_counter += 1
        if spent_count <= 0 or total_from_dice <= 0:
            raise EncounterValidationError('No additional Hit Point Dice can be spent right now.')
        healing_total = min(target.max_hit_points - target.current_hit_points, total_from_dice + bonus)
        self._emit(state, events, [HealingAppliedEvent(source_actor_id=source_actor_id, target_id=target.actor_id, healing_total=healing_total, target_hit_points_after=min(target.max_hit_points, target.current_hit_points + healing_total))])

    def _apply_temporary_hit_points(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, effect: TemporaryHitPointsEffectDef) -> None:
        source = self.kernel._require_actor(state, source_actor_id)
        bonus = self._healing_bonus(source, effect)
        rolls: tuple[int, ...] = ()
        total = effect.bonus + bonus
        if effect.dice_count > 0 and effect.die_faces > 0:
            rolls, total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=effect.dice_count, die_faces=effect.die_faces, bonus=effect.bonus + bonus)
            self._emit(state, events, [DamageRolledEvent(actor_id=source_actor_id, attack_id=None, target_id=target_id, damage_rolls=rolls, damage_total=total, damage_type='temp-hp', random_counter_used=state.random_counter)])
        self._emit(state, events, [TemporaryHitPointsAppliedEvent(source_actor_id=source_actor_id, target_id=target_id, temp_hit_points_total=total)])

    def _apply_stabilize(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str) -> None:
        target = self.kernel._require_target(state, target_id)
        if target.current_hit_points != 0 or target.dying_state.status == target.dying_state.status.DEAD:
            raise EncounterValidationError('The chosen target cannot be stabilized.')
        recovery_hours, random_counter_used = self.kernel._roll_stable_recovery_hours(state)
        self._emit(state, events, [StabilizedEvent(actor_id=target_id, reason='magic-stabilized', stabilized_by_actor_id=source_actor_id, recovery_hours=recovery_hours, random_counter_used=random_counter_used)])

    def _apply_attack_gate(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, capability: CapabilityDefinition, gate: AttackRollGateEffect) -> tuple[bool, bool]:
        actor = self.kernel._require_actor(state, source_actor_id); target = self.kernel._require_target(state, target_id)
        if gate.damaging:
            validate_hostile_targeting(actor, target, is_damaging=True, is_magical=(capability.kind == CapabilityKind.SPELL))
        attack = AttackProfile(attack_id=capability.capability_id, name=capability.name, attack_kind=_ATTACK_KIND_MAP[gate.attack_kind], to_hit_bonus=self._attack_bonus(actor, gate), reach_ft=gate.reach_ft, range_ft=gate.range_ft, long_range_ft=gate.long_range_ft, damage_dice_count=0, damage_die_faces=0, damage_bonus=0, damage_type='force')
        legality = self.kernel.battlefield_rules.attack_legality(state, actor, target, attack)
        if not legality.has_line_of_sight:
            raise EncounterValidationError('The target cannot currently be seen by the acting actor.')
        if not legality.has_line_of_effect:
            raise EncounterValidationError('The target is blocked from line of effect.')
        modifiers = self.kernel._attack_modifier_state(state, actor, target, distance_ft=legality.distance_ft, long_range_disadvantage=legality.long_range_disadvantage)
        req = D20TestRequest(request_id=f'capability-attack:{capability.capability_id}:{source_actor_id}:{target_id}:{state.random_counter}', test_type=D20TestType.ATTACK, actor_id=source_actor_id, flat_modifier=attack.to_hit_bonus + modifiers['modifier'], roll_mode=merge_roll_mode(advantage=(modifiers['advantage'] or self._spell_attack_roll_advantage(state, actor_id=source_actor_id)), disadvantage=modifiers['disadvantage']), dc=target.effective_armor_class + legality.armor_class_bonus)
        self._emit(state, events, list(modifiers.get('effect_events', ())) + [AttackRollRequestedEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target_id)])
        res = self.kernel.d20_engine.resolve(req, random_counter=state.random_counter)
        self._emit(state, events, [
            D20TestRolledEvent(actor_id=source_actor_id, result=res.result, random_counter_used=res.random_counter_used),
            AttackRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_id, attack_rolls=res.result.rolls, attack_total=res.result.total, random_counter_used=res.random_counter_used),
            *self.kernel._consume_next_incoming_attack_roll_effects(tuple(modifiers.get('consumed_incoming_attack_advantage_effect_ids', ()))),
        ])
        hit = self.kernel._attack_hits(res.result.total, target.effective_armor_class + legality.armor_class_bonus, res.result.selected_roll)
        self._emit(state, events, [CapabilityHitEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target_id), AttackHitEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_id)] if hit else [CapabilityMissedEvent(actor_id=source_actor_id, capability_id=capability.capability_id, target_id=target_id), AttackMissedEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=target_id)])
        return hit, res.result.critical_success

    def _apply_conditional_creature_type_damage(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        target_id: str,
        effect: ConditionalCreatureTypeDamageEffectDef,
    ) -> None:
        self._execute_effect(state, events, source_actor_id=source_actor_id, capability=CapabilityDefinition(capability_id='conditional-damage', name='Conditional Damage', kind=CapabilityKind.SPELL, source='XPHB', action_cost='none', targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE), effect=effect.base_damage), effect=effect.base_damage, target_ids=(target_id,), point=None, active_effect_id=None, critical_hit=False, parameters={})
        target = self.kernel._require_target(state, target_id)
        if effect.bonus_damage is not None and target.creature_type.casefold() in {value.casefold() for value in effect.creature_types}:
            self._execute_effect(state, events, source_actor_id=source_actor_id, capability=CapabilityDefinition(capability_id='conditional-damage', name='Conditional Damage', kind=CapabilityKind.SPELL, source='XPHB', action_cost='none', targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE), effect=effect.bonus_damage), effect=effect.bonus_damage, target_ids=(target_id,), point=None, active_effect_id=None, critical_hit=False, parameters={})

    def _apply_group_save_gate(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        gate: GroupSaveGateEffectDef,
        point: GridPosition | None,
        parameters: Mapping[str, str],
    ) -> None:
        source_actor = self.kernel._require_actor(state, source_actor_id)
        failed_target_ids: list[str] = []
        succeeded_target_ids: list[str] = []
        for target_id in target_ids:
            target = self.kernel._require_target(state, target_id)
            roll_mode = merge_roll_mode(
                advantage=(gate.roll_mode == D20RollMode.ADVANTAGE or (gate.advantage_when_target_hostile_to_source and target.side != source_actor.side)),
                disadvantage=(gate.roll_mode == D20RollMode.DISADVANTAGE),
            )
            req = SaveRequest(
                context=ResolutionContext(effect_id=capability.capability_id, source_actor_id=source_actor_id, target_actor_id=target_id, reason=capability.name),
                ability=gate.ability,
                dc=self._save_dc(state, source_actor, gate),
                roll_mode=roll_mode,
            )
            resolution, save_events = self.kernel.resolve_save_consumer(state, req, apply=True)
            events.extend(save_events)
            branch = gate.on_failure if resolution.branch.value == 'failure' else gate.on_success
            for child in branch:
                self._execute_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=child, target_ids=(target_id,), point=point, active_effect_id=None, critical_hit=False, parameters=parameters)
            if resolution.branch.value == 'failure':
                failed_target_ids.append(target_id)
            else:
                succeeded_target_ids.append(target_id)
        if failed_target_ids and gate.failure_active_effect is not None:
            self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=tuple(failed_target_ids), capability=capability, definition=gate.failure_active_effect, point=point)
        if succeeded_target_ids and gate.success_active_effect is not None:
            self._start_active_effect(state, events, source_actor_id=source_actor_id, target_ids=tuple(succeeded_target_ids), capability=capability, definition=gate.success_active_effect, point=point)

    def _apply_group_parameterized_condition_save_gate(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        gate: SaveGateEffect,
        point: GridPosition | None,
        condition_effect: ParameterizedConditionEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        source_actor = self.kernel._require_actor(state, source_actor_id)
        chosen = self._required_parameter(parameters, condition_effect.condition_parameter_key, label='a condition').strip().casefold()
        condition_aliases = {
            'blind': ConditionType.BLINDED,
            'blindness': ConditionType.BLINDED,
            'blinded': ConditionType.BLINDED,
            'deaf': ConditionType.DEAFENED,
            'deafness': ConditionType.DEAFENED,
            'deafened': ConditionType.DEAFENED,
        }
        if chosen in condition_aliases:
            condition_type = condition_aliases[chosen]
        else:
            allowed = {value.value.casefold(): value for value in condition_effect.allowed_condition_types}
            if chosen not in allowed:
                labels = ', '.join(condition.value for condition in condition_effect.allowed_condition_types)
                raise EncounterValidationError(f'Invalid condition. Choose one of: {labels}.')
            condition_type = allowed[chosen]
        failed_target_ids: list[str] = []
        succeeded_target_ids: list[str] = []
        for target_id in target_ids:
            target = self.kernel._require_target(state, target_id)
            roll_mode = merge_roll_mode(
                advantage=(gate.roll_mode == D20RollMode.ADVANTAGE or (gate.advantage_when_target_hostile_to_source and target.side != source_actor.side)),
                disadvantage=(gate.roll_mode == D20RollMode.DISADVANTAGE),
            )
            if gate.advantage_for_target_sizes and target.size.casefold() in {value.casefold() for value in gate.advantage_for_target_sizes}:
                roll_mode = merge_roll_mode(advantage=True, disadvantage=(roll_mode == D20RollMode.DISADVANTAGE))
            req = SaveRequest(
                context=ResolutionContext(effect_id=capability.capability_id, source_actor_id=source_actor_id, target_actor_id=target_id, reason=capability.name),
                ability=gate.ability,
                dc=self._save_dc(state, source_actor, gate),
                partial_success_margin=gate.partial_success_margin,
                roll_mode=roll_mode,
            )
            resolution, save_events = self.kernel.resolve_save_consumer(state, req, apply=True)
            events.extend(save_events)
            if resolution.branch.value == 'failure':
                failed_target_ids.append(target_id)
            else:
                succeeded_target_ids.append(target_id)
        if failed_target_ids:
            definition = ActiveEffectDefinition(
                name=condition_effect.name,
                duration=condition_effect.duration,
                concentration=condition_effect.concentration,
                replace_existing_same_name_from_source=condition_effect.replace_existing_same_name_from_source,
                on_start=(ConditionEffectDef(condition_type=condition_type, source_label=(condition_effect.source_label or condition_effect.name)),),
                ongoing_triggers=condition_effect.ongoing_triggers,
            )
            self._apply_start_active_effect_def(
                state,
                events,
                source_actor_id=source_actor_id,
                capability=capability,
                target_ids=tuple(failed_target_ids),
                point=point,
                effect=StartActiveEffectDef(
                    active_effect=definition,
                    split_targets_individually=condition_effect.split_targets_individually,
                    concentration_anchor_name=condition_effect.concentration_anchor_name,
                ),
            )


    def _apply_group_start_active_effect_save_gate(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        gate: SaveGateEffect,
        point: GridPosition | None,
        start_effect: StartActiveEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        source_actor = self.kernel._require_actor(state, source_actor_id)
        failed_target_ids: list[str] = []
        for target_id in target_ids:
            target = self.kernel._require_target(state, target_id)
            roll_mode = merge_roll_mode(
                advantage=(gate.roll_mode == D20RollMode.ADVANTAGE or (gate.advantage_when_target_hostile_to_source and target.side != source_actor.side)),
                disadvantage=(gate.roll_mode == D20RollMode.DISADVANTAGE),
            )
            if gate.advantage_for_target_sizes and target.size.casefold() in {value.casefold() for value in gate.advantage_for_target_sizes}:
                roll_mode = merge_roll_mode(advantage=True, disadvantage=(roll_mode == D20RollMode.DISADVANTAGE))
            req = SaveRequest(
                context=ResolutionContext(effect_id=capability.capability_id, source_actor_id=source_actor_id, target_actor_id=target_id, reason=capability.name),
                ability=gate.ability,
                dc=self._save_dc(state, source_actor, gate),
                partial_success_margin=gate.partial_success_margin,
                roll_mode=roll_mode,
            )
            resolution, save_events = self.kernel.resolve_save_consumer(state, req, apply=True)
            events.extend(save_events)
            if resolution.branch.value == 'failure':
                failed_target_ids.append(target_id)
        if failed_target_ids:
            self._apply_start_active_effect_def(
                state,
                events,
                source_actor_id=source_actor_id,
                capability=capability,
                target_ids=tuple(failed_target_ids),
                point=point,
                effect=start_effect,
            )

    def _apply_chaining_spell_attack(
        self,
        state: EncounterState,
        events: list[object],
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        target_ids: tuple[str, ...],
        effect: ChainingSpellAttackEffectDef,
        parameters: Mapping[str, str],
    ) -> None:
        if len(target_ids) != 1:
            raise EncounterValidationError('This spell requires exactly one initial target.')
        actor = self.kernel._require_actor(state, source_actor_id)
        default_damage_type = effect.allowed_damage_types[0] if effect.allowed_damage_types else 'acid'
        damage_type = self._parameterized_damage_type(parameters, parameter_key=effect.damage_type_parameter_key, allowed_damage_types=effect.allowed_damage_types, default=default_damage_type)
        queued_jump_targets = list(self._split_parameter_values(parameters.get(effect.chain_parameter_key, '')))
        struck_target_ids: list[str] = []
        current_target_id = target_ids[0]
        for jump_index in range(effect.max_additional_targets + 1):
            attack = AttackProfile(
                attack_id=f'{capability.capability_id}:{jump_index}',
                name=capability.name,
                attack_kind=AttackKind.RANGED if effect.attack_kind == AttackExecutionKind.RANGED_SPELL else AttackKind.MELEE,
                to_hit_bonus=(actor.spell_attack_bonus or 0) + effect.flat_attack_bonus,
                reach_ft=effect.reach_ft,
                range_ft=effect.range_ft,
                long_range_ft=effect.range_ft,
                damage_dice_count=effect.base_dice_count,
                damage_die_faces=effect.damage_die_faces,
                damage_bonus=0,
                damage_type=damage_type,
            )
            hit, critical = self._apply_attack_profile_gate(state, events, source_actor_id=source_actor_id, target_id=current_target_id, capability=capability, attack=attack, magical=effect.magical, damaging=effect.damaging)
            struck_target_ids.append(current_target_id)
            if not hit:
                return
            roll_count = effect.base_dice_count * (2 if critical else 1)
            rolls, total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=roll_count, die_faces=effect.damage_die_faces, bonus=0)
            hp_after, temp_after, applied_damage_total, effect_events = self.kernel._damage_preview(state, self.kernel._require_target(state, current_target_id), total, damage_type=damage_type)
            self._emit(state, events, list(effect_events) + [DamageRolledEvent(actor_id=source_actor_id, attack_id=capability.capability_id, target_id=current_target_id, damage_rolls=rolls, damage_total=total, damage_type=damage_type, random_counter_used=state.random_counter), DamageAppliedEvent(source_actor_id=source_actor_id, target_id=current_target_id, damage_total=total, applied_damage_total=applied_damage_total, target_hit_points_after=hp_after, target_temp_hit_points_after=temp_after, damage_type=damage_type, critical_hit=critical)])
            counts: dict[int, int] = {}
            for roll in rolls:
                counts[roll] = counts.get(roll, 0) + 1
            if jump_index >= effect.max_additional_targets or not counts or max(counts.values()) < effect.duplicate_threshold:
                return
            current_target = self.kernel._require_target(state, current_target_id)
            legal_jump_targets = [
                other.actor_id
                for other in state.actors.values()
                if other.actor_id not in struck_target_ids and not other.is_dead and self.kernel.battlefield_rules.get_distance3d(current_target.position, other.position) <= effect.chain_range_ft
            ]
            if not legal_jump_targets:
                return
            if queued_jump_targets:
                requested = queued_jump_targets.pop(0)
                if requested not in legal_jump_targets:
                    raise EncounterValidationError(f'Invalid chained target {requested!r} for {capability.name}.')
                current_target_id = requested
                continue
            if len(legal_jump_targets) == 1:
                current_target_id = legal_jump_targets[0]
                continue
            raise EncounterValidationError(f'{capability.name} requires --{effect.chain_parameter_key} to choose the chained target.')

    def _apply_save_gate(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, capability: CapabilityDefinition, gate: SaveGateEffect, point: GridPosition | None, active_effect_id: str | None, parameters: Mapping[str, str]) -> None:
        target = self.kernel._require_target(state, target_id)
        roll_mode = merge_roll_mode(
            advantage=(gate.roll_mode == D20RollMode.ADVANTAGE or (gate.advantage_when_target_hostile_to_source and target.side != self.kernel._require_actor(state, source_actor_id).side)),
            disadvantage=(gate.roll_mode == D20RollMode.DISADVANTAGE),
        )
        if gate.advantage_for_target_sizes and target.size.casefold() in {value.casefold() for value in gate.advantage_for_target_sizes}:
            roll_mode = merge_roll_mode(advantage=True, disadvantage=(roll_mode == D20RollMode.DISADVANTAGE))
        req = SaveRequest(context=ResolutionContext(effect_id=(active_effect_id or capability.capability_id), source_actor_id=source_actor_id, target_actor_id=target_id, reason=capability.name), ability=gate.ability, dc=self._save_dc(state, self.kernel._require_actor(state, source_actor_id), gate), partial_success_margin=gate.partial_success_margin, roll_mode=roll_mode)
        resolution, save_events = self.kernel.resolve_save_consumer(state, req, apply=True)
        events.extend(save_events)
        branch = gate.on_failure if resolution.branch.value == 'failure' else gate.on_success if resolution.branch.value == 'success' else gate.on_partial_success
        for child in branch:
            self._execute_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=child, target_ids=(target_id,), point=point, active_effect_id=active_effect_id, critical_hit=False, parameters=parameters)

    def _apply_check_gate(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, capability: CapabilityDefinition, gate: CheckGateEffect, point: GridPosition | None, active_effect_id: str | None) -> None:
        req = CheckRequest(context=ResolutionContext(effect_id=(active_effect_id or capability.capability_id), source_actor_id=source_actor_id, target_actor_id=target_id, reason=capability.name), ability=gate.ability, dc=self._save_dc(state, self.kernel._require_actor(state, source_actor_id), gate), skill_name=gate.skill_name, partial_success_margin=gate.partial_success_margin, requires_sight=gate.requires_sight, requires_hearing=gate.requires_hearing)
        resolution, check_events = self.kernel.resolve_check_consumer(state, req, apply=True)
        events.extend(check_events)
        branch = gate.on_failure if resolution.branch.value == 'failure' else gate.on_success if resolution.branch.value == 'success' else gate.on_partial_success
        for child in branch:
            self._execute_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=child, target_ids=(target_id,), point=point, active_effect_id=active_effect_id, critical_hit=False, parameters={})

    def _apply_forced_movement(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_id: str, effect: ForcedMovementEffectDef, capability: CapabilityDefinition) -> None:
        mode = ForcedMovementMode(effect.mode.value); vector = None
        if effect.vector_mode == ForcedMovementVectorMode.FIXED_VECTOR:
            mode = ForcedMovementMode.REPOSITION
            vector = DisplacementVector(effect.fixed_dx, effect.fixed_dy, effect.fixed_dz)
        forced = ForcedMovementEffect(context=ResolutionContext(effect_id=capability.capability_id, source_actor_id=source_actor_id, target_actor_id=target_id, reason=capability.name), mode=mode, distance_ft=effect.distance_ft, vector=vector)
        result, forced_events = self.kernel.apply_forced_movement(state, forced, apply=True)
        events.extend(forced_events)
        self._emit(state, events, [ForcedMovementAppliedEvent(actor_id=source_actor_id, target_id=target_id, final_position=result.final_position, moved_distance_ft=result.moved_distance_ft)])

    def _apply_teleport(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, effect: TeleportEffectDef, point: GridPosition | None) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        if point is None:
            raise EncounterValidationError('This teleport requires a destination point.')
        legality = self.kernel.battlefield_rules.teleport_legality(state, actor, point, range_ft=capability.targeting.range_ft, requires_visible_destination=effect.requires_visible_destination, requires_unoccupied_destination=effect.requires_unoccupied_destination, requires_line_of_effect=effect.requires_line_of_effect)
        if not legality.destination_legal or not legality.within_range:
            raise EncounterValidationError(legality.detail)
        self._emit(state, events, [TeleportDeclaredEvent(actor_id=source_actor_id, spell_id=capability.capability_id, from_position=actor.position, to_position=point, distance_ft=legality.distance_ft), TeleportResolvedEvent(actor_id=source_actor_id, spell_id=capability.capability_id, from_position=actor.position, to_position=point, distance_ft=legality.distance_ft), RelocationResolvedEvent(actor_id=source_actor_id, from_position=actor.position, to_position=point, relocation_type=RelocationType.TELEPORT, movement_mode=TraversalMode.TELEPORT), PositionChangedEvent(actor_id=source_actor_id, from_position=actor.position, to_position=point, relocation_type=RelocationType.TELEPORT, movement_mode=TraversalMode.TELEPORT)])

    def _create_terrain_effect(self, state: EncounterState, events: list[object], *, source_actor_id: str, capability: CapabilityDefinition, effect: CreateTerrainEffectDef, point: GridPosition | None) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        if point is None:
            raise EncounterValidationError('This capability requires a point for terrain creation.')
        self._validate_point_target(state, actor=actor, point=point, spec=capability.targeting)
        feature_id = f"{capability.capability_id}:{source_actor_id}:{state.round_number}:{state.turn_index}:{len(state.event_log)}"
        self._emit(state, events, [TerrainEffectCreatedEvent(feature_id=feature_id, template_id=effect.template_id, anchor=point)])

    def _start_active_effect(self, state: EncounterState, events: list[object], *, source_actor_id: str, target_ids: tuple[str, ...], capability: CapabilityDefinition, definition: ActiveEffectDefinition, point: GridPosition | None, metadata: tuple[tuple[str, str], ...] = ()) -> None:
        source = self.kernel._require_actor(state, source_actor_id)
        if definition.replace_existing_same_name_from_source:
            for existing_effect_id, existing in tuple(state.active_effects.items()):
                if existing.source_actor_id == source_actor_id and existing.name == definition.name:
                    self._end_active_effect(state, events, effect_id=existing_effect_id, reason='replaced')
        if definition.concentration and source.concentrating_effect_id is not None:
            self._end_active_effect(state, events, effect_id=source.concentrating_effect_id, reason='replaced')
        effect_id = f'{capability.capability_id}:{source_actor_id}:{state.round_number}:{state.turn_index}:{len(state.event_log)}'
        anchor_actor_id = source_actor_id if definition.duration.anchor == DurationAnchor.SOURCE else (target_ids[0] if target_ids else source_actor_id)
        anchor_position = point or source.position
        active = ActiveEffectState(
            effect_instance_id=effect_id,
            capability_id=capability.capability_id,
            name=definition.name,
            source_actor_id=source_actor_id,
            target_actor_ids=target_ids,
            definition=definition,
            metadata=metadata,
            started_round_number=state.round_number,
            started_turn_actor_id=state.active_actor_id,
            duration_anchor_actor_id=anchor_actor_id,
            remaining_rounds=definition.duration.rounds,
            origin_point=point,
        )
        start_events: list[object] = [ActiveEffectStartedEvent(effect=active)]
        if definition.concentration:
            start_events.append(ConcentrationStartedEvent(actor_id=source_actor_id, effect_instance_id=effect_id))
        for target_id in target_ids:
            if definition.armor_class_bonus:
                start_events.append(ArmorClassAdjustedEvent(actor_id=target_id, effect_instance_id=effect_id, delta=definition.armor_class_bonus, reason=definition.name))
            if definition.max_hit_points_bonus:
                start_events.append(HitPointMaximumAdjustedEvent(actor_id=target_id, effect_instance_id=effect_id, delta=definition.max_hit_points_bonus, adjust_current_by_same_delta=True, reason=definition.name))
        self._emit(state, events, start_events)

        persistent_events: list[object] = []
        for index, summon in enumerate(definition.summoned_creatures):
            persistent, summon_state = self._start_summoned_creature(
                source_actor_id=source_actor_id,
                target_ids=target_ids,
                capability=capability,
                source_effect_id=effect_id,
                anchor_position=anchor_position,
                definition=summon,
                index=index,
            )
            persistent_events.append(PersistentEffectStartedEvent(persistent_effect=persistent))
            persistent_events.append(CreatedCreatureSpawnedEvent(creature=summon_state))
        for index, created_object in enumerate(definition.created_objects):
            persistent, created_object_state = self._start_created_object(
                source_actor_id=source_actor_id,
                capability=capability,
                source_effect_id=effect_id,
                anchor_position=anchor_position,
                definition=created_object,
                index=index,
            )
            persistent_events.append(PersistentEffectStartedEvent(persistent_effect=persistent))
            persistent_events.append(CreatedObjectSpawnedEvent(created_object=created_object_state))
        for index, illusion in enumerate(definition.illusions):
            persistent, illusion_state = self._start_illusion(
                source_actor_id=source_actor_id,
                target_ids=target_ids,
                capability=capability,
                source_effect_id=effect_id,
                anchor_position=anchor_position,
                definition=illusion,
                index=index,
            )
            persistent_events.append(PersistentEffectStartedEvent(persistent_effect=persistent))
            persistent_events.append(IllusionCreatedEvent(illusion=illusion_state))
        for index, payload in enumerate(definition.information_payloads):
            persistent, payload_state = self._start_information_payload(
                source_actor_id=source_actor_id,
                target_ids=target_ids,
                capability=capability,
                source_effect_id=effect_id,
                anchor_position=anchor_position,
                definition=payload,
                index=index,
            )
            persistent_events.append(PersistentEffectStartedEvent(persistent_effect=persistent))
            if payload.kind == InformationPayloadKind.DETECTION:
                persistent_events.append(DetectionPayloadProducedEvent(payload=payload_state))
            else:
                persistent_events.append(DivinationPayloadProducedEvent(payload=payload_state))
        for index, area in enumerate(definition.persistent_areas):
            persistent, area_state = self._start_persistent_area(
                source_actor_id=source_actor_id,
                target_ids=target_ids,
                capability=capability,
                source_effect_id=effect_id,
                anchor_position=anchor_position,
                definition=area,
                index=index,
            )
            persistent_events.append(PersistentEffectStartedEvent(persistent_effect=persistent))
            persistent_events.append(PersistentAreaCreatedEvent(area=area_state))
        if persistent_events:
            self._emit(state, events, persistent_events)
        for child in definition.on_start:
            self._execute_effect(state, events, source_actor_id=source_actor_id, capability=capability, effect=child, target_ids=target_ids, point=point, active_effect_id=effect_id, critical_hit=False, parameters={})

    def _persistent_effect_base(
        self,
        *,
        persistent_effect_id: str,
        family: PersistentEffectFamily,
        source_effect_id: str,
        source_actor_id: str,
        capability_id: str,
        anchor_position: GridPosition,
        observer_mode: PersistentObserverMode,
        observer_actor_ids: tuple[str, ...] = (),
    ) -> PersistentEffectState:
        return PersistentEffectState(
            persistent_effect_id=persistent_effect_id,
            family=family,
            source_effect_id=source_effect_id,
            source_capability_id=capability_id,
            source_actor_id=source_actor_id,
            owner_actor_id=source_actor_id,
            owner_controller_id=None,
            anchor_position=anchor_position,
            observer_mode=observer_mode,
            observer_actor_ids=observer_actor_ids,
        )

    def _observer_actor_ids(self, *, observer_mode: PersistentObserverMode, configured_observers: tuple[str, ...], target_ids: tuple[str, ...]) -> tuple[str, ...]:
        if observer_mode == PersistentObserverMode.TARGETS_ONLY:
            return target_ids
        if observer_mode == PersistentObserverMode.SELECTED_OBSERVERS:
            return configured_observers
        return ()

    def _start_summoned_creature(
        self,
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        source_effect_id: str,
        anchor_position: GridPosition,
        definition: SummonedCreatureDefinition,
        index: int,
    ) -> tuple[PersistentEffectState, SummonedCreatureState]:
        summon_id = f'{source_effect_id}:summon:{index}'
        observer_actor_ids = self._observer_actor_ids(
            observer_mode=definition.observer_filter.observer_mode,
            configured_observers=definition.observer_filter.observer_actor_ids,
            target_ids=target_ids,
        )
        persistent = self._persistent_effect_base(
            persistent_effect_id=summon_id,
            family=PersistentEffectFamily.SUMMONED_CREATURE,
            source_effect_id=source_effect_id,
            source_actor_id=source_actor_id,
            capability_id=capability.capability_id,
            anchor_position=anchor_position,
            observer_mode=definition.observer_filter.observer_mode,
            observer_actor_ids=observer_actor_ids,
        )
        return persistent, SummonedCreatureState(
            persistent=persistent,
            summon_id=summon_id,
            definition=definition,
            position=anchor_position,
            linked_actor_id=None,
        )

    def _start_created_object(
        self,
        *,
        source_actor_id: str,
        capability: CapabilityDefinition,
        source_effect_id: str,
        anchor_position: GridPosition,
        definition: CreatedObjectDefinition,
        index: int,
    ) -> tuple[PersistentEffectState, CreatedObjectState]:
        object_id = f'{source_effect_id}:object:{index}'
        persistent = self._persistent_effect_base(
            persistent_effect_id=object_id,
            family=PersistentEffectFamily.CREATED_OBJECT,
            source_effect_id=source_effect_id,
            source_actor_id=source_actor_id,
            capability_id=capability.capability_id,
            anchor_position=anchor_position,
            observer_mode=PersistentObserverMode.ALL_VALID_OBSERVERS,
        )
        linked_feature_id = f'{object_id}:feature' if definition.physical else None
        return persistent, CreatedObjectState(
            persistent=persistent,
            object_id=object_id,
            definition=definition,
            cells=footprint_cells(anchor_position, definition.footprint),
            linked_feature_id=linked_feature_id,
        )

    def _start_illusion(
        self,
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        source_effect_id: str,
        anchor_position: GridPosition,
        definition: IllusionDefinition,
        index: int,
    ) -> tuple[PersistentEffectState, IllusionState]:
        illusion_id = f'{source_effect_id}:illusion:{index}'
        observer_actor_ids = self._observer_actor_ids(
            observer_mode=definition.observer_filter.observer_mode,
            configured_observers=definition.observer_filter.observer_actor_ids,
            target_ids=target_ids,
        )
        persistent = self._persistent_effect_base(
            persistent_effect_id=illusion_id,
            family=PersistentEffectFamily.ILLUSION,
            source_effect_id=source_effect_id,
            source_actor_id=source_actor_id,
            capability_id=capability.capability_id,
            anchor_position=anchor_position,
            observer_mode=definition.observer_filter.observer_mode,
            observer_actor_ids=observer_actor_ids,
        )
        observer_states = {observer_id: IllusionObserverState(observer_id=observer_id) for observer_id in observer_actor_ids}
        return persistent, IllusionState(
            persistent=persistent,
            illusion_id=illusion_id,
            definition=definition,
            cells=rectangular_cells(anchor_position, width_ft=definition.width_ft, depth_ft=definition.depth_ft),
            observer_states=observer_states,
        )

    def _start_information_payload(
        self,
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        source_effect_id: str,
        anchor_position: GridPosition,
        definition: InformationPayloadDefinition,
        index: int,
    ) -> tuple[PersistentEffectState, InformationalPayloadState]:
        payload_id = f'{source_effect_id}:payload:{index}'
        observer_actor_ids = self._observer_actor_ids(
            observer_mode=definition.observer_filter.observer_mode,
            configured_observers=definition.observer_filter.observer_actor_ids,
            target_ids=target_ids,
        )
        persistent = self._persistent_effect_base(
            persistent_effect_id=payload_id,
            family=PersistentEffectFamily.INFORMATION_PAYLOAD,
            source_effect_id=source_effect_id,
            source_actor_id=source_actor_id,
            capability_id=capability.capability_id,
            anchor_position=anchor_position,
            observer_mode=definition.observer_filter.observer_mode,
            observer_actor_ids=observer_actor_ids,
        )
        return persistent, InformationalPayloadState(
            persistent=persistent,
            payload_id=payload_id,
            definition=definition,
        )

    def _start_persistent_area(
        self,
        *,
        source_actor_id: str,
        target_ids: tuple[str, ...],
        capability: CapabilityDefinition,
        source_effect_id: str,
        anchor_position: GridPosition,
        definition: PersistentAreaDefinition,
        index: int,
    ) -> tuple[PersistentEffectState, PersistentAreaState]:
        area_id = f'{source_effect_id}:area:{index}'
        observer_actor_ids = self._observer_actor_ids(
            observer_mode=definition.observer_filter.observer_mode,
            configured_observers=definition.observer_filter.observer_actor_ids,
            target_ids=target_ids,
        )
        persistent = self._persistent_effect_base(
            persistent_effect_id=area_id,
            family=PersistentEffectFamily.PERSISTENT_AREA,
            source_effect_id=source_effect_id,
            source_actor_id=source_actor_id,
            capability_id=capability.capability_id,
            anchor_position=anchor_position,
            observer_mode=definition.observer_filter.observer_mode,
            observer_actor_ids=observer_actor_ids,
        )
        origins = tuple(
            GridPosition(anchor_position.x + dx, anchor_position.y + dy, anchor_position.z + dz)
            for dx, dy, dz in (definition.relative_origins or ((0, 0, 0),))
        )
        return persistent, PersistentAreaState(
            persistent=persistent,
            area_id=area_id,
            definition=definition,
            origin=anchor_position,
            origins=origins,
        )
    def _resolve_ongoing_trigger(self, state: EncounterState, events: list[object], *, effect: ActiveEffectState, trigger: OngoingTriggerDefinition, trigger_actor_id: str) -> None:
        if trigger.timing == TriggerTiming.START_OF_TURN and trigger_actor_id in effect.target_actor_ids:
            total_temp_hit_points = effect.definition.start_of_turn_temp_hit_points
            if effect.definition.start_of_turn_temp_hit_points_bonus_source == HealingBonusSource.ACTOR_SPELLCASTING_MODIFIER:
                source_actor = self.kernel._require_actor(state, effect.source_actor_id)
                if source_actor.spellcasting_ability is None:
                    raise EncounterValidationError('The acting actor does not have a spellcasting ability for this ongoing effect.')
                total_temp_hit_points += source_actor.ability_modifiers[source_actor.spellcasting_ability]
            if total_temp_hit_points > 0:
                self._emit(
                    state,
                    events,
                    [TemporaryHitPointsAppliedEvent(source_actor_id=effect.source_actor_id, target_id=trigger_actor_id, temp_hit_points_total=total_temp_hit_points)],
                )
        if effect.name.startswith('Command:'):
            self._apply_command_trigger(state, events, effect=effect, trigger_actor_id=trigger_actor_id)
        for child in trigger.on_trigger:
            self._execute_effect(state, events, source_actor_id=effect.source_actor_id, capability=CapabilityDefinition(capability_id=effect.capability_id, name=effect.name, kind=CapabilityKind.SPELL, source='ACTIVE_EFFECT', action_cost='none', targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE), effect=child), effect=child, target_ids=(trigger_actor_id,), point=effect.origin_point, active_effect_id=effect.effect_instance_id, critical_hit=False, parameters={})
        if trigger.save_ability is None:
            return
        req = SaveRequest(context=ResolutionContext(effect_id=effect.effect_instance_id, source_actor_id=effect.source_actor_id, target_actor_id=trigger_actor_id, reason=effect.name), ability=trigger.save_ability, dc=self._save_dc(state, self.kernel._require_actor(state, effect.source_actor_id), trigger), roll_mode=trigger.save_roll_mode)
        resolution, save_events = self.kernel.resolve_save_consumer(state, req, apply=True)
        events.extend(save_events)
        branch_effects = trigger.on_success if resolution.branch.value == 'success' else trigger.on_failure
        for child in branch_effects:
            self._execute_effect(state, events, source_actor_id=effect.source_actor_id, capability=CapabilityDefinition(capability_id=effect.capability_id, name=effect.name, kind=CapabilityKind.SPELL, source='ACTIVE_EFFECT', action_cost='none', targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE), effect=child), effect=child, target_ids=(trigger_actor_id,), point=effect.origin_point, active_effect_id=effect.effect_instance_id, critical_hit=False, parameters={})
        if resolution.branch.value == 'success' and trigger.end_effect_on_success:
            self._end_active_effect(state, events, effect_id=effect.effect_instance_id, reason='trigger-save-success')
        if resolution.branch.value == 'failure' and trigger.end_effect_on_failure:
            self._end_active_effect(state, events, effect_id=effect.effect_instance_id, reason='trigger-save-failure')

    def _effect_expires_at_boundary(self, state: EncounterState, effect: ActiveEffectState, *, actor_id: str, timing: TriggerTiming) -> bool:
        duration = effect.definition.duration
        if effect.duration_anchor_actor_id != actor_id:
            return False
        if duration.duration_type == EffectDurationType.UNTIL_START_OF_NEXT_TURN:
            return timing == TriggerTiming.START_OF_TURN and (state.round_number > effect.started_round_number or effect.started_turn_actor_id != actor_id)
        if duration.duration_type == EffectDurationType.UNTIL_END_OF_NEXT_TURN:
            return timing == TriggerTiming.END_OF_TURN and (state.round_number > effect.started_round_number or effect.started_turn_actor_id != actor_id)
        if duration.duration_type == EffectDurationType.ROUNDS and duration.rounds is not None:
            return timing == TriggerTiming.END_OF_TURN and state.round_number >= effect.started_round_number + duration.rounds - 1
        return False

    def _trigger_targets(self, effect: ActiveEffectState, *, actor_id: str, scope: TriggerActorScope) -> tuple[str, ...]:
        return (effect.source_actor_id,) if scope == TriggerActorScope.SOURCE and effect.source_actor_id == actor_id else ((actor_id,) if scope == TriggerActorScope.EACH_TARGET and actor_id in effect.target_actor_ids else ())


    def resolve_persistent_area_transition(
        self,
        state: EncounterState,
        *,
        area: PersistentAreaState,
        actor_id: str,
        entering: bool,
    ) -> list[object]:
        work = copy.deepcopy(state)
        events: list[object] = []
        effects = area.definition.entry_effects if entering else area.definition.exit_effects
        if not effects:
            return []
        capability = CapabilityDefinition(
            capability_id=area.persistent.source_capability_id,
            name=area.definition.name,
            kind=CapabilityKind.SPELL,
            source='PERSISTENT',
            action_cost='none',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE),
            effect=effects[0],
        )
        for child in effects:
            self._execute_effect(
                work,
                events,
                source_actor_id=area.persistent.source_actor_id,
                capability=capability,
                effect=child,
                target_ids=(actor_id,),
                point=area.origin,
                active_effect_id=area.persistent.source_effect_id,
                critical_hit=False,
                parameters={},
            )
        return events

    def _end_active_effect(self, state: EncounterState, events: list[object], *, effect_id: str, reason: str) -> None:
        effect = state.active_effects.get(effect_id)
        if effect is None:
            return
        for child in effect.definition.on_end:
            self._execute_effect(
                state,
                events,
                source_actor_id=effect.source_actor_id,
                capability=CapabilityDefinition(capability_id=effect.capability_id, name=effect.name, kind=CapabilityKind.SPELL, source='ACTIVE_EFFECT', action_cost='none', targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE), effect=child),
                effect=child,
                target_ids=(effect.target_actor_ids[0],) if effect.target_actor_ids else (effect.source_actor_id,),
                point=effect.origin_point,
                active_effect_id=effect.effect_instance_id,
                critical_hit=False,
                parameters={},
            )
        for actor in state.actors.values():
            for instance in actor.condition_instances:
                if instance.source_effect_id == effect_id:
                    self._emit(state, events, [self.kernel._condition_removed_event_for_instance(actor.actor_id, instance.instance_id)])
        for target_id in effect.target_actor_ids:
            if effect.definition.armor_class_bonus:
                self._emit(state, events, [ArmorClassAdjustedEvent(actor_id=target_id, effect_instance_id=effect_id, delta=-effect.definition.armor_class_bonus, reason=reason)])
            if effect.definition.max_hit_points_bonus:
                self._emit(state, events, [HitPointMaximumAdjustedEvent(actor_id=target_id, effect_instance_id=effect_id, delta=-effect.definition.max_hit_points_bonus, adjust_current_by_same_delta=True, reason=reason)])

        cleanup_events: list[object] = []
        for summon in tuple(state.summoned_creatures.values()):
            if summon.persistent.source_effect_id != effect_id:
                continue
            cleanup_events.append(CreatedCreatureRemovedEvent(summon_id=summon.summon_id, reason=reason))
            cleanup_events.append(PersistentEffectEndedEvent(persistent_effect_id=summon.persistent.persistent_effect_id, family=PersistentEffectFamily.SUMMONED_CREATURE, reason=reason))
        for created_object in tuple(state.created_objects.values()):
            if created_object.persistent.source_effect_id != effect_id:
                continue
            cleanup_events.append(CreatedObjectRemovedEvent(object_id=created_object.object_id, reason=reason))
            cleanup_events.append(PersistentEffectEndedEvent(persistent_effect_id=created_object.persistent.persistent_effect_id, family=PersistentEffectFamily.CREATED_OBJECT, reason=reason))
        for illusion in tuple(state.illusions.values()):
            if illusion.persistent.source_effect_id != effect_id:
                continue
            cleanup_events.append(PersistentEffectEndedEvent(persistent_effect_id=illusion.persistent.persistent_effect_id, family=PersistentEffectFamily.ILLUSION, reason=reason))
        for payload in tuple(state.informational_payloads.values()):
            if payload.persistent.source_effect_id != effect_id:
                continue
            cleanup_events.append(PersistentEffectEndedEvent(persistent_effect_id=payload.persistent.persistent_effect_id, family=PersistentEffectFamily.INFORMATION_PAYLOAD, reason=reason))
        for area in tuple(state.persistent_areas.values()):
            if area.persistent.source_effect_id != effect_id:
                continue
            cleanup_events.append(PersistentAreaEndedEvent(area_id=area.area_id, reason=reason))
            cleanup_events.append(PersistentEffectEndedEvent(persistent_effect_id=area.persistent.persistent_effect_id, family=PersistentEffectFamily.PERSISTENT_AREA, reason=reason))
        if cleanup_events:
            self._emit(state, events, cleanup_events)

        if self.kernel._require_actor(state, effect.source_actor_id).concentrating_effect_id == effect_id:
            self._emit(state, events, [ConcentrationEndedEvent(actor_id=effect.source_actor_id, effect_instance_id=effect_id, reason=reason)])
        self._emit(state, events, [ActiveEffectEndedEvent(effect_instance_id=effect_id, reason=reason)])
    def _emit(self, state: EncounterState, events: list[object], new_events: list[object]) -> None:
        for event in new_events:
            self.kernel._apply_event(state, event)
            events.append(event)

    def _spell_attack_roll_advantage(self, state: EncounterState, *, actor_id: str) -> bool:
        return any(
            actor_id in effect.target_actor_ids and effect.definition.spell_attack_roll_advantage
            for effect in state.active_effects.values()
        )

    def _spell_save_dc_bonus(self, state: EncounterState, *, actor_id: str) -> int:
        return sum(
            effect.definition.spell_save_dc_bonus
            for effect in state.active_effects.values()
            if actor_id in effect.target_actor_ids and effect.definition.spell_save_dc_bonus
        )

    def _attack_bonus(self, actor: RuntimeActorState, gate: AttackRollGateEffect) -> int:
        if gate.attack_bonus_source == AttackBonusSource.FLAT:
            return gate.flat_attack_bonus
        if gate.attack_bonus_source == AttackBonusSource.ACTOR_ABILITY_MODIFIER:
            if gate.attack_ability is None:
                raise EncounterValidationError('The capability is missing its attack ability.')
            ability_bonus = actor.ability_modifiers[gate.attack_ability]
            if gate.include_proficiency:
                ability_bonus += actor.proficiency_bonus
            return ability_bonus + gate.flat_attack_bonus
        if actor.spell_attack_bonus is None:
            raise EncounterValidationError('The acting actor does not have a spell attack bonus for this capability.')
        return actor.spell_attack_bonus + gate.flat_attack_bonus

    def _healing_bonus(self, actor: RuntimeActorState, effect: HealingEffectDef) -> int:
        if effect.bonus_source == HealingBonusSource.FLAT:
            return 0
        if effect.bonus_source == HealingBonusSource.ACTOR_LEVEL:
            return actor.level
        if actor.spellcasting_ability is None:
            raise EncounterValidationError('The acting actor does not have a spellcasting ability for this healing effect.')
        return actor.ability_modifiers[actor.spellcasting_ability]

    def _save_dc(self, state: EncounterState, actor: RuntimeActorState, gate: SaveGateEffect | GroupSaveGateEffectDef | CheckGateEffect | OngoingTriggerDefinition) -> int:
        dc_source = (gate.save_dc_source if isinstance(gate, OngoingTriggerDefinition) else gate.dc_source)
        if dc_source == SaveDcSource.FLAT:
            if gate.flat_dc is None:
                raise EncounterValidationError('The capability is missing a flat DC.')
            return gate.flat_dc
        if actor.spell_save_dc is None:
            raise EncounterValidationError('The acting actor does not have a spell save DC for this capability.')
        return actor.spell_save_dc + self._spell_save_dc_bonus(state, actor_id=actor.actor_id)

    def _matches_affinity(self, actor: RuntimeActorState, target: RuntimeActorState, affinity: TargetAffinity) -> bool:
        if affinity == TargetAffinity.ANY:
            return True
        if affinity == TargetAffinity.SELF_ONLY:
            return actor.actor_id == target.actor_id
        if affinity == TargetAffinity.ALLY:
            return actor.side == target.side
        if affinity == TargetAffinity.ENEMY:
            return actor.side != target.side
        return False

    def _effect_is_damaging(self, effect: EffectDefinition) -> bool:
        if isinstance(effect, DamageEffectDef):
            return True
        if isinstance(effect, CompositeEffect):
            return any(self._effect_is_damaging(child) for child in effect.effects)
        if isinstance(effect, AttackRollGateEffect):
            return True
        if isinstance(effect, SaveGateEffect):
            return any(self._effect_is_damaging(child) for child in effect.on_success + effect.on_failure + effect.on_partial_success)
        if isinstance(effect, CheckGateEffect):
            return any(self._effect_is_damaging(child) for child in effect.on_success + effect.on_failure + effect.on_partial_success)
        if isinstance(effect, StartActiveEffectDef):
            return any(self._effect_is_damaging(child) for child in effect.active_effect.on_start + effect.active_effect.on_end)
        return False













