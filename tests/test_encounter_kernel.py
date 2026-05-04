from __future__ import annotations

from pathlib import Path
import unittest

from character_creation import build_default_kernel
from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface, SlashCommandInterface
from shared_types.encounter_control import ControllerBinding, ControllerRole
from shared_types.capabilities import CapabilityDefinition, CapabilityKind, CompositeEffect, TargetSelectionKind, TargetingSpec
from shared_types.encounter_events import (
    ActionDeclaredEvent,
    ActionEffectEvent,
    ActionValidatedEvent,
    AttackMissedEvent,
    EncounterStartedEvent,
    ReactionChosenEvent,
    ReactionWindowOpenedEvent,
    ReadiedSpellDissipatedEvent,
    ReadyDeclaredEvent,
    ReadyExpiredEvent,
    ReadyTriggeredEvent,
    ResourceSpentEvent,
    SaveRolledEvent,
    SimultaneousEffectsOrderedEvent,
    SpellCastEvent,
    TeleportDeclaredEvent,
    TeleportResolvedEvent,
    TurnEndedEvent,
)
from shared_types.encounter_intents import ChooseTimingOrderIntent, ContinueTimingIntent, MoveActorIntent
from shared_types.encounter_models import (
    ActorSide,
    CharacterPlacement,
    GridPosition,
    MonsterPlacement,
    ReadyResponseKind,
    ReadyResponseState,
    ReadyTriggerKind,
    ReadyTriggerState,
    ReadiedActionState,
    RuntimeCapabilityState,
    RuntimeSpellState,
)
from shared_types.models import Ability
from shared_types.errors import EncounterValidationError, UnknownEncounterCommandError


LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class EncounterKernelTests(unittest.TestCase):
    def _build_player_record(self):
        kernel = build_default_kernel(base_url=LOCAL_MIRROR_BASE_URL)
        ui = SlashCommandInterface(kernel)
        state = kernel.new_state()
        for command in (
            '/create begin',
            '/create choose species aasimar',
            '/create choose class wizard',
            '/create choose class-skills Arcana History',
            '/create choose background acolyte',
            '/create choose choice class:wizard:cantrips fire-bolt mage-hand light',
            '/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person',
            '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS',
            '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance',
            '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds',
            '/create ability generate point-buy 15 14 13 12 10 8',
            '/create ability assign 8 14 13 15 12 10',
            '/create background-asi choose acolyte-int2-wis1',
            '/create equipment background gold',
            '/create equipment class package wizard-package-1',
            '/create confirm',
        ):
            state, _ = ui.execute(state, command)
        assert state.character_record is not None
        return state.character_record

    def _build_runtime(self):
        return build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def _monster_id(self, runtime, *, name: str, source: str) -> str:
        for record_id, record in runtime.encounter_catalog.monsters.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f'Monster not found: {name} [{source}]')

    def _build_state(self, *, player_position=GridPosition(0, 0), skeleton_position=GridPosition(6, 0), mage_position=GridPosition(8, 2)):
        runtime = self._build_runtime()
        record = self._build_player_record()
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        mage_id = self._monster_id(runtime, name='Mage', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=player_position),),
            monsters=(
                MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=skeleton_position),
                MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=mage_position),
            ),
        )
        return runtime, state

    def _build_control_runtime(self, runtime, *, mage_controller: str = 'dm'):
        controllers = {
            'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
            'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
        }
        actor_controllers = {
            'player-1': 'player-1-controller',
            'monster-skeleton-1': 'dm',
            'monster-mage-1': mage_controller,
        }
        return runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)

    def _advance_to_actor(self, ui: EncounterSlashCommandInterface, state, actor_id: str):
        guard = 0
        output = ''
        while state.active_actor_id != actor_id:
            guard += 1
            if guard > 10:
                raise AssertionError(f'Could not reach actor turn: {actor_id}')
            state, output = ui.execute(state, f'/endturn {state.active_actor_id}')
        return state, output

    def test_initiative_is_deterministic_for_same_seed_and_setup(self) -> None:
        runtime_one, state_one = self._build_state()
        runtime_two, state_two = self._build_state()
        ui_one = EncounterSlashCommandInterface(runtime_one.kernel)
        ui_two = EncounterSlashCommandInterface(runtime_two.kernel)

        state_one, output_one = ui_one.execute(state_one, '/encounter start')
        state_two, output_two = ui_two.execute(state_two, '/encounter start')

        self.assertEqual(output_one, output_two)
        self.assertEqual(state_one.initiative_order, state_two.initiative_order)
        self.assertIsInstance(state_one.event_log[0], EncounterStartedEvent)
        self.assertEqual(state_one.random_counter, 1)

    def test_action_economy_consumption_and_turn_reset(self) -> None:
        runtime, state = self._build_state()
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = ui.execute(state, '/dash monster-skeleton-1')
        self.assertFalse(state.actors['monster-skeleton-1'].action_available)
        self.assertEqual(state.actors['monster-skeleton-1'].remaining_movement_ft, 60)
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/dodge monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        state, _ = ui.execute(state, '/endturn player-1')
        self.assertEqual(state.active_actor_id, 'monster-skeleton-1')
        self.assertTrue(state.actors['monster-skeleton-1'].action_available)
        self.assertTrue(state.actors['monster-skeleton-1'].bonus_action_available)
        self.assertTrue(state.actors['monster-skeleton-1'].reaction_available)
        self.assertEqual(state.actors['monster-skeleton-1'].remaining_movement_ft, 30)

    def test_invalid_bonus_action_rejected_when_actor_lacks_capability(self) -> None:
        runtime, state = self._build_state()
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        self.assertNotIn('bonus_actions', runtime.kernel.snapshot(state).available_choices)
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/cast player-1 misty-step 5 0')

    def test_movement_limit_and_opportunity_attack_reaction_flow(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(1, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        self.assertEqual(state.active_actor_id, 'player-1')
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/move player-1 20 0')
        state, output = ui.execute(state, '/move player-1 5 0')
        self.assertIn('Reaction window:', output)
        self.assertIsNotNone(state.pending_reaction_window)
        option_id = next(option.option_id for option in state.pending_reaction_window.options if option.actor_id == 'monster-skeleton-1')
        state, _ = ui.execute(state, f'/react monster-skeleton-1 {option_id}')
        self.assertFalse(state.actors['monster-skeleton-1'].reaction_available)
        self.assertEqual(state.actors['player-1'].position, GridPosition(5, 0))
        self.assertTrue(any(isinstance(event, ReactionWindowOpenedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, ReactionChosenEvent) for event in state.event_log))
        state, _ = ui.execute(state, '/endturn player-1')
        self.assertEqual(state.active_actor_id, 'monster-skeleton-1')
        self.assertTrue(state.actors['monster-skeleton-1'].reaction_available)

    def test_shield_reaction_window_and_consumption(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(9, 9), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(1, 0))
        state.actors['monster-mage-1'].side = ActorSide.PLAYER
        state.actors['monster-mage-1'].armor_class = 10
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        self.assertEqual(state.active_actor_id, 'monster-skeleton-1')
        state, output = ui.execute(state, '/attack monster-skeleton-1 shortsword monster-mage-1')
        self.assertIn('Reaction window:', output)
        option_id = next(option.option_id for option in state.pending_reaction_window.options if option.actor_id == 'monster-mage-1')
        state, _ = ui.execute(state, f'/react monster-mage-1 {option_id}')
        self.assertFalse(state.actors['monster-mage-1'].reaction_available)
        self.assertEqual(state.actors['monster-mage-1'].armor_class_modifier, 5)
        self.assertIn('shield', state.actors['monster-mage-1'].spells)
        self.assertEqual(state.actors['monster-mage-1'].spells['shield'].remaining_uses, 2)
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == 'shield' for event in state.event_log))
        self.assertTrue(any(isinstance(event, AttackMissedEvent) for event in state.event_log))

    def test_control_runtime_routes_opportunity_prompt_to_dm_and_auto_declines(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(1, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        control_runtime = self._build_control_runtime(runtime)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        result = control_runtime.dispatch_intent(
            state,
            MoveActorIntent(actor_id='player-1', x=3, y=0),
            reaction_decider=lambda prompt, current_state: None,
        )
        self.assertIsNone(result.prompt)
        self.assertEqual(state.actors['player-1'].position, GridPosition(3, 0))
        self.assertTrue(state.actors['monster-skeleton-1'].reaction_available)
        self.assertTrue(any(isinstance(event, ReactionWindowOpenedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, ReactionChosenEvent) for event in state.event_log))

    def test_control_runtime_exposes_prompt_and_routes_it_to_dm(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(1, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        control_runtime = self._build_control_runtime(runtime)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        result = control_runtime.dispatch_intent(state, MoveActorIntent(actor_id='player-1', x=3, y=0))
        self.assertIsNotNone(result.prompt)
        assert result.prompt is not None
        self.assertEqual(result.prompt.recipients[0].controller_id, 'dm')
        self.assertEqual(result.prompt.recipients[0].role, ControllerRole.DM)
        self.assertTrue(any(option.actor_id == 'monster-skeleton-1' for option in result.prompt.options))
        self.assertEqual(state.actors['player-1'].position, GridPosition(0, 0))

    def test_control_runtime_routes_shield_prompt_to_defender_controller(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(9, 9), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(1, 0))
        state.actors['monster-mage-1'].side = ActorSide.PLAYER
        state.actors['monster-mage-1'].armor_class = 10
        ui = EncounterSlashCommandInterface(runtime.kernel)
        control_runtime = self._build_control_runtime(runtime, mage_controller='player-1-controller')
        state, _ = ui.execute(state, '/encounter start')
        result = control_runtime.dispatch_intent(
            state,
            ui.parse_command('/attack monster-skeleton-1 shortsword monster-mage-1'),
        )
        self.assertIsNotNone(result.prompt)
        assert result.prompt is not None
        self.assertEqual(result.prompt.recipients[0].controller_id, 'player-1-controller')
        chosen_option_id = next(option.option_id for option in result.prompt.options if option.actor_id == 'monster-mage-1')
        result = control_runtime.continue_after_prompt(
            state,
            reaction_decider=lambda prompt, current_state: chosen_option_id,
        )
        self.assertIsNone(result.prompt)
        self.assertFalse(state.actors['monster-mage-1'].reaction_available)
        self.assertEqual(state.actors['monster-mage-1'].spells['shield'].remaining_uses, 2)
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == 'shield' for event in state.event_log))

    def test_slash_validation_and_typed_event_emission(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(9, 9), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(1, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        with self.assertRaises(UnknownEncounterCommandError):
            ui.execute(state, '/ready monster-skeleton-1')
        state, _ = ui.execute(state, '/disengage monster-skeleton-1')
        event_types = {type(event) for event in state.event_log}
        self.assertIn(ActionDeclaredEvent, event_types)
        self.assertIn(ActionValidatedEvent, event_types)
        self.assertIn(ResourceSpentEvent, event_types)
        self.assertIn(ActionEffectEvent, event_types)

    def test_turn_end_event_is_emitted(self) -> None:
        runtime, state = self._build_state()
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, output = ui.execute(state, '/encounter start')
        self.assertIn('Active actor:', output)
        state, output = ui.execute(state, '/endturn monster-skeleton-1')
        self.assertIsInstance(state.event_log[-1], TurnEndedEvent)
        self.assertIn('Active actor:', output)

    def test_misty_step_does_not_consume_movement_and_spends_bonus_action(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(20, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        state.actors['monster-mage-1'].remaining_movement_ft = 0
        state.actors['monster-mage-1'].movement_spent_ft = state.actors['monster-mage-1'].max_path_speed_ft
        state, _ = ui.execute(state, '/cast monster-mage-1 misty-step 5 2')
        mage = state.actors['monster-mage-1']
        self.assertEqual(mage.position, GridPosition(5, 2, 0))
        self.assertEqual(mage.remaining_movement_ft, 0)
        self.assertFalse(mage.bonus_action_available)
        self.assertTrue(any(isinstance(event, TeleportDeclaredEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, TeleportResolvedEvent) for event in state.event_log))

    def test_misty_step_fails_if_destination_is_occupied(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(5, 2), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/cast monster-mage-1 misty-step 5 2')

    def test_misty_step_fails_if_destination_is_out_of_range(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(20, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/cast monster-mage-1 misty-step 16 2')

    def test_teleport_cast_remains_a_cast_intent(self) -> None:
        runtime, _ = self._build_state()
        ui = EncounterSlashCommandInterface(runtime.kernel)
        intent = ui.parse_command('/cast monster-mage-1 misty-step 5 2')
        self.assertIsInstance(intent, __import__('shared_types.encounter_intents', fromlist=['CastSpellIntent']).CastSpellIntent)

    def test_flying_budget_uses_fly_speed_and_mixed_speed_switching_counts_distance_already_moved(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(20, 0), mage_position=GridPosition(20, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state.actors['player-1'].speed_ft = 20
        state.actors['player-1'].fly_speed_ft = 30
        state.actors['player-1'].remaining_movement_ft = 30
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/move player-1 4 0')
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/fly player-1 4 0 15')


    def test_ready_attack_triggers_on_movement_and_consumes_reaction(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(6, 0), mage_position=GridPosition(9, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-skeleton-1')
        state, _ = ui.execute(state, '/ready attack monster-skeleton-1 player-1 shortsword')
        self.assertIsNotNone(state.actors['monster-skeleton-1'].readied_action)
        self.assertTrue(any(isinstance(event, ReadyDeclaredEvent) for event in state.event_log))
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        state, output = ui.execute(state, '/move player-1 5 0')
        self.assertIn('Reaction window:', output)
        self.assertIsNotNone(state.pending_reaction_window)
        assert state.pending_reaction_window is not None
        self.assertEqual(state.pending_reaction_window.trigger_type.value, 'ready-trigger')
        option_id = next(option.option_id for option in state.pending_reaction_window.options if option.actor_id == 'monster-skeleton-1')
        state, _ = ui.execute(state, f'/react monster-skeleton-1 {option_id}')
        self.assertFalse(state.actors['monster-skeleton-1'].reaction_available)
        self.assertIsNone(state.actors['monster-skeleton-1'].readied_action)
        self.assertEqual(state.actors['player-1'].position, GridPosition(5, 0))
        self.assertTrue(any(isinstance(event, ReadyTriggeredEvent) for event in state.event_log))

    def test_ready_movement_triggers_after_target_moves(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(6, 0), mage_position=GridPosition(9, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/ready move player-1 monster-skeleton-1 0 1')
        self.assertIsNotNone(state.actors['player-1'].readied_action)
        state, _ = ui.execute(state, '/endturn player-1')
        state, _ = self._advance_to_actor(ui, state, 'monster-skeleton-1')
        state, _ = ui.execute(state, '/move monster-skeleton-1 5 0')
        self.assertIsNotNone(state.pending_reaction_window)
        assert state.pending_reaction_window is not None
        option_id = next(option.option_id for option in state.pending_reaction_window.options if option.actor_id == 'player-1')
        state, _ = ui.execute(state, f'/react player-1 {option_id}')
        self.assertEqual(state.actors['player-1'].position, GridPosition(0, 1, 0))
        self.assertFalse(state.actors['player-1'].reaction_available)
        self.assertIsNone(state.actors['player-1'].readied_action)

    def test_ready_expires_at_start_of_next_turn(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(6, 0), mage_position=GridPosition(9, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-skeleton-1')
        state, _ = ui.execute(state, '/ready attack monster-skeleton-1 player-1 shortsword')
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        state, _ = ui.execute(state, '/endturn player-1')
        self.assertIsNotNone(state.pending_timing_queue)
        state = runtime.kernel.dispatch(state, ContinueTimingIntent(actor_id='monster-skeleton-1'))
        self.assertIsNone(state.actors['monster-skeleton-1'].readied_action)
        self.assertTrue(any(isinstance(event, ReadyExpiredEvent) for event in state.event_log))

    def test_readied_spell_spends_resource_immediately_and_dissipates_on_failed_concentration(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(1, 0), mage_position=GridPosition(9, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        player = state.actors['player-1']
        player.max_hit_points = 20
        player.current_hit_points = 20
        player.armor_class_modifier = -20
        player.saving_throw_bonuses[Ability.CON] = -20
        player.spells['test-bolt'] = RuntimeSpellState(
            option_id='test-bolt',
            name='Test Bolt',
            source='test',
            action_cost='action',
            range_ft=60,
            remaining_uses=1,
            max_uses=1,
            capability=CapabilityDefinition(
                capability_id='test-bolt',
                name='Test Bolt',
                kind=CapabilityKind.SPELL,
                source='test',
                action_cost='action',
                targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=60, requires_target_to_be_seen=True),
                effect=CompositeEffect(effects=()),
            ),
        )
        spell_uses_before = player.spells['test-bolt'].remaining_uses
        state, _ = ui.execute(state, '/ready cast player-1 monster-skeleton-1 test-bolt')
        player = state.actors['player-1']
        self.assertEqual(player.spells['test-bolt'].remaining_uses, spell_uses_before - 1)
        self.assertIsNotNone(player.readied_action)
        self.assertIsNotNone(player.concentrating_effect_id)
        state, _ = ui.execute(state, '/endturn player-1')
        state, _ = self._advance_to_actor(ui, state, 'monster-skeleton-1')
        state, _ = ui.execute(state, '/attack monster-skeleton-1 shortsword player-1')
        if state.pending_reaction_window is not None:
            state, _ = ui.execute(state, '/react player-1 decline')
        player = state.actors['player-1']
        self.assertIsNone(player.readied_action)
        self.assertIsNone(player.concentrating_effect_id)
        self.assertTrue(any(isinstance(event, SaveRolledEvent) and event.resolution.request.context.reason == 'Maintain Concentration' for event in state.event_log))
        self.assertTrue(any(isinstance(event, ReadiedSpellDissipatedEvent) for event in state.event_log))

    def test_start_of_turn_simultaneous_effects_require_ordering_choice(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(6, 0), mage_position=GridPosition(9, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        control_runtime = self._build_control_runtime(runtime)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-skeleton-1')
        skeleton = state.actors['monster-skeleton-1']
        skeleton.readied_action = ReadiedActionState(
            trigger=ReadyTriggerState(trigger_kind=ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW, trigger_actor_id='player-1'),
            response=ReadyResponseState(response_kind=ReadyResponseKind.ATTACK, attack_id='shortsword', target_actor_id='player-1'),
            declared_round_number=state.round_number,
        )
        skeleton.capabilities['test-recharge'] = RuntimeCapabilityState(
            option_id='test-recharge',
            name='Test Recharge',
            source='test',
            kind=CapabilityKind.MONSTER_ACTION,
            action_cost='action',
            remaining_uses=0,
            capability=CapabilityDefinition(
                capability_id='test-recharge',
                name='Test Recharge',
                kind=CapabilityKind.MONSTER_ACTION,
                source='test',
                action_cost='action',
                targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF),
                effect=CompositeEffect(effects=()),
            ),
            recharge_min_roll=6,
            max_uses=1,
        )
        state, _ = ui.execute(state, '/endturn monster-skeleton-1')
        state, _ = ui.execute(state, '/endturn monster-mage-1')
        state, _ = ui.execute(state, '/endturn player-1')
        self.assertIsNotNone(state.pending_timing_queue)
        prompt = control_runtime.prompt_for_controller(state, 'dm')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertEqual(prompt.prompt_kind, 'timing-order')
        ordered_entry_id = next(option.option_id for option in prompt.options if 'ready-expire' in option.option_id)
        result = control_runtime.submit_intent(state, 'dm', ChooseTimingOrderIntent(actor_id='monster-skeleton-1', entry_id=ordered_entry_id))
        self.assertIsNone(result.prompt)
        self.assertIsNone(state.pending_timing_queue)
        self.assertIsNone(state.actors['monster-skeleton-1'].readied_action)
        self.assertTrue(any(isinstance(event, SimultaneousEffectsOrderedEvent) for event in state.event_log))


if __name__ == '__main__':
    unittest.main()
