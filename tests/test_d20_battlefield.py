from __future__ import annotations

import copy
import unittest

from encounter_runtime.battlefield import BattlefieldRules
from encounter_runtime.d20_engine import D20TestEngine
from encounter_runtime.conditions import has_condition
from player_interface import EncounterSlashCommandInterface
from shared_types.battlefield import CoverLevel
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType
from shared_types.encounter_events import (
    AttackDeclaredEvent,
    AttackHitEvent,
    AttackMissedEvent,
    D20TestRolledEvent,
    DamageAppliedEvent,
    DamageRolledEvent,
    MoveDeclaredEvent,
    StoodFromProneEvent,
)
from shared_types.encounter_models import AttackKind, EncounterPhase, GridPosition
from shared_types.errors import EncounterValidationError, UnknownEncounterCommandError
from shared_types.models import Ability
from tests.test_encounter_kernel import EncounterKernelTests


class D20AndBattlefieldTests(unittest.TestCase):
    def _helper(self) -> EncounterKernelTests:
        helper = EncounterKernelTests()
        helper.setUp = lambda: None
        return helper

    def _build_state(self, **kwargs):
        return self._helper()._build_state(**kwargs)

    def _advance_to_actor(self, ui, state, actor_id: str):
        return self._helper()._advance_to_actor(ui, state, actor_id)

    def _instance(self, actor_id: str, condition_type: ConditionType, **kwargs) -> ConditionInstance:
        source_actor_id = kwargs.get('source_actor_id') or 'test-source'
        source_token = kwargs.get('source_effect_id') or kwargs.get('source_label') or condition_type.value
        return ConditionInstance(
            instance_id=f'{actor_id}:{condition_type.value}:{source_actor_id}:{source_token}',
            condition_type=condition_type,
            source_actor_id=kwargs.get('source_actor_id'),
            source_effect_id=kwargs.get('source_effect_id'),
            source_label=kwargs.get('source_label'),
            charmer_actor_id=kwargs.get('charmer_actor_id'),
            fear_source_actor_id=kwargs.get('fear_source_actor_id'),
            grappler_actor_id=kwargs.get('grappler_actor_id'),
        )

    def _find_ranged_attack(self, actor) -> str:
        for attack in actor.attacks.values():
            if attack.attack_kind != AttackKind.MELEE and (attack.range_ft is not None or attack.long_range_ft is not None):
                return attack.attack_id
        raise AssertionError(f'No ranged attack found for actor {actor.actor_id}')

    def test_generic_d20_roll_modes_and_determinism(self) -> None:
        engine = D20TestEngine(seed='d20-test-seed')
        normal = engine.resolve(D20TestRequest(request_id='normal', test_type=D20TestType.ABILITY_CHECK, actor_id='a', ability=Ability.WIS), random_counter=12)
        advantage = engine.resolve(D20TestRequest(request_id='adv', test_type=D20TestType.ABILITY_CHECK, actor_id='a', ability=Ability.WIS, roll_mode=D20RollMode.ADVANTAGE), random_counter=12)
        disadvantage = engine.resolve(D20TestRequest(request_id='dis', test_type=D20TestType.ABILITY_CHECK, actor_id='a', ability=Ability.WIS, roll_mode=D20RollMode.DISADVANTAGE), random_counter=12)
        repeat = engine.resolve(D20TestRequest(request_id='adv', test_type=D20TestType.ABILITY_CHECK, actor_id='a', ability=Ability.WIS, roll_mode=D20RollMode.ADVANTAGE), random_counter=12)

        self.assertEqual(len(normal.result.rolls), 1)
        self.assertEqual(len(advantage.result.rolls), 2)
        self.assertEqual(advantage.result.selected_roll, max(advantage.result.rolls))
        self.assertEqual(disadvantage.result.selected_roll, min(disadvantage.result.rolls))
        self.assertEqual(advantage.result, repeat.result)

    def test_save_and_check_hooks_integrate_condition_effects(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        actor.condition_instances = (
            self._instance(actor.actor_id, ConditionType.PARALYZED),
            self._instance(actor.actor_id, ConditionType.FRIGHTENED, fear_source_actor_id='monster-skeleton-1'),
        )
        save_resolution = runtime.kernel.resolve_saving_throw(state, actor_id=actor.actor_id, ability=Ability.DEX, dc=15)
        check_resolution = runtime.kernel.resolve_ability_check(state, actor_id=actor.actor_id, ability=Ability.WIS, dc=10, skill_name='Perception')
        self.assertTrue(save_resolution.result.auto_fail)
        self.assertEqual(len(check_resolution.result.rolls), 2)
        self.assertEqual(check_resolution.result.roll_mode, D20RollMode.DISADVANTAGE)

    def test_proficient_skill_checks_use_compiled_skill_bonus(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        skill_name = 'Arcana'
        skill_resolution = runtime.kernel.resolve_ability_check(state, actor_id=actor.actor_id, ability=Ability.INT, dc=10, skill_name=skill_name)
        ability_resolution = runtime.kernel.resolve_ability_check(state, actor_id=actor.actor_id, ability=Ability.INT, dc=10)

        self.assertEqual(skill_resolution.result.rolls, ability_resolution.result.rolls)
        self.assertEqual(skill_resolution.result.selected_roll, ability_resolution.result.selected_roll)
        self.assertEqual(
            skill_resolution.result.total - ability_resolution.result.total,
            actor.skill_bonuses[skill_name] - actor.ability_modifiers[Ability.INT],
        )
        self.assertEqual(
            skill_resolution.result.total,
            skill_resolution.result.selected_roll + actor.skill_bonuses[skill_name],
        )

    def test_attack_roll_vs_ac_and_typed_attack_events(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(1, 0), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        if state.active_actor_id != 'monster-skeleton-1':
            state, _ = self._advance_to_actor(ui, state, 'monster-skeleton-1')
        state, _ = ui.execute(state, '/attack monster-skeleton-1 shortsword player-1')
        event_types = {type(event) for event in state.event_log}
        self.assertIn(AttackDeclaredEvent, event_types)
        self.assertIn(D20TestRolledEvent, event_types)
        self.assertTrue(AttackHitEvent in event_types or AttackMissedEvent in event_types)

    def test_critical_hit_handling_and_damage_application(self) -> None:
        runtime, base_state = self._build_state(player_position=GridPosition(1, 0), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        base_state, _ = ui.execute(base_state, '/encounter start')
        if base_state.active_actor_id != 'monster-skeleton-1':
            base_state, _ = self._advance_to_actor(ui, base_state, 'monster-skeleton-1')
        critical_state = None
        for counter in range(1000):
            state = copy.deepcopy(base_state)
            state.random_counter = counter
            state.actors['player-1'].temp_hit_points = 3
            state, _ = ui.execute(state, '/attack monster-skeleton-1 shortsword player-1')
            if any(
                isinstance(event, D20TestRolledEvent)
                and event.result.test_type == D20TestType.ATTACK
                and event.result.critical_success
                for event in state.event_log
            ):
                if state.pending_reaction_window is not None:
                    state, _ = ui.execute(state, '/react player-1 decline')
                critical_state = state
                break
        self.assertIsNotNone(critical_state)
        assert critical_state is not None
        damage_event = next(event for event in critical_state.event_log if isinstance(event, DamageRolledEvent))
        self.assertGreaterEqual(len(damage_event.damage_rolls), 2)
        self.assertEqual(critical_state.actors['player-1'].temp_hit_points, 0)
        self.assertLess(critical_state.actors['player-1'].current_hit_points, critical_state.actors['player-1'].max_hit_points)
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) for event in critical_state.event_log))

    def test_melee_reach_and_ranged_range_validation(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(6, 0), mage_position=GridPosition(8, 2))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/attack monster-skeleton-1 shortsword player-1')

        ranged_attack_id = self._find_ranged_attack(state.actors['monster-skeleton-1'])
        ranged_attack = state.actors['monster-skeleton-1'].attacks[ranged_attack_id]
        far_tiles = ((ranged_attack.long_range_ft or ranged_attack.range_ft or 5) // 5) + 2
        runtime_far, state_far = self._build_state(player_position=GridPosition(far_tiles, 0), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(8, 2))
        ui_far = EncounterSlashCommandInterface(runtime_far.kernel)
        state_far, _ = ui_far.execute(state_far, '/encounter start')
        with self.assertRaises(EncounterValidationError):
            ui_far.execute(state_far, f'/attack monster-skeleton-1 {ranged_attack_id} player-1')

    def test_movement_spending_difficult_terrain_and_blocked_speed_zero(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(8, 0), mage_position=GridPosition(8, 2))
        state.battlefield.difficult_terrain_positions = frozenset({GridPosition(1, 0)})
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/move player-1 2 0')
        self.assertEqual(state.actors['player-1'].remaining_movement_ft, 20)
        self.assertIsInstance(next(event for event in state.event_log if isinstance(event, MoveDeclaredEvent)), MoveDeclaredEvent)

        blocked_runtime, blocked_state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(8, 0), mage_position=GridPosition(8, 2))
        blocked_state.actors['player-1'].condition_instances = (self._instance('player-1', ConditionType.GRAPPLED, grappler_actor_id='monster-skeleton-1'),)
        blocked_ui = EncounterSlashCommandInterface(blocked_runtime.kernel)
        blocked_state, _ = blocked_ui.execute(blocked_state, '/encounter start')
        blocked_state, _ = self._advance_to_actor(blocked_ui, blocked_state, 'player-1')
        with self.assertRaises(EncounterValidationError):
            blocked_ui.execute(blocked_state, '/move player-1 1 0')

    def test_stand_from_prone_legality_cost_and_events(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(8, 0), mage_position=GridPosition(8, 2))
        actor = state.actors['player-1']
        actor.condition_instances = (self._instance(actor.actor_id, ConditionType.PRONE),)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/stand player-1')
        self.assertFalse(has_condition(state.actors['player-1'], ConditionType.PRONE))
        self.assertEqual(state.actors['player-1'].remaining_movement_ft, 15)
        self.assertTrue(any(isinstance(event, StoodFromProneEvent) for event in state.event_log))

        blocked_runtime, blocked_state = self._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(8, 0), mage_position=GridPosition(8, 2))
        blocked_actor = blocked_state.actors['player-1']
        blocked_actor.condition_instances = (
            self._instance(blocked_actor.actor_id, ConditionType.PRONE),
            self._instance(blocked_actor.actor_id, ConditionType.GRAPPLED, grappler_actor_id='monster-skeleton-1'),
        )
        blocked_ui = EncounterSlashCommandInterface(blocked_runtime.kernel)
        blocked_state, _ = blocked_ui.execute(blocked_state, '/encounter start')
        blocked_state, _ = self._advance_to_actor(blocked_ui, blocked_state, 'player-1')
        with self.assertRaises(EncounterValidationError):
            blocked_ui.execute(blocked_state, '/stand player-1')

    def test_cover_and_slash_validation(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(1, 0), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(8, 2))
        state.battlefield.cover_by_pair[('monster-skeleton-1', 'player-1')] = CoverLevel.HALF
        legality = BattlefieldRules().attack_legality(state, state.actors['monster-skeleton-1'], state.actors['player-1'], state.actors['monster-skeleton-1'].attacks['shortsword'])
        self.assertEqual(legality.armor_class_bonus, 2)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        with self.assertRaises(UnknownEncounterCommandError):
            ui.parse_command('/stand')

    def test_deterministic_replay_behavior_for_attack_sequence(self) -> None:
        runtime_one, state_one = self._build_state(player_position=GridPosition(1, 0), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(8, 2))
        runtime_two, state_two = self._build_state(player_position=GridPosition(1, 0), skeleton_position=GridPosition(0, 0), mage_position=GridPosition(8, 2))
        ui_one = EncounterSlashCommandInterface(runtime_one.kernel)
        ui_two = EncounterSlashCommandInterface(runtime_two.kernel)
        for ui, state in ((ui_one, state_one), (ui_two, state_two)):
            pass
        state_one, output_one = ui_one.execute(state_one, '/encounter start')
        state_two, output_two = ui_two.execute(state_two, '/encounter start')
        if state_one.active_actor_id != 'monster-skeleton-1':
            state_one, _ = self._advance_to_actor(ui_one, state_one, 'monster-skeleton-1')
        if state_two.active_actor_id != 'monster-skeleton-1':
            state_two, _ = self._advance_to_actor(ui_two, state_two, 'monster-skeleton-1')
        state_one, attack_output_one = ui_one.execute(state_one, '/attack monster-skeleton-1 shortsword player-1')
        state_two, attack_output_two = ui_two.execute(state_two, '/attack monster-skeleton-1 shortsword player-1')
        self.assertEqual(output_one, output_two)
        self.assertEqual(attack_output_one, attack_output_two)
        self.assertEqual(state_one.actors['player-1'].current_hit_points, state_two.actors['player-1'].current_hit_points)
        self.assertEqual(state_one.event_log, state_two.event_log)


if __name__ == '__main__':
    unittest.main()
