from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from character_creation import build_default_kernel
from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface, SlashCommandInterface
from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from session_server import EncounterSession
from session_server.web_projection import project_encounter_session_view
from shared_types.capabilities import TriggerTiming
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.encounter_control import ControllerBinding, ControllerPrompt, ControllerRole, PromptOption, PromptRecipient
from shared_types.encounter_intents import ChooseTimingOrderIntent
from shared_types.encounter_events import DamageAppliedEvent, ReactionRejectedEvent
from shared_types.encounter_models import CharacterPlacement, DyingState, DyingStateStatus, GridPosition, MonsterPlacement, PendingTimingQueueState, TimingEntryKind, TimingEntryState
from shared_types.errors import EncounterOwnershipError, EncounterPermissionError


LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class EncounterSessionTests(unittest.TestCase):
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

    def _controllers(self):
        controllers = {
            'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
            'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
        }
        actor_controllers = {
            'player-1': 'player-1-controller',
            'monster-skeleton-1': 'dm',
            'monster-mage-1': 'dm',
        }
        return controllers, actor_controllers

    def _build_session(self):
        runtime = self._build_runtime()
        record = self._build_player_record()
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        mage_id = self._monster_id(runtime, name='Mage', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=GridPosition(0, 0)),),
            monsters=(
                MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=GridPosition(6, 0)),
                MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=GridPosition(8, 2)),
            ),
        )
        controllers, actor_controllers = self._controllers()
        control_runtime = runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)
        command_interface = EncounterSlashCommandInterface(runtime.kernel)
        return EncounterSession(state=state, control_runtime=control_runtime, command_interface=command_interface)

    def _build_battlefield_session(self):
        runtime = self._build_runtime()
        record = self._build_player_record()
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        mage_id = self._monster_id(runtime, name='Mage', source='XMM')
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=battlefield.spawn_zones['players'][0]),),
            monsters=(
                MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=battlefield.spawn_zones['goblinNorth'][0]),
                MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=battlefield.spawn_zones['goblinSouth'][0]),
            ),
            battlefield=battlefield,
        )
        controllers, actor_controllers = self._controllers()
        control_runtime = runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)
        command_interface = EncounterSlashCommandInterface(runtime.kernel)
        return EncounterSession(state=state, control_runtime=control_runtime, command_interface=command_interface)

    def test_missing_actor_binding_is_rejected(self) -> None:
        runtime = self._build_runtime()
        record = self._build_player_record()
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=GridPosition(0, 0)),),
            monsters=(MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=GridPosition(6, 0)),),
        )
        controllers = {
            'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
            'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
        }
        actor_controllers = {
            'player-1': 'player-1-controller',
        }
        with self.assertRaises(EncounterOwnershipError):
            EncounterSession(
                state=state,
                control_runtime=runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers),
                command_interface=EncounterSlashCommandInterface(runtime.kernel),
            )

    def test_player_cannot_control_monster(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        with self.assertRaises(EncounterPermissionError):
            session.execute_for_controller('player-1-controller', '/dash monster-skeleton-1')

    def test_dm_cannot_control_player(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        with self.assertRaises(EncounterPermissionError):
            session.execute_for_controller('dm', '/endturn player-1')

    def test_owner_can_control_owned_actor(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        dm_view = session.execute_for_controller('dm', '/dash monster-skeleton-1').view
        self.assertIn('monster-skeleton-1', '\n'.join(dm_view.summary_lines))
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        player_view = session.execute_for_controller('player-1-controller', '/endturn player-1').view
        self.assertIn('Active actor: monster-skeleton-1', '\n'.join(player_view.summary_lines))

    def test_recent_damage_events_keep_recorded_hp_after_later_damage(self) -> None:
        session = self._build_session()
        target = session.state.actors['monster-skeleton-1']
        target.current_hit_points = 4
        session.state.event_log.append(
            DamageAppliedEvent(
                source_actor_id='player-1',
                target_id='monster-skeleton-1',
                damage_total=6,
                applied_damage_total=6,
                target_hit_points_after=4,
                target_temp_hit_points_after=0,
                damage_type='force',
            )
        )
        target.current_hit_points = 0
        session.state.event_log.append(
            DamageAppliedEvent(
                source_actor_id='player-1',
                target_id='monster-skeleton-1',
                damage_total=4,
                applied_damage_total=4,
                target_hit_points_after=0,
                target_temp_hit_points_after=0,
                damage_type='fire',
            )
        )

        summary = '\n'.join(session.view_for_controller('dm').summary_lines)

        self.assertIn(f'Skeleton takes 6 force damage; HP 4/{target.max_hit_points}, Temp 0.', summary)
        self.assertIn(f'Skeleton takes 4 fire damage; HP 0/{target.max_hit_points}, Temp 0.', summary)
        self.assertNotIn(f'Skeleton takes 6 force damage; HP 0/{target.max_hit_points}, Temp 0.', summary)

    def test_combat_chat_entry_ids_stay_stable_when_recent_window_slides(self) -> None:
        session = self._build_session()
        target = session.state.actors['monster-skeleton-1']
        for event_index in range(12):
            session.state.event_log.append(
                DamageAppliedEvent(
                    source_actor_id='player-1',
                    target_id='monster-skeleton-1',
                    damage_total=event_index + 1,
                    applied_damage_total=event_index + 1,
                    target_hit_points_after=max(0, target.max_hit_points - event_index - 1),
                    target_temp_hit_points_after=0,
                    damage_type='force',
                )
            )
        before_entries = [
            entry
            for entry in project_encounter_session_view(session, 'dm', session_id='combat-chat-ids').chat_entries
            if entry.category == 'combat'
        ]
        tracked_entry = before_entries[1]

        session.state.event_log.append(
            DamageAppliedEvent(
                source_actor_id='player-1',
                target_id='monster-skeleton-1',
                damage_total=13,
                applied_damage_total=13,
                target_hit_points_after=0,
                target_temp_hit_points_after=0,
                damage_type='force',
            )
        )
        after_entries = [
            entry
            for entry in project_encounter_session_view(session, 'dm', session_id='combat-chat-ids').chat_entries
            if entry.category == 'combat'
        ]
        after_by_id = {entry.entry_id: entry.text for entry in after_entries}

        self.assertIn(tracked_entry.entry_id, after_by_id)
        self.assertEqual(after_by_id[tracked_entry.entry_id], tracked_entry.text)

    def test_combat_chat_entry_ids_are_scoped_by_web_session(self) -> None:
        session = self._build_session()
        target = session.state.actors['monster-skeleton-1']
        session.state.event_log.append(
            DamageAppliedEvent(
                source_actor_id='player-1',
                target_id='monster-skeleton-1',
                damage_total=3,
                applied_damage_total=3,
                target_hit_points_after=target.max_hit_points - 3,
                target_temp_hit_points_after=0,
                damage_type='force',
            )
        )

        first_id = [
            entry.entry_id
            for entry in project_encounter_session_view(session, 'dm', session_id='combat-a').chat_entries
            if entry.category == 'combat'
        ][0]
        second_id = [
            entry.entry_id
            for entry in project_encounter_session_view(session, 'dm', session_id='combat-b').chat_entries
            if entry.category == 'combat'
        ][0]

        self.assertEqual(first_id, 'combat-a:encounter-event:0')
        self.assertEqual(second_id, 'combat-b:encounter-event:0')

    def test_reaction_prompt_only_visible_to_owner(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/move monster-skeleton-1 1 0')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        session.execute_for_controller('player-1-controller', '/move player-1 3 0')
        self.assertIsNotNone(session.prompt_for_controller('dm'))
        self.assertIsNone(session.prompt_for_controller('player-1-controller'))

    def test_timing_order_prompt_only_visible_to_owner_and_suppresses_action_choices(self) -> None:
        session = self._build_session()
        session.state.pending_timing_queue = PendingTimingQueueState(
            actor_id='player-1',
            phase=TriggerTiming.START_OF_TURN,
            entries=(
                TimingEntryState(
                    entry_id='effect-expire',
                    actor_id='player-1',
                    phase=TriggerTiming.START_OF_TURN,
                    kind=TimingEntryKind.ACTIVE_EFFECT_EXPIRE,
                    label='Bless expires',
                ),
                TimingEntryState(
                    entry_id='effect-trigger',
                    actor_id='player-1',
                    phase=TriggerTiming.START_OF_TURN,
                    kind=TimingEntryKind.ACTIVE_EFFECT_TRIGGER,
                    label='Regeneration trigger',
                ),
            ),
        )

        prompt = session.prompt_for_controller('player-1-controller')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertEqual(prompt.prompt_kind, 'timing-order')
        self.assertEqual([option.option_id for option in prompt.options], ['effect-expire', 'effect-trigger'])
        self.assertIsNone(session.prompt_for_controller('dm'))

        player_view = session.view_for_controller('player-1-controller')
        rendered = '\n'.join(player_view.summary_lines)
        self.assertIn('Pending timing order prompt: waiting on Player 1.', rendered)
        self.assertIn('Timing order prompt: Choose the next start-of-turn effect to resolve.', rendered)
        self.assertEqual(player_view.available_choices, {})

    def test_timing_order_prompt_response_submits_choose_timing_intent(self) -> None:
        session = self._build_session()
        prompt = ControllerPrompt(
            prompt_id='timing:player-1:start-of-turn',
            prompt_kind='timing-order',
            prompt='Choose the next start-of-turn effect to resolve.',
            recipients=(
                PromptRecipient(
                    controller_id='player-1-controller',
                    role=ControllerRole.PLAYER,
                    label='Player 1',
                    actor_ids=('player-1',),
                ),
            ),
            options=(
                PromptOption(option_id='effect-expire', label='Bless expires', detail='active-effect-expire', actor_id='player-1'),
                PromptOption(option_id='effect-trigger', label='Regeneration trigger', detail='active-effect-trigger', actor_id='player-1'),
            ),
        )
        submitted: list[ChooseTimingOrderIntent] = []
        original_prompt_for_controller = session.prompt_for_controller
        original_submit_intent = session.control_runtime.submit_intent
        session.prompt_for_controller = lambda controller_id: prompt if controller_id == 'player-1-controller' else None

        def fake_submit_intent(state, controller_id, intent, reaction_decider=None):
            self.assertEqual(controller_id, 'player-1-controller')
            submitted.append(intent)
            return None

        session.control_runtime.submit_intent = fake_submit_intent
        try:
            session.respond_to_prompt('player-1-controller', ['effect-trigger'])
        finally:
            session.prompt_for_controller = original_prompt_for_controller
            session.control_runtime.submit_intent = original_submit_intent

        self.assertEqual(len(submitted), 1)
        self.assertIsInstance(submitted[0], ChooseTimingOrderIntent)
        self.assertEqual(submitted[0].actor_id, 'player-1')
        self.assertEqual(submitted[0].entry_id, 'effect-trigger')
    def test_player_view_hides_monster_private_state(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        player_view = session.view_for_controller('player-1-controller')
        rendered = '\n'.join(player_view.summary_lines)
        self.assertIn('monster-skeleton-1: Skeleton [monster] Pos (6,0,0); Status active', rendered)
        self.assertNotIn('monster-skeleton-1: Skeleton [monster] HP 13/13', rendered)
        self.assertNotIn('attacks:', rendered)

    def test_dm_view_shows_monster_private_state_but_not_player_choices(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        dm_view = session.view_for_controller('dm')
        rendered = '\n'.join(dm_view.summary_lines)
        self.assertIn('monster-skeleton-1: Skeleton [monster] HP 13/13', rendered)
        self.assertNotIn('actions:', rendered)

    def test_player_projection_hides_monster_private_state_and_exposes_semantic_cells(self) -> None:
        session = self._build_battlefield_session()
        session.system_execute('/encounter start')
        view = session.view_for_controller('player-1-controller')
        projection = view.projection
        self.assertIsNotNone(projection)
        assert projection is not None
        self.assertIsNotNone(projection.battlefield)
        assert projection.battlefield is not None
        self.assertEqual(projection.battlefield.map_id, 'triboar_trail_goblin_ambush_v1')
        road_cell = next(cell for cell in projection.battlefield.cells if (cell.x, cell.y) == (12, 15))
        self.assertEqual(road_cell.terrain_id, 'lower_road')
        self.assertEqual(road_cell.elevation_ft, 0)
        monster = next(actor for actor in projection.actors if actor.public.actor_id == 'monster-skeleton-1')
        player = next(actor for actor in projection.actors if actor.public.actor_id == 'player-1')
        self.assertIsNone(monster.private_state)
        self.assertIsNotNone(player.private_state)

    def test_dm_projection_keeps_player_private_state_hidden_but_shows_monster_private_state(self) -> None:
        session = self._build_battlefield_session()
        session.system_execute('/encounter start')
        projection = session.view_for_controller('dm').projection
        self.assertIsNotNone(projection)
        assert projection is not None
        monster = next(actor for actor in projection.actors if actor.public.actor_id == 'monster-skeleton-1')
        player = next(actor for actor in projection.actors if actor.public.actor_id == 'player-1')
        self.assertIsNotNone(monster.private_state)
        self.assertIsNone(player.private_state)

    def test_projection_choice_groups_only_visible_to_active_owner(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        player_projection = session.view_for_controller('player-1-controller').projection
        dm_projection = session.view_for_controller('dm').projection
        self.assertIsNotNone(player_projection)
        self.assertIsNotNone(dm_projection)
        assert player_projection is not None
        assert dm_projection is not None
        self.assertIn('actions', {group.group_id for group in player_projection.choice_groups})
        self.assertEqual(dm_projection.choice_groups, ())

    def test_owner_and_dm_views_surface_dying_state_without_leaking_player_private_projection(self) -> None:
        session = self._build_session()
        actor = session.state.actors['player-1']
        actor.current_hit_points = 0
        actor.dying_state = DyingState(
            status=DyingStateStatus.AT_0_HP_UNCONSCIOUS,
            death_save_successes=1,
            death_save_failures=2,
        )
        actor.condition_instances = (
            ConditionInstance(instance_id='zero-hit-points-unconscious:player-1', condition_type=ConditionType.UNCONSCIOUS, source_label='zero-hit-points'),
        )

        player_view = session.view_for_controller('player-1-controller')
        dm_view = session.view_for_controller('dm')

        player_rendered = '\n'.join(player_view.summary_lines)
        dm_rendered = '\n'.join(dm_view.summary_lines)
        self.assertIn('Dying at-0-hp-unconscious; Death saves 1/2', player_rendered)
        self.assertIn('Status unconscious; Death saves 1/2', dm_rendered)

        player_projection = player_view.projection
        dm_projection = dm_view.projection
        self.assertIsNotNone(player_projection)
        self.assertIsNotNone(dm_projection)
        assert player_projection is not None
        assert dm_projection is not None
        player_actor = next(actor for actor in player_projection.actors if actor.public.actor_id == 'player-1')
        dm_actor = next(actor for actor in dm_projection.actors if actor.public.actor_id == 'player-1')
        self.assertIsNotNone(player_actor.private_state)
        self.assertIsNone(dm_actor.private_state)
        assert player_actor.private_state is not None
        self.assertEqual(player_actor.private_state.dying_status, 'at-0-hp-unconscious')
        self.assertEqual(player_actor.private_state.death_save_successes, 1)
        self.assertEqual(player_actor.private_state.death_save_failures, 2)

    def test_reaction_resolution_is_visible_in_controller_view(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/move monster-skeleton-1 1 0')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        session.execute_for_controller('player-1-controller', '/move player-1 3 0')
        prompt = session.prompt_for_controller('dm')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        option_id = next(option.option_id for option in prompt.options if option.option_id != 'decline')
        dm_view = session.respond_to_prompt('dm', option_id).view
        rendered = '\n'.join(dm_view.summary_lines)
        self.assertIn('Recent events:', rendered)
        self.assertIn('Opportunity Attack (Shortsword)', rendered)
        self.assertTrue('Shortsword hits' in rendered or 'Shortsword misses' in rendered)

    def test_fall_resolution_is_visible_in_controller_view(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        dm_view = session.execute_for_controller('dm', '/cast monster-mage-1 misty-step 5 2 10').view
        rendered = '\n'.join(dm_view.summary_lines)
        self.assertIn('teleports to (5,2,10)', rendered)
        self.assertIn('starts falling', rendered)
        self.assertIn('falls 10 ft', rendered)
        self.assertIn('lands at (5,2,0)', rendered)

    def test_comma_separated_multi_reaction_selection_resolves_subset(self) -> None:
        session = self._build_session()
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(0, 1)
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        session.execute_for_controller('player-1-controller', '/move player-1 3 0')
        prompt = session.prompt_for_controller('dm')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        selected: list[str] = []
        chosen_actor_ids: set[str] = set()
        for option in prompt.options:
            if option.actor_id in chosen_actor_ids:
                continue
            selected.append(option.option_id)
            chosen_actor_ids.add(option.actor_id)
        self.assertGreaterEqual(len(selected), 2)
        dm_view = session.respond_to_prompt('dm', selected).view
        rendered = '\n'.join(dm_view.summary_lines)
        self.assertIsNone(session.prompt_for_controller('dm'))
        self.assertIn('Recent events:', rendered)
        self.assertIn('Opportunity Attack', rendered)
        self.assertGreaterEqual(rendered.count('triggered Opportunity Attack'), 2)

    def test_multi_reaction_submission_revalidates_after_earlier_reaction_changes_state(self) -> None:
        session = self._build_session()
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(0, 1)
        session.state.actors['player-1'].current_hit_points = 1
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        session.execute_for_controller('player-1-controller', '/move player-1 3 0')
        prompt = session.prompt_for_controller('dm')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        selected: list[str] = []
        chosen_actor_ids: list[str] = []
        for option in prompt.options:
            if option.actor_id in chosen_actor_ids:
                continue
            chosen_actor_ids.append(option.actor_id)
            selected.append(option.option_id)
        self.assertGreaterEqual(len(selected), 2)
        first_actor_id = chosen_actor_ids[0]
        second_actor_id = chosen_actor_ids[1]
        first_option = next(option for option in prompt.options if option.actor_id == first_actor_id)
        first_attack_id = first_option.option_id.split(':', 2)[2]
        first_actor = session.state.actors[first_actor_id]
        first_attack = first_actor.attacks[first_attack_id]
        first_actor.attacks[first_attack_id] = replace(first_attack, to_hit_bonus=100, damage_bonus=100)
        dm_view = session.respond_to_prompt('dm', selected).view
        rendered = '\n'.join(dm_view.summary_lines)
        self.assertIn('Recent events:', rendered)
        self.assertFalse(session.state.actors[first_actor_id].reaction_available)
        self.assertTrue(session.state.actors[second_actor_id].reaction_available)


if __name__ == '__main__':
    unittest.main()


