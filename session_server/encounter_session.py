from __future__ import annotations

from dataclasses import dataclass

from encounter_runtime.control import EncounterControlRuntime, PromptDecision
from encounter_runtime.visibility import controller_visibility_state
from player_interface.encounter_commands import EncounterSlashCommandInterface
from session_server.encounter_projection import build_controller_encounter_projection
from shared_types.encounter_control import ControllerEncounterView
from shared_types.encounter_events import (
    AttackDeclaredEvent,
    AttackHitEvent,
    AttackMissedEvent,
    AttackRolledEvent,
    DamageAppliedEvent,
    DeathSaveFailedEvent,
    DeathSaveNaturalOneEvent,
    DeathSaveNaturalTwentyEvent,
    DeathSaveRolledEvent,
    DeathSaveSucceededEvent,
    DiedEvent,
    FallDistanceComputedEvent,
    FallLandedEvent,
    FallStartedEvent,
    HealedFromZeroEvent,
    ProneAppliedFromFallEvent,
    ReactionChosenEvent,
    StabilizedEvent,
    ShortRestCompletedEvent,
    ShortRestInterruptedEvent,
    ShortRestStartedEvent,
    LongRestCompletedEvent,
    LongRestInterruptedEvent,
    LongRestResumedEvent,
    LongRestStartedEvent,
    HitPointDieSpentEvent,
    HitPointDiceRestoredEvent,
    HitPointsRecoveredFromRestEvent,
    SpellSlotsRecoveredFromRestEvent,
    ResourceRecoveredFromRestEvent,
    ItemChargesRecoveredFromRestEvent,
    ExhaustionReducedFromRestEvent,
    TimeAdvancedEvent,
    SupportStateEvaluatedEvent,
    TeleportDeclaredEvent,
    TeleportResolvedEvent,
    UnconsciousAtZeroAppliedEvent,
)
from shared_types.encounter_intents import ChooseReactionIntent, ChooseTimingOrderIntent, StartEncounterIntent
from shared_types.encounter_models import ActorSide, DyingStateStatus, EncounterState, GridPosition
from shared_types.errors import EncounterPermissionError
from shared_types.models import ChoiceView
from shared_types.visibility import ObserverVisibilityState


@dataclass(frozen=True)
class ControllerCommandResult:
    view: ControllerEncounterView


def _actor_name(state: EncounterState, actor_id: str) -> str:
    actor = state.actors.get(actor_id)
    return actor.name if actor is not None else actor_id


def _attack_name(state: EncounterState, actor_id: str, attack_id: str) -> str:
    actor = state.actors.get(actor_id)
    if actor is None:
        return attack_id
    attack = actor.attacks.get(attack_id)
    return attack.name if attack is not None else attack_id


def _tile_suffix(state: EncounterState, position: GridPosition) -> str:
    battlefield = state.battlefield
    if not battlefield.has_authored_map:
        return ''
    tile = battlefield.tiles[GridPosition(position.x, position.y)]
    return f'; Tile {tile.terrain_id} @ {tile.elevation_ft} ft'


def _battlefield_public_lines(state: EncounterState) -> tuple[str, ...]:
    battlefield = state.battlefield
    if not battlefield.has_authored_map or battlefield.grid is None:
        return ()
    return (
        f'Battlefield: {battlefield.name} [{battlefield.map_id}] {battlefield.grid.width}x{battlefield.grid.height} @ {battlefield.grid.cell_size_feet}-ft grid.',
        f'Battlefield features: {len(battlefield.object_ids)} objects, {len(battlefield.blocker_ids)} blockers; spawn zones {", ".join(sorted(battlefield.spawn_zones))}.',
    )


def _recent_event_lines(state: EncounterState, *, limit: int = 12, actor_labeler=None) -> tuple[str, ...]:
    actor_label = actor_labeler or (lambda actor_id: _actor_name(state, actor_id))
    formatted: list[str] = []
    for event in state.event_log:
        if isinstance(event, ReactionChosenEvent):
            if event.option_id == 'decline':
                formatted.append(f'{actor_label(event.actor_id)} declined a reaction.')
            elif event.option_id.startswith('opportunity:'):
                _, owner_actor_id, attack_id = event.option_id.split(':', 2)
                formatted.append(
                    f'{actor_label(owner_actor_id)} triggered Opportunity Attack ({_attack_name(state, owner_actor_id, attack_id)}).'
                )
        elif isinstance(event, AttackDeclaredEvent):
            formatted.append(
                f'{actor_label(event.actor_id)} attacks {actor_label(event.target_id)} with {_attack_name(state, event.actor_id, event.attack_id)}.'
            )
        elif isinstance(event, AttackRolledEvent):
            roll_text = ', '.join(str(roll) for roll in event.attack_rolls)
            formatted.append(
                f'{actor_label(event.actor_id)} rolled {roll_text} for {_attack_name(state, event.actor_id, event.attack_id)}: total {event.attack_total}.'
            )
        elif isinstance(event, AttackHitEvent):
            formatted.append(
                f'{_attack_name(state, event.actor_id, event.attack_id)} hits {actor_label(event.target_id)}.'
            )
        elif isinstance(event, AttackMissedEvent):
            formatted.append(
                f'{_attack_name(state, event.actor_id, event.attack_id)} misses {actor_label(event.target_id)}.'
            )
        elif isinstance(event, DamageAppliedEvent):
            target = state.actors.get(event.target_id)
            if target is None:
                formatted.append(f'{event.target_id} takes {event.damage_total} {event.damage_type} damage.')
            else:
                formatted.append(
                    f'{actor_label(event.target_id)} takes {event.damage_total} {event.damage_type} damage; HP {target.current_hit_points}/{target.max_hit_points}, Temp {target.temp_hit_points}.'
                )
        elif isinstance(event, UnconsciousAtZeroAppliedEvent):
            formatted.append(f'{actor_label(event.actor_id)} drops to 0 HP and falls unconscious.')
        elif isinstance(event, DeathSaveRolledEvent):
            formatted.append(f'{actor_label(event.actor_id)} rolls a death save: {event.selected_roll}.')
        elif isinstance(event, DeathSaveSucceededEvent):
            formatted.append(f'{actor_label(event.actor_id)} records a death save success ({event.total_successes}/3).')
        elif isinstance(event, DeathSaveFailedEvent):
            formatted.append(f'{actor_label(event.actor_id)} records {event.failures_added} death save failure(s) ({event.total_failures}/3).')
        elif isinstance(event, DeathSaveNaturalOneEvent):
            formatted.append(f'{actor_label(event.actor_id)} rolled a natural 1 on a death save.')
        elif isinstance(event, DeathSaveNaturalTwentyEvent):
            formatted.append(f'{actor_label(event.actor_id)} rolled a natural 20 on a death save and regains 1 HP.')
        elif isinstance(event, StabilizedEvent):
            formatted.append(f'{actor_label(event.actor_id)} is stabilized at 0 HP.')
        elif isinstance(event, HealedFromZeroEvent):
            formatted.append(f'{actor_label(event.actor_id)} is healed from 0 HP to {event.hit_points_after} HP.')
        elif isinstance(event, DiedEvent):
            formatted.append(f'{actor_label(event.actor_id)} dies.')
        elif isinstance(event, ShortRestStartedEvent):
            formatted.append(f'{actor_label(event.actor_id)} starts a short rest.')
        elif isinstance(event, ShortRestInterruptedEvent):
            formatted.append(f'{actor_label(event.actor_id)} has a short rest interrupted by {event.reason.value}.')
        elif isinstance(event, ShortRestCompletedEvent):
            formatted.append(f'{actor_label(event.actor_id)} completes a short rest.')
        elif isinstance(event, LongRestStartedEvent):
            formatted.append(f'{actor_label(event.actor_id)} starts a long rest.')
        elif isinstance(event, LongRestInterruptedEvent):
            formatted.append(f'{actor_label(event.actor_id)} has a long rest interrupted by {event.reason.value}.')
        elif isinstance(event, LongRestResumedEvent):
            formatted.append(f'{actor_label(event.actor_id)} resumes a long rest.')
        elif isinstance(event, LongRestCompletedEvent):
            formatted.append(f'{actor_label(event.actor_id)} completes a long rest.')
        elif isinstance(event, TimeAdvancedEvent):
            formatted.append(f'Time advances by {event.elapsed_seconds // 60} minute(s) of {event.activity_type.value}.')
        elif isinstance(event, HitPointDieSpentEvent):
            formatted.append(f'{actor_label(event.actor_id)} spends a Hit Point Die and recovers {event.hit_points_gained} HP.')
        elif isinstance(event, HitPointDiceRestoredEvent):
            formatted.append(f'{actor_label(event.actor_id)} restores Hit Point Dice to {event.remaining_hit_dice}.')
        elif isinstance(event, HitPointsRecoveredFromRestEvent):
            formatted.append(f'{actor_label(event.actor_id)} recovers {event.amount_recovered} HP from rest.')
        elif isinstance(event, SpellSlotsRecoveredFromRestEvent):
            formatted.append(f'{actor_label(event.actor_id)} recovers spell slots in {event.resource_id}.')
        elif isinstance(event, ResourceRecoveredFromRestEvent):
            formatted.append(f'{actor_label(event.actor_id)} recovers {event.resource_id}.')
        elif isinstance(event, ItemChargesRecoveredFromRestEvent):
            formatted.append(f'{actor_label(event.actor_id)} recovers charges for {event.resource_id}.')
        elif isinstance(event, ExhaustionReducedFromRestEvent):
            formatted.append(f'{actor_label(event.actor_id)} reduces Exhaustion to {event.exhaustion_level_after}.')
        elif isinstance(event, TeleportDeclaredEvent):
            formatted.append(
                f'{actor_label(event.actor_id)} begins a teleport to ({event.to_position.x},{event.to_position.y},{event.to_position.z}).'
            )
        elif isinstance(event, TeleportResolvedEvent):
            formatted.append(
                f'{actor_label(event.actor_id)} teleports to ({event.to_position.x},{event.to_position.y},{event.to_position.z}).'
            )
        elif isinstance(event, FallStartedEvent):
            formatted.append(f'{actor_label(event.actor_id)} starts falling.')
        elif isinstance(event, FallDistanceComputedEvent):
            formatted.append(f'{actor_label(event.actor_id)} falls {event.distance_ft} ft.')
        elif isinstance(event, FallLandedEvent):
            formatted.append(
                f'{actor_label(event.actor_id)} lands at ({event.to_position.x},{event.to_position.y},{event.to_position.z}) on {event.landing_surface_type.value}.'
            )
        elif isinstance(event, ProneAppliedFromFallEvent):
            formatted.append(f'{actor_label(event.actor_id)} lands prone from the fall.')
        elif isinstance(event, SupportStateEvaluatedEvent) and event.support_state.value in {'flying', 'hovering'}:
            formatted.append(f'{actor_label(event.actor_id)} is now {event.support_state.value}.')
    if not formatted:
        return ()
    tail = formatted[-limit:]
    return tuple(['Recent events:', *[f'  - {line}' for line in tail]])


class EncounterSession:
    def __init__(
        self,
        *,
        state: EncounterState,
        control_runtime: EncounterControlRuntime,
        command_interface: EncounterSlashCommandInterface,
        runtime_services=None,
    ) -> None:
        self.state = state
        self.control_runtime = control_runtime
        self.command_interface = command_interface
        self.runtime_services = runtime_services
        self.control_runtime.validate_actor_bindings(self.state)

    def system_execute(
        self,
        command: str,
        *,
        reaction_decider: PromptDecision | None = None,
    ) -> None:
        intent = self.command_interface.parse_command(command)
        if not isinstance(intent, StartEncounterIntent):
            raise EncounterPermissionError('The system connector only handles `/encounter start` directly in this session layer.')
        self.control_runtime.dispatch_intent(self.state, intent, reaction_decider=reaction_decider)

    def _sync_dynamic_actor_bindings(self) -> None:
        stale_actor_ids = [actor_id for actor_id in self.control_runtime.actor_controllers if actor_id not in self.state.actors]
        for actor_id in stale_actor_ids:
            self.control_runtime.actor_controllers.pop(actor_id, None)
        for actor_id, actor in self.state.actors.items():
            if actor_id in self.control_runtime.actor_controllers:
                continue
            if actor.summon_owner_actor_id is None:
                continue
            owner_controller_id = self.control_runtime.actor_controllers.get(actor.summon_owner_actor_id)
            if owner_controller_id is not None:
                self.control_runtime.actor_controllers[actor_id] = owner_controller_id

    def execute_for_controller(
        self,
        controller_id: str,
        command: str,
        *,
        reaction_decider: PromptDecision | None = None,
    ) -> ControllerCommandResult:
        self._sync_dynamic_actor_bindings()
        self.control_runtime.validate_actor_bindings(self.state)
        self.control_runtime.validate_controller(controller_id)
        intent = self.command_interface.parse_command(command)
        if intent is None:
            return ControllerCommandResult(view=self.view_for_controller(controller_id))
        if isinstance(intent, StartEncounterIntent):
            raise EncounterPermissionError('Encounter start is managed by the system connector, not by a DM or player controller.')
        self.control_runtime.submit_intent(self.state, controller_id, intent, reaction_decider=reaction_decider)
        return ControllerCommandResult(view=self.view_for_controller(controller_id))

    def respond_to_prompt(self, controller_id: str, option_ids: list[str] | str | None) -> ControllerCommandResult:
        self._sync_dynamic_actor_bindings()
        prompt = self.prompt_for_controller(controller_id)
        if prompt is None:
            raise EncounterPermissionError('There is no prompt available for this controller.')
        if prompt.prompt_kind == 'reaction':
            return self._respond_to_reaction_prompt(controller_id, prompt, option_ids)
        if prompt.prompt_kind == 'timing-order':
            return self._respond_to_timing_order_prompt(controller_id, prompt, option_ids)
        raise EncounterPermissionError(f'Unsupported prompt kind: {prompt.prompt_kind}.')

    def _respond_to_reaction_prompt(self, controller_id: str, prompt, option_ids: list[str] | str | None) -> ControllerCommandResult:
        selected_ids = self._normalize_reaction_selection(prompt, option_ids)
        selected_by_actor = {option.actor_id: option.option_id for option in prompt.options if option.option_id in selected_ids}
        actor_order: list[str] = []
        for option in prompt.options:
            if option.actor_id not in actor_order:
                actor_order.append(option.actor_id)

        for actor_id in actor_order:
            current_prompt = self.prompt_for_controller(controller_id)
            if current_prompt is None:
                break
            current_actor_ids = {option.actor_id for option in current_prompt.options}
            if actor_id not in current_actor_ids:
                continue
            chosen_option_id = selected_by_actor.get(actor_id, 'decline')
            self.control_runtime.submit_intent(self.state, controller_id, ChooseReactionIntent(actor_id=actor_id, option_id=chosen_option_id))

        return ControllerCommandResult(view=self.view_for_controller(controller_id))

    def _respond_to_timing_order_prompt(self, controller_id: str, prompt, option_ids: list[str] | str | None) -> ControllerCommandResult:
        selected_id = self._normalize_single_prompt_selection(prompt, option_ids)
        if len(prompt.recipients) != 1 or len(prompt.recipients[0].actor_ids) != 1:
            raise EncounterPermissionError('Timing-order prompts must target exactly one controlled actor.')
        actor_id = prompt.recipients[0].actor_ids[0]
        self.control_runtime.submit_intent(self.state, controller_id, ChooseTimingOrderIntent(actor_id=actor_id, entry_id=selected_id))
        return ControllerCommandResult(view=self.view_for_controller(controller_id))

    def _prompt_tokens(self, option_ids: list[str] | str | None) -> list[str]:
        if option_ids is None:
            return []
        if isinstance(option_ids, str):
            return [token.strip() for token in option_ids.split(',') if token.strip()]
        return [token.strip() for token in option_ids if token.strip()]

    def _normalize_single_prompt_selection(self, prompt, option_ids: list[str] | str | None) -> str:
        tokens = self._prompt_tokens(option_ids)
        if len(tokens) != 1:
            raise EncounterPermissionError('This prompt requires exactly one option selection.')
        token = tokens[0]
        if token.lower() == 'decline':
            raise EncounterPermissionError('This prompt does not support `decline`.')
        option_ids_available = {option.option_id for option in prompt.options}
        if token not in option_ids_available:
            raise EncounterPermissionError('The chosen prompt option is not available to this controller.')
        return token

    def _normalize_reaction_selection(self, prompt, option_ids: list[str] | str | None) -> set[str]:
        tokens = self._prompt_tokens(option_ids)
        if not tokens:
            return set()
        if len(tokens) == 1 and tokens[0].lower() == 'decline':
            return set()
        option_map = {option.option_id: option for option in prompt.options}
        selected: set[str] = set()
        selected_actor_ids: set[str] = set()
        for token in tokens:
            if token.lower() == 'decline':
                raise EncounterPermissionError('`decline` cannot be mixed with explicit reaction choices.')
            option = option_map.get(token)
            if option is None:
                raise EncounterPermissionError('The chosen reaction option is not available to this controller.')
            if option.actor_id in selected_actor_ids:
                raise EncounterPermissionError('A controller may choose at most one reaction option per reacting actor.')
            selected.add(option.option_id)
            selected_actor_ids.add(option.actor_id)
        return selected

    def view_for_controller(self, controller_id: str) -> ControllerEncounterView:
        self._sync_dynamic_actor_bindings()
        binding = self.control_runtime.validate_controller(controller_id)
        self.control_runtime.validate_actor_bindings(self.state)
        summary_lines = [
            f'Phase: {self.state.phase.value}',
            f'Round: {self.state.round_number or 0}',
            f'Active actor: {self.state.active_actor_id or "pending"}',
            f'Initiative: {", ".join(self.state.initiative_order) or "pending"}',
        ]
        summary_lines.extend(_battlefield_public_lines(self.state))
        prompt = self.control_runtime.build_prompt(self.state)
        if prompt is not None:
            waiting_on = ', '.join(recipient.label for recipient in prompt.recipients)
            prompt_label = prompt.prompt_kind.replace('-', ' ')
            summary_lines.append(f'Pending {prompt_label} prompt: waiting on {waiting_on}.')
            controller_prompt = self.control_runtime.prompt_for_controller(self.state, controller_id)
            if controller_prompt is not None:
                controller_prompt_label = controller_prompt.prompt_kind.replace('-', ' ')
                summary_lines.append(f'{controller_prompt_label.capitalize()} prompt: {controller_prompt.prompt}')
        actor_order = self.state.initiative_order or tuple(self.state.actors)
        observer_actor_ids = tuple(
            actor_id
            for actor_id in actor_order
            if self.control_runtime.controller_for_actor(actor_id) == controller_id
        )
        for actor_id in actor_order:
            actor = self.state.actors[actor_id]
            owner_controller_id = self.control_runtime.controller_for_actor(actor_id)
            owns_actor = owner_controller_id == controller_id
            sees_private = owns_actor or (binding.role.value == 'dm' and actor.side == ActorSide.MONSTER)
            visibility_state = ObserverVisibilityState.VISIBLE
            if binding.role.value != 'dm' and not owns_actor:
                visibility_state = controller_visibility_state(self.state, observer_actor_ids, actor)
                if visibility_state == ObserverVisibilityState.HIDDEN:
                    continue
            tile_suffix = _tile_suffix(self.state, actor.position)
            if sees_private:
                dying_suffix = ''
                if actor.dying_state.status != DyingStateStatus.ALIVE:
                    dying_suffix = f'; Dying {actor.dying_state.status.value}; Death saves {actor.dying_state.death_save_successes}/{actor.dying_state.death_save_failures}'
                summary_lines.append(
                    f'{actor.actor_id}: {actor.name} [{actor.side.value}] HP {actor.current_hit_points}/{actor.max_hit_points}; Temp {actor.temp_hit_points}; AC {actor.effective_armor_class}; Pos ({actor.position.x},{actor.position.y},{actor.position.z}){tile_suffix}; Move {actor.remaining_movement_ft}; Action {"yes" if actor.action_available else "no"}; Bonus {"yes" if actor.bonus_action_available else "no"}; Reaction {"yes" if actor.reaction_available else "no"}{dying_suffix}'
                )
            else:
                if actor.dying_state.status == DyingStateStatus.DEAD:
                    status = 'dead'
                elif actor.dying_state.status == DyingStateStatus.STABLE_AT_0_HP:
                    status = 'stable'
                elif actor.current_hit_points == 0 or actor.dying_state.status == DyingStateStatus.AT_0_HP_UNCONSCIOUS:
                    status = 'unconscious'
                else:
                    status = 'active'
                turn_marker = '; Turn active' if actor.actor_id == self.state.active_actor_id else ''
                label = actor.name if visibility_state == ObserverVisibilityState.VISIBLE else 'Unseen contact'
                display_actor_id = actor.actor_id if visibility_state == ObserverVisibilityState.VISIBLE else 'unknown-contact'
                dm_dying_suffix = ''
                if binding.role.value == 'dm' and actor.dying_state.status != DyingStateStatus.ALIVE:
                    dm_dying_suffix = f'; Death saves {actor.dying_state.death_save_successes}/{actor.dying_state.death_save_failures}'
                summary_lines.append(
                    f'{display_actor_id}: {label} [{actor.side.value if visibility_state == ObserverVisibilityState.VISIBLE else "unknown"}] Pos ({actor.position.x},{actor.position.y},{actor.position.z}){tile_suffix}; Status {status}{turn_marker}{dm_dying_suffix}'
                )
        def actor_labeler(actor_id: str) -> str:
            actor = self.state.actors.get(actor_id)
            if actor is None:
                return actor_id
            owner_controller_id = self.control_runtime.controller_for_actor(actor_id)
            owns_actor = owner_controller_id == controller_id
            if binding.role.value == 'dm' or owns_actor:
                return actor.name
            visibility_state = controller_visibility_state(self.state, observer_actor_ids, actor)
            if visibility_state == ObserverVisibilityState.VISIBLE:
                return actor.name
            if visibility_state == ObserverVisibilityState.UNSEEN:
                return 'Unseen contact'
            return 'Unknown contact'

        recent_event_lines = _recent_event_lines(self.state, actor_labeler=actor_labeler)
        summary_lines.extend(recent_event_lines)
        available_choices: dict[str, tuple[ChoiceView, ...]] = {}
        controller_prompt = self.control_runtime.prompt_for_controller(self.state, controller_id)
        if controller_prompt is not None:
            if controller_prompt.prompt_kind == 'reaction':
                available_choices['reactions'] = tuple(
                    ChoiceView(option_id=option.option_id, label=option.label, detail=option.detail)
                    for option in controller_prompt.options
                )
        elif self.state.active_actor_id is not None:
            active_owner = self.control_runtime.controller_for_actor(self.state.active_actor_id)
            if active_owner == controller_id:
                available_choices = dict(self.command_interface.kernel.snapshot(self.state).available_choices)
        projection = build_controller_encounter_projection(
            state=self.state,
            control_runtime=self.control_runtime,
            controller_id=controller_id,
            available_choices=available_choices,
            recent_events=tuple(line[4:] for line in recent_event_lines[1:]) if recent_event_lines else (),
        )
        return ControllerEncounterView(
            controller_id=controller_id,
            role=binding.role,
            phase=self.state.phase,
            summary_lines=tuple(summary_lines),
            available_choices=available_choices,
            projection=projection,
        )

    def prompt_for_controller(self, controller_id: str):
        self._sync_dynamic_actor_bindings()
        self.control_runtime.validate_controller(controller_id)
        self.control_runtime.validate_actor_bindings(self.state)
        return self.control_runtime.prompt_for_controller(self.state, controller_id)




