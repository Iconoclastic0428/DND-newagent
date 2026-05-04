from __future__ import annotations

from typing import TYPE_CHECKING

from rules_engine.encounter_math import roll_damage
from rules_engine.rng import seeded_random
from shared_types.battlefield import FallReason, OccupiedVolume
from shared_types.effects import (
    CheckRequest,
    CheckResolution,
    ConditionApplication,
    DisplacementVector,
    EffectResolutionBranch,
    ForcedMovementEffect,
    ForcedMovementMode,
    ForcedMovementResult,
    ForcedMovementStopReason,
    HazardResolutionRequest,
    HazardResolutionResult,
    LiquidEntryMitigationChoice,
    LiquidEntryMitigationResolution,
    SaveRequest,
    SaveResolution,
)
from shared_types.encounter_events import (
    CheckFailedEvent,
    CheckRequestedEvent,
    CheckRolledEvent,
    CheckSucceededEvent,
    DamageAppliedEvent,
    DamageRolledEvent,
    FallMitigationCheckOfferedEvent,
    FallMitigationCheckResolvedEvent,
    ForcedMovementStartedEvent,
    ForcedMovementStepResolvedEvent,
    ForcedMovementStoppedEvent,
    HazardResolvedEvent,
    HazardTriggeredEvent,
    LiquidEntryDetectedEvent,
    ResourceSpentEvent,
    SaveFailedEvent,
    SaveRequestedEvent,
    SaveRolledEvent,
    SaveSucceededEvent,
)
from shared_types.encounter_models import EncounterState, GridPosition, RuntimeActorState
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability

from .conditions import can_take_reactions, get_condition_state

if TYPE_CHECKING:
    from .kernel import EncounterKernel


class EncounterEffectConsumers:
    def __init__(self, *, kernel: 'EncounterKernel') -> None:
        self.kernel = kernel

    def resolve_save(self, state: EncounterState, request: SaveRequest, *, apply: bool = False) -> tuple[SaveResolution, list[object]]:
        actor = self.kernel._require_actor(state, request.context.target_actor_id)
        events: list[object] = [SaveRequestedEvent(request=request)]
        effect_modifier, effect_events = self.kernel._saving_throw_effect_modifier(state, actor_id=actor.actor_id)
        events.extend(effect_events)
        resolution = self.kernel.resolve_saving_throw(
            state,
            actor_id=actor.actor_id,
            ability=request.ability,
            dc=request.dc,
            flat_modifier=request.flat_modifier + effect_modifier,
            roll_mode=request.roll_mode,
        )
        branch = self._select_branch(resolution.result.success, resolution.result.total, request.dc, request.partial_success_margin)
        save_resolution = SaveResolution(request=request, result=resolution.result, branch=branch)
        events.append(SaveRolledEvent(resolution=save_resolution, random_counter_used=resolution.random_counter_used))
        events.append(SaveSucceededEvent(resolution=save_resolution) if branch == EffectResolutionBranch.SUCCESS else SaveFailedEvent(resolution=save_resolution))
        if apply:
            self._apply_events(state, events)
        return save_resolution, events

    def resolve_check(self, state: EncounterState, request: CheckRequest, *, apply: bool = False) -> tuple[CheckResolution, list[object]]:
        actor = self.kernel._require_actor(state, request.context.target_actor_id)
        modifier_bonus, modifier_events = self.kernel._ability_check_effect_modifier(state, actor_id=actor.actor_id, skill_name=request.skill_name)
        events: list[object] = [CheckRequestedEvent(request=request), *modifier_events]
        resolution = self.kernel.resolve_ability_check(
            state,
            actor_id=actor.actor_id,
            ability=request.ability,
            dc=request.dc,
            flat_modifier=request.flat_modifier + modifier_bonus,
            requires_sight=request.requires_sight,
            requires_hearing=request.requires_hearing,
            interacting_with_actor_id=request.interacting_with_actor_id,
            skill_name=request.skill_name,
            roll_mode=request.roll_mode,
        )
        branch = self._select_branch(resolution.result.success, resolution.result.total, request.dc, request.partial_success_margin)
        check_resolution = CheckResolution(request=request, result=resolution.result, branch=branch)
        events.append(CheckRolledEvent(resolution=check_resolution, random_counter_used=resolution.random_counter_used))
        events.append(CheckSucceededEvent(resolution=check_resolution) if branch == EffectResolutionBranch.SUCCESS else CheckFailedEvent(resolution=check_resolution))
        if apply:
            self._apply_events(state, events)
        return check_resolution, events

    def apply_forced_movement(
        self,
        state: EncounterState,
        effect: ForcedMovementEffect,
        *,
        liquid_choice: LiquidEntryMitigationChoice | None = None,
        apply: bool = True,
    ) -> tuple[ForcedMovementResult, list[object]]:
        actor = self.kernel._require_actor(state, effect.context.target_actor_id)
        origin = actor.position
        positions = self._candidate_positions(state, actor, effect)
        events: list[object] = [ForcedMovementStartedEvent(effect=effect, from_position=origin)]
        path: list[GridPosition] = []
        moved_distance_ft = 0
        stop_reason = ForcedMovementStopReason.COMPLETED
        entered_liquid = False
        caused_fall = False
        current_position = origin
        for index, next_position in enumerate(positions, start=1):
            stop_reason = self._forced_movement_stop_reason(state, actor, next_position)
            if stop_reason is not None:
                break
            step_event = ForcedMovementStepResolvedEvent(
                actor_id=actor.actor_id,
                from_position=current_position,
                to_position=next_position,
                step_distance_ft=5,
                step_index=index,
            )
            events.append(step_event)
            if apply:
                self.kernel._apply_event(state, step_event)
            path.append(next_position)
            moved_distance_ft += 5
            current_position = next_position
            if self.kernel.battlefield_rules.is_liquid_position(state, next_position):
                entered_liquid = True
            support_events = self.kernel._support_reconciliation_events(
                state,
                actor_id=actor.actor_id,
                reason=FallReason.FORCED_RELOCATION,
                liquid_choice=liquid_choice,
            )
            if any(type(event).__name__ == 'FallStartedEvent' for event in support_events):
                caused_fall = True
            if apply:
                self._apply_events(state, support_events)
            events.extend(support_events)
            if caused_fall:
                stop_reason = ForcedMovementStopReason.ENTERED_UNSUPPORTED_SPACE
                break
            if entered_liquid:
                stop_reason = ForcedMovementStopReason.ENTERED_LIQUID
                break
        else:
            stop_reason = ForcedMovementStopReason.COMPLETED
        result = ForcedMovementResult(
            effect=effect,
            path=tuple(path),
            final_position=state.actors[actor.actor_id].position if apply else current_position,
            moved_distance_ft=moved_distance_ft,
            stop_reason=stop_reason,
            entered_liquid=entered_liquid,
            caused_fall=caused_fall,
        )
        stopped_event = ForcedMovementStoppedEvent(result=result)
        events.append(stopped_event)
        if apply:
            self.kernel._apply_event(state, stopped_event)
        return result, events

    def resolve_hazard(
        self,
        state: EncounterState,
        request: HazardResolutionRequest,
        *,
        liquid_choice: LiquidEntryMitigationChoice | None = None,
        apply: bool = True,
    ) -> tuple[HazardResolutionResult, list[object]]:
        actor = self.kernel._require_actor(state, request.context.target_actor_id)
        events: list[object] = [HazardTriggeredEvent(request=request)]
        if apply:
            self.kernel._apply_event(state, events[0])
        save_resolution = None
        check_resolution = None
        branch: EffectResolutionBranch | None = None
        if request.save_request is not None:
            save_resolution, save_events = self.resolve_save(state, request.save_request, apply=apply)
            events.extend(save_events)
            branch = save_resolution.branch
        elif request.check_request is not None:
            check_resolution, check_events = self.resolve_check(state, request.check_request, apply=apply)
            events.extend(check_events)
            branch = check_resolution.branch
        outcome = self._branch_outcome(request, branch)
        forced_movement_result = None
        if outcome is not None:
            damage_total = 0
            if outcome.damage is not None:
                rng = seeded_random(self.kernel.seed, state.random_counter)
                damage_rolls, damage_total = roll_damage(
                    rng,
                    dice_count=outcome.damage.dice_count,
                    die_faces=outcome.damage.die_faces,
                    bonus=outcome.damage.bonus,
                )
                if outcome.damage_divisor > 1:
                    damage_total //= outcome.damage_divisor
                hit_points_after, temp_hit_points_after, applied_damage_total = self.kernel._damage_preview(actor, damage_total, damage_type=outcome.damage.damage_type)
                damage_events = [
                    DamageRolledEvent(
                        actor_id=request.context.source_actor_id or actor.actor_id,
                        attack_id=None,
                        target_id=actor.actor_id,
                        damage_rolls=damage_rolls,
                        damage_total=damage_total,
                        damage_type=outcome.damage.damage_type,
                        random_counter_used=state.random_counter,
                    ),
                    DamageAppliedEvent(
                        source_actor_id=request.context.source_actor_id or actor.actor_id,
                        target_id=actor.actor_id,
                        damage_total=damage_total,
                        applied_damage_total=applied_damage_total,
                        target_hit_points_after=hit_points_after,
                        target_temp_hit_points_after=temp_hit_points_after,
                        damage_type=outcome.damage.damage_type,
                    ),
                ]
                events.extend(damage_events)
                if apply:
                    self._apply_events(state, damage_events)
            if outcome.conditions:
                condition_events = []
                for application in outcome.conditions:
                    condition_events.append(
                        self.kernel._condition_added_event_from_application(
                            target_actor_id=actor.actor_id,
                            application=application,
                        )
                    )
                events.extend(condition_events)
                if apply:
                    self._apply_events(state, condition_events)
            if outcome.forced_movement is not None:
                forced_movement_result, forced_events = self.apply_forced_movement(
                    state,
                    outcome.forced_movement,
                    liquid_choice=liquid_choice,
                    apply=apply,
                )
                events.extend(forced_events)
        result = HazardResolutionResult(
            request=request,
            branch=branch,
            save_resolution=save_resolution,
            check_resolution=check_resolution,
            forced_movement_result=forced_movement_result,
        )
        resolved_event = HazardResolvedEvent(result=result)
        events.append(resolved_event)
        if apply:
            self.kernel._apply_event(state, resolved_event)
        return result, events

    def resolve_liquid_entry_mitigation(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        choice: LiquidEntryMitigationChoice | None,
        damage_total: int,
    ) -> tuple[LiquidEntryMitigationResolution, list[object]]:
        actor = self.kernel._require_actor(state, actor_id)
        reaction_available = actor.reaction_available and can_take_reactions(actor)
        offered_event = FallMitigationCheckOfferedEvent(actor_id=actor.actor_id, reaction_available=reaction_available, dc=(choice.dc if choice is not None else 15))
        events: list[object] = [offered_event]
        if choice is None or not choice.attempt or not reaction_available:
            resolution = LiquidEntryMitigationResolution(used_reaction=False, success=False, damage_before=damage_total, damage_after=damage_total, check_resolution=None)
            events.append(FallMitigationCheckResolvedEvent(actor_id=actor.actor_id, resolution=resolution))
            return resolution, events
        if choice.skill_name not in {'Athletics', 'Acrobatics'}:
            raise EncounterValidationError('Liquid-entry mitigation requires Athletics or Acrobatics.')
        ability = choice.ability
        skill_bonus = actor.skill_bonuses.get(choice.skill_name, actor.ability_modifiers[ability])
        flat_modifier = skill_bonus - actor.ability_modifiers[ability]
        check_request = CheckRequest(
            context=self._liquid_context(actor.actor_id),
            ability=ability,
            dc=choice.dc,
            skill_name=choice.skill_name,
            flat_modifier=flat_modifier,
        )
        check_resolution, check_events = self.resolve_check(state, check_request, apply=False)
        events.append(ResourceSpentEvent(actor_id=actor.actor_id, resource='reaction', reason='fall-liquid-mitigation'))
        events.extend(check_events)
        damage_after = damage_total // 2 if check_resolution.branch == EffectResolutionBranch.SUCCESS else damage_total
        resolution = LiquidEntryMitigationResolution(
            used_reaction=True,
            success=(check_resolution.branch == EffectResolutionBranch.SUCCESS),
            damage_before=damage_total,
            damage_after=damage_after,
            check_resolution=check_resolution,
        )
        events.append(FallMitigationCheckResolvedEvent(actor_id=actor.actor_id, resolution=resolution))
        return resolution, events

    def _apply_events(self, state: EncounterState, events: list[object]) -> None:
        for event in events:
            self.kernel._apply_event(state, event)

    def _select_branch(self, success: bool | None, total: int, dc: int, partial_success_margin: int | None) -> EffectResolutionBranch:
        if success:
            return EffectResolutionBranch.SUCCESS
        if partial_success_margin is not None and total >= dc - partial_success_margin:
            return EffectResolutionBranch.PARTIAL_SUCCESS
        return EffectResolutionBranch.FAILURE

    def _branch_outcome(self, request: HazardResolutionRequest, branch: EffectResolutionBranch | None):
        if branch == EffectResolutionBranch.SUCCESS:
            return request.success_outcome
        if branch == EffectResolutionBranch.PARTIAL_SUCCESS:
            return request.partial_success_outcome or request.failure_outcome
        return request.failure_outcome

    def _forced_movement_stop_reason(self, state: EncounterState, actor: RuntimeActorState, destination: GridPosition) -> ForcedMovementStopReason | None:
        try:
            tile = self.kernel.battlefield_rules.get_tile(state.battlefield, destination.x, destination.y)
        except EncounterValidationError:
            return ForcedMovementStopReason.OUTSIDE_BATTLEFIELD
        volume = OccupiedVolume(destination.x, destination.y, destination.z, height_ft=actor.occupied_height_ft)
        if volume.z < tile.elevation_ft or volume.top_z > tile.ceiling_ft:
            return ForcedMovementStopReason.BLOCKED_TERRAIN
        for other in state.actors.values():
            if other.actor_id == actor.actor_id or not other.is_conscious:
                continue
            if volume.intersects(other.occupied_volume):
                return ForcedMovementStopReason.BLOCKED_OCCUPANCY
        if not self.kernel.battlefield_rules.is_volume_occupiable(state, volume, actor, ignore_actor_id=actor.actor_id):
            return ForcedMovementStopReason.BLOCKED_TERRAIN
        return None

    def _candidate_positions(self, state: EncounterState, actor: RuntimeActorState, effect: ForcedMovementEffect) -> tuple[GridPosition, ...]:
        steps = max(0, effect.distance_ft // 5)
        if steps == 0:
            return ()
        if effect.mode == ForcedMovementMode.REPOSITION:
            if effect.destination is not None:
                return self._path_to_destination(actor.position, effect.destination, steps)
            if effect.vector is None:
                raise EncounterValidationError('Forced reposition requires a destination or displacement vector.')
            return self._path_by_vector(actor.position, effect.vector, steps)
        if effect.context.source_actor_id is None:
            raise EncounterValidationError('Push and pull effects require a source actor id.')
        source = self.kernel._require_actor(state, effect.context.source_actor_id)
        dx = self._step_axis(actor.position.x, source.position.x, away=(effect.mode == ForcedMovementMode.PUSH))
        dy = self._step_axis(actor.position.y, source.position.y, away=(effect.mode == ForcedMovementMode.PUSH))
        dz = 0
        vector = DisplacementVector(dx=dx, dy=dy, dz=dz)
        return self._path_by_vector(actor.position, vector, steps)

    def _path_by_vector(self, start: GridPosition, vector, steps: int) -> tuple[GridPosition, ...]:
        dx = 0 if vector.dx == 0 else (1 if vector.dx > 0 else -1)
        dy = 0 if vector.dy == 0 else (1 if vector.dy > 0 else -1)
        dz = 0 if vector.dz == 0 else (5 if vector.dz > 0 else -5)
        out = []
        current = start
        for _ in range(steps):
            current = GridPosition(current.x + dx, current.y + dy, current.z + dz)
            out.append(current)
        return tuple(out)

    def _path_to_destination(self, start: GridPosition, destination: GridPosition, max_steps: int) -> tuple[GridPosition, ...]:
        out = []
        current = start
        for _ in range(max_steps):
            if current == destination:
                break
            dx = 0 if destination.x == current.x else (1 if destination.x > current.x else -1)
            dy = 0 if destination.y == current.y else (1 if destination.y > current.y else -1)
            z_delta = destination.z - current.z
            dz = 0 if z_delta == 0 else (5 if z_delta > 0 else -5)
            current = GridPosition(current.x + dx, current.y + dy, current.z + dz)
            out.append(current)
            if current == destination:
                break
        return tuple(out)

    def _step_axis(self, actor_value: int, source_value: int, *, away: bool) -> int:
        if actor_value == source_value:
            return 0
        if away:
            return 1 if actor_value > source_value else -1
        return -1 if actor_value > source_value else 1

    def _liquid_context(self, actor_id: str) -> 'ResolutionContext':
        from shared_types.effects import ResolutionContext

        return ResolutionContext(effect_id='liquid-entry-mitigation', source_actor_id=None, target_actor_id=actor_id, reason='falling into liquid')
