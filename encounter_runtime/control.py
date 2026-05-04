from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from shared_types.encounter_control import ControllerBinding, ControllerPrompt, PromptOption, PromptRecipient
from shared_types.encounter_intents import (
    AdvanceTimeIntent,
    AttackIntent,
    CastSpellIntent,
    ChooseReactionIntent,
    ChooseTimingOrderIntent,
    ContinueTimingIntent,
    DismountActorIntent,
    EncounterIntent,
    EndTurnIntent,
    GrappleIntent,
    MountActorIntent,
    MoveActorIntent,
    ObjectInteractionIntent,
    ReadyIntent,
    ResumeRestIntent,
    ShareFamiliarSensesIntent,
    ShoveIntent,
    SpendHitPointDieIntent,
    StandFromProneIntent,
    StartEncounterIntent,
    StartLongRestIntent,
    StartShortRestIntent,
    TakeCombatActionIntent,
    UseCapabilityIntent,
    UseImprovisedWeaponIntent,
)
from shared_types.encounter_models import EncounterState
from shared_types.errors import EncounterOwnershipError, EncounterPermissionError, EncounterValidationError

from .kernel import EncounterKernel

PromptDecision = Callable[[ControllerPrompt, EncounterState], str | None]


@dataclass(frozen=True)
class EncounterControlResult:
    state: EncounterState
    prompt: ControllerPrompt | None


class EncounterControlRuntime:
    def __init__(
        self,
        *,
        kernel: EncounterKernel,
        controllers: dict[str, ControllerBinding],
        actor_controllers: dict[str, str],
        dm_override_enabled: bool = False,
    ) -> None:
        self.kernel = kernel
        self.controllers = controllers
        self.actor_controllers = actor_controllers
        self.dm_override_enabled = dm_override_enabled

    def dispatch_intent(
        self,
        state: EncounterState,
        intent: EncounterIntent,
        *,
        reaction_decider: PromptDecision | None = None,
    ) -> EncounterControlResult:
        self.validate_actor_bindings(state)
        self.kernel.dispatch(state, intent)
        return self._continue(state, reaction_decider=reaction_decider)

    def submit_intent(
        self,
        state: EncounterState,
        controller_id: str,
        intent: EncounterIntent,
        *,
        reaction_decider: PromptDecision | None = None,
    ) -> EncounterControlResult:
        self.validate_actor_bindings(state)
        self._authorize_intent(controller_id, intent)
        self.kernel.dispatch(state, intent)
        return self._continue(state, reaction_decider=reaction_decider)

    def continue_after_prompt(
        self,
        state: EncounterState,
        *,
        reaction_decider: PromptDecision,
    ) -> EncounterControlResult:
        self.validate_actor_bindings(state)
        return self._continue(state, reaction_decider=reaction_decider)

    def controller_for_actor(self, actor_id: str) -> str:
        controller_id = self.actor_controllers.get(actor_id)
        if controller_id is None:
            raise EncounterOwnershipError(f'Actor {actor_id!r} is not bound to any controller.')
        if controller_id not in self.controllers:
            raise EncounterOwnershipError(f'Actor {actor_id!r} is bound to unknown controller {controller_id!r}.')
        return controller_id

    def validate_controller(self, controller_id: str) -> ControllerBinding:
        binding = self.controllers.get(controller_id)
        if binding is None:
            raise EncounterPermissionError(f'Unknown controller: {controller_id!r}.')
        return binding

    def validate_actor_bindings(self, state: EncounterState) -> None:
        missing = sorted(actor_id for actor_id in state.actors if actor_id not in self.actor_controllers)
        if missing:
            raise EncounterOwnershipError(f'Every actor must be bound to exactly one controller. Missing bindings: {", ".join(missing)}.')
        extras = sorted(actor_id for actor_id in self.actor_controllers if actor_id not in state.actors)
        if extras:
            raise EncounterOwnershipError(f'Actor bindings reference unknown encounter actors: {", ".join(extras)}.')
        unknown_controllers = sorted({controller_id for controller_id in self.actor_controllers.values() if controller_id not in self.controllers})
        if unknown_controllers:
            raise EncounterOwnershipError(f'Actor bindings reference unknown controllers: {", ".join(unknown_controllers)}.')

    def build_prompt(self, state: EncounterState) -> ControllerPrompt | None:
        window = state.pending_reaction_window
        if window is not None:
            if not window.options:
                raise EncounterValidationError('Reaction window has no legal options.')
            recipient_actor_ids: dict[str, list[str]] = {}
            for option in window.options:
                controller_id = self.controller_for_actor(option.actor_id)
                recipient_actor_ids.setdefault(controller_id, [])
                if option.actor_id not in recipient_actor_ids[controller_id]:
                    recipient_actor_ids[controller_id].append(option.actor_id)
            recipients = tuple(
                PromptRecipient(
                    controller_id=controller_id,
                    role=self.controllers[controller_id].role,
                    label=self.controllers[controller_id].label,
                    actor_ids=tuple(actor_ids),
                )
                for controller_id, actor_ids in recipient_actor_ids.items()
            )
            return ControllerPrompt(
                prompt_id=f'reaction:{window.trigger_id}',
                prompt_kind='reaction',
                prompt=window.prompt,
                recipients=recipients,
                options=tuple(
                    PromptOption(
                        option_id=option.option_id,
                        label=option.label,
                        detail=option.detail,
                        actor_id=option.actor_id,
                    )
                    for option in window.options
                ),
                trigger_id=window.trigger_id,
                trigger_type=window.trigger_type.value,
            )
        queue = state.pending_timing_queue
        if queue is None or len(queue.entries) <= 1:
            return None
        controller_id = self.controller_for_actor(queue.actor_id)
        binding = self.controllers[controller_id]
        return ControllerPrompt(
            prompt_id=f'timing:{queue.actor_id}:{queue.phase.value}',
            prompt_kind='timing-order',
            prompt=f'Choose the next {queue.phase.value} effect to resolve.',
            recipients=(
                PromptRecipient(
                    controller_id=controller_id,
                    role=binding.role,
                    label=binding.label,
                    actor_ids=(queue.actor_id,),
                ),
            ),
            options=tuple(
                PromptOption(
                    option_id=entry.entry_id,
                    label=entry.label,
                    detail=entry.kind.value,
                    actor_id=entry.actor_id,
                )
                for entry in queue.entries
            ),
        )

    def prompt_for_controller(self, state: EncounterState, controller_id: str) -> ControllerPrompt | None:
        prompt = self.build_prompt(state)
        if prompt is None:
            return None
        self.validate_controller(controller_id)
        recipient_ids = {recipient.controller_id for recipient in prompt.recipients}
        if controller_id not in recipient_ids:
            return None
        if prompt.prompt_kind == 'reaction':
            option_actor_ids = {
                option.actor_id
                for option in prompt.options
                if option.actor_id is not None and self.controller_for_actor(option.actor_id) == controller_id
            }
            options = tuple(
                option
                for option in prompt.options
                if option.actor_id is not None and option.actor_id in option_actor_ids
            )
        else:
            options = prompt.options
        recipients = tuple(recipient for recipient in prompt.recipients if recipient.controller_id == controller_id)
        return ControllerPrompt(
            prompt_id=prompt.prompt_id,
            prompt_kind=prompt.prompt_kind,
            prompt=prompt.prompt,
            recipients=recipients,
            options=options,
            trigger_id=prompt.trigger_id,
            trigger_type=prompt.trigger_type,
        )

    def _continue(
        self,
        state: EncounterState,
        *,
        reaction_decider: PromptDecision | None,
    ) -> EncounterControlResult:
        while True:
            prompt = self.build_prompt(state)
            if prompt is not None:
                if reaction_decider is None:
                    return EncounterControlResult(state=state, prompt=prompt)
                chosen_option_id = reaction_decider(prompt, state)
                if prompt.prompt_kind == 'reaction':
                    actor_id = self._actor_for_reaction_choice(prompt, chosen_option_id)
                    option_id = 'decline' if chosen_option_id in {None, '', 'decline'} else chosen_option_id
                    self.kernel.dispatch(state, ChooseReactionIntent(actor_id=actor_id, option_id=option_id))
                    continue
                if prompt.prompt_kind == 'timing-order':
                    actor_id = prompt.recipients[0].actor_ids[0]
                    option_id = self._timing_choice_id(prompt, chosen_option_id)
                    self.kernel.dispatch(state, ChooseTimingOrderIntent(actor_id=actor_id, entry_id=option_id))
                    continue
                raise EncounterValidationError(f'Unsupported prompt kind: {prompt.prompt_kind}.')
            if state.pending_timing_queue is not None:
                self.kernel.dispatch(state, ContinueTimingIntent(actor_id=state.pending_timing_queue.actor_id))
                continue
            return EncounterControlResult(state=state, prompt=None)

    def _authorize_intent(self, controller_id: str, intent: EncounterIntent) -> None:
        binding = self.validate_controller(controller_id)
        if isinstance(intent, AdvanceTimeIntent):
            if binding.role.value != 'dm':
                raise EncounterPermissionError('Only the DM may advance global session time.')
            return
        acting_actor_id = self._intent_actor_id(intent)
        if acting_actor_id is None:
            if isinstance(intent, StartEncounterIntent):
                raise EncounterPermissionError('Encounter start is managed by the system connector, not by DM or player controllers.')
            return
        owner_controller_id = self.controller_for_actor(acting_actor_id)
        if controller_id == owner_controller_id:
            return
        if self.dm_override_enabled and binding.role.value == 'dm':
            return
        raise EncounterPermissionError(
            f'Controller {controller_id!r} does not own actor {acting_actor_id!r} and cannot submit this intent.'
        )

    def _intent_actor_id(self, intent: EncounterIntent) -> str | None:
        if isinstance(intent, (MoveActorIntent, MountActorIntent, DismountActorIntent, ShareFamiliarSensesIntent, StandFromProneIntent, TakeCombatActionIntent, ReadyIntent, AttackIntent, CastSpellIntent, UseCapabilityIntent, ObjectInteractionIntent, UseImprovisedWeaponIntent, GrappleIntent, ShoveIntent, ChooseReactionIntent, ChooseTimingOrderIntent, ContinueTimingIntent, EndTurnIntent, StartShortRestIntent, StartLongRestIntent, ResumeRestIntent, SpendHitPointDieIntent)):
            return intent.actor_id
        if isinstance(intent, StartEncounterIntent):
            return None
        raise EncounterValidationError('Unknown encounter intent for authorization.')

    def _actor_for_reaction_choice(self, prompt: ControllerPrompt, chosen_option_id: str | None) -> str:
        if chosen_option_id in {None, '', 'decline'}:
            actor_id = prompt.options[0].actor_id
            if actor_id is None:
                raise EncounterValidationError('Reaction prompt options must carry an actor id.')
            return actor_id
        for option in prompt.options:
            if option.option_id == chosen_option_id:
                if option.actor_id is None:
                    raise EncounterValidationError('Reaction prompt options must carry an actor id.')
                return option.actor_id
        raise EncounterValidationError('The chosen reaction option is not legal for the active prompt.')

    def _timing_choice_id(self, prompt: ControllerPrompt, chosen_option_id: str | None) -> str:
        if chosen_option_id in {None, '', 'decline'}:
            raise EncounterValidationError('A simultaneous timing prompt requires an explicit ordering choice.')
        for option in prompt.options:
            if option.option_id == chosen_option_id:
                return option.option_id
        raise EncounterValidationError('The chosen timing option is not legal for the active prompt.')
