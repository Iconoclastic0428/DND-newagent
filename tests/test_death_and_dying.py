from __future__ import annotations

import copy
from dataclasses import replace
import unittest

from player_interface import EncounterSlashCommandInterface
from shared_types.conditions import ConditionType
from shared_types.d20 import D20TestRequest, D20TestType
from shared_types.encounter_events import (
    DiedEvent,
    DeathSaveFailedEvent,
    DeathSaveNaturalOneEvent,
    DeathSaveNaturalTwentyEvent,
    DeathSaveRequestedEvent,
    DeathSaveRolledEvent,
    DeathSaveSucceededEvent,
    DamageAppliedEvent,
    HealingAppliedEvent,
    HealedFromZeroEvent,
    HitPointsDroppedToZeroEvent,
    InstantDeathTriggeredEvent,
    StabilizedEvent,
    StableBrokenByDamageEvent,
    TemporaryHitPointsAppliedEvent,
    TemporaryHitPointsReceivedAtZeroEvent,
    UnconsciousAtZeroAppliedEvent,
)
from shared_types.encounter_intents import ContinueTimingIntent, EndTurnIntent
from shared_types.encounter_models import (
    CharacterPlacement,
    DyingStateStatus,
    EncounterPhase,
    GridPosition,
    MonsterPlacement,
)
from shared_types.models import Ability
from tests.test_encounter_kernel import EncounterKernelTests


class DeathAndDyingTests(unittest.TestCase):
    def _helper(self) -> EncounterKernelTests:
        helper = EncounterKernelTests()
        helper.setUp = lambda: None
        return helper

    def _build_runtime(self):
        return self._helper()._build_runtime()

    def _build_player_record(self):
        return self._helper()._build_player_record()

    def _monster_id(self, runtime, *, name: str, source: str) -> str:
        return self._helper()._monster_id(runtime, name=name, source=source)

    def _build_state(self, **kwargs):
        return self._helper()._build_state(**kwargs)

    def _build_two_player_state(self):
        runtime = self._build_runtime()
        player_one = self._build_player_record()
        player_two = copy.deepcopy(player_one)
        player_two.record_id = 'level-1-character-p2'
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        state = runtime.new_state(
            characters=(
                CharacterPlacement(actor_id='player-1', record=player_one, position=GridPosition(0, 0)),
                CharacterPlacement(actor_id='player-2', record=player_two, position=GridPosition(1, 0)),
            ),
            monsters=(
                MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=GridPosition(6, 0)),
            ),
        )
        return runtime, state

    def _set_turn(self, state, *actor_ids: str) -> None:
        state.phase = EncounterPhase.IN_PROGRESS
        state.initiative_order = tuple(actor_ids)
        state.turn_index = 0
        state.round_number = 1
        state.active_actor_id = actor_ids[0] if actor_ids else None

    def _apply_damage(
        self,
        runtime,
        state,
        *,
        target_id: str,
        damage_total: int,
        source_actor_id: str = 'monster-skeleton-1',
        damage_type: str = 'slashing',
        critical_hit: bool = False,
    ) -> None:
        target = state.actors[target_id]
        hit_points_after, temp_hit_points_after, applied_damage_total, effect_events = runtime.kernel._damage_preview(
            state,
            target,
            damage_total,
            damage_type=damage_type,
        )
        for event in effect_events:
            runtime.kernel._apply_event(state, event)
        runtime.kernel._apply_event(
            state,
            DamageAppliedEvent(
                source_actor_id=source_actor_id,
                target_id=target_id,
                damage_total=damage_total,
                applied_damage_total=applied_damage_total,
                target_hit_points_after=hit_points_after,
                target_temp_hit_points_after=temp_hit_points_after,
                damage_type=damage_type,
                critical_hit=critical_hit,
            ),
        )

    def _drop_to_zero(self, runtime, state, actor_id: str = 'player-1'):
        self._apply_damage(runtime, state, target_id=actor_id, damage_total=state.actors[actor_id].current_hit_points)

    def _resolve_death_save_start_of_turn(self, runtime, state, actor_id: str = 'player-1') -> None:
        runtime.kernel.dispatch(state, EndTurnIntent(actor_id=actor_id))
        self.assertIsNotNone(state.pending_timing_queue)
        runtime.kernel.dispatch(state, ContinueTimingIntent(actor_id=actor_id))

    def _find_death_save_counter(self, runtime, predicate) -> int:
        request = D20TestRequest(
            request_id='test-death-save',
            test_type=D20TestType.DEATH_SAVE,
            actor_id='player-1',
            dc=10,
        )
        for counter in range(5000):
            resolution = runtime.kernel.d20_engine.resolve(request, random_counter=counter)
            if predicate(resolution.result):
                return counter
        raise AssertionError('No matching death-save counter found.')

    def _find_check_counter(self, runtime, state, *, actor_id: str, ability: Ability, dc: int, skill_name: str, predicate) -> int:
        original_counter = state.random_counter
        try:
            for counter in range(5000):
                state.random_counter = counter
                resolution = runtime.kernel.resolve_ability_check(
                    state,
                    actor_id=actor_id,
                    ability=ability,
                    dc=dc,
                    skill_name=skill_name,
                )
                if predicate(resolution.result):
                    return counter
        finally:
            state.random_counter = original_counter
        raise AssertionError('No matching ability-check counter found.')

    def test_dropping_to_zero_applies_unconscious_and_death_save_state(self) -> None:
        runtime, state = self._build_state()

        self._drop_to_zero(runtime, state)

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 0)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.AT_0_HP_UNCONSCIOUS)
        self.assertEqual(actor.dying_state.death_save_successes, 0)
        self.assertEqual(actor.dying_state.death_save_failures, 0)
        self.assertTrue(actor.eligible_for_death_saves)
        self.assertTrue(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, HitPointsDroppedToZeroEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, UnconsciousAtZeroAppliedEvent) for event in state.event_log))

    def test_massive_damage_triggers_instant_death(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        actor.current_hit_points = 1

        self._apply_damage(runtime, state, target_id='player-1', damage_total=actor.max_hit_points + actor.current_hit_points)

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 0)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.DEAD)
        self.assertTrue(actor.is_dead)
        self.assertFalse(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, InstantDeathTriggeredEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, DiedEvent) for event in state.event_log))
        self.assertFalse(any(isinstance(event, UnconsciousAtZeroAppliedEvent) for event in state.event_log))

    def test_death_save_success_counts_up(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)
        self._set_turn(state, 'player-1')
        state.random_counter = self._find_death_save_counter(runtime, lambda result: result.success and result.selected_roll not in {1, 20})

        self._resolve_death_save_start_of_turn(runtime, state)

        actor = state.actors['player-1']
        self.assertEqual(actor.dying_state.status, DyingStateStatus.AT_0_HP_UNCONSCIOUS)
        self.assertEqual(actor.dying_state.death_save_successes, 1)
        self.assertEqual(actor.dying_state.death_save_failures, 0)
        self.assertTrue(any(isinstance(event, DeathSaveRequestedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, DeathSaveRolledEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, DeathSaveSucceededEvent) for event in state.event_log))

    def test_three_successes_stabilize_the_actor(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)
        actor = state.actors['player-1']
        actor.dying_state = replace(actor.dying_state, death_save_successes=2)
        self._set_turn(state, 'player-1')
        state.random_counter = self._find_death_save_counter(runtime, lambda result: result.success and result.selected_roll not in {1, 20})

        self._resolve_death_save_start_of_turn(runtime, state)

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 0)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.STABLE_AT_0_HP)
        self.assertEqual(actor.dying_state.death_save_successes, 0)
        self.assertEqual(actor.dying_state.death_save_failures, 0)
        self.assertIn(actor.dying_state.stable_recovery_hours_remaining, {1, 2, 3, 4})
        self.assertTrue(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, StabilizedEvent) for event in state.event_log))

    def test_death_save_failure_and_three_failures_kill(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)
        self._set_turn(state, 'player-1')
        state.random_counter = self._find_death_save_counter(runtime, lambda result: (not result.success) and result.selected_roll not in {1, 20})

        self._resolve_death_save_start_of_turn(runtime, state)

        actor = state.actors['player-1']
        self.assertEqual(actor.dying_state.death_save_failures, 1)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.AT_0_HP_UNCONSCIOUS)
        self.assertTrue(any(isinstance(event, DeathSaveFailedEvent) for event in state.event_log))

        runtime_two, state_two = self._build_state()
        self._drop_to_zero(runtime_two, state_two)
        state_two.actors['player-1'].dying_state = replace(state_two.actors['player-1'].dying_state, death_save_failures=2)
        self._set_turn(state_two, 'player-1')
        state_two.random_counter = self._find_death_save_counter(runtime_two, lambda result: (not result.success) and result.selected_roll not in {1, 20})

        self._resolve_death_save_start_of_turn(runtime_two, state_two)

        actor_two = state_two.actors['player-1']
        self.assertEqual(actor_two.dying_state.status, DyingStateStatus.DEAD)
        self.assertTrue(any(isinstance(event, DiedEvent) for event in state_two.event_log))

    def test_death_save_natural_one_causes_two_failures(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)
        self._set_turn(state, 'player-1')
        state.random_counter = self._find_death_save_counter(runtime, lambda result: result.selected_roll == 1)

        self._resolve_death_save_start_of_turn(runtime, state)

        actor = state.actors['player-1']
        self.assertEqual(actor.dying_state.death_save_failures, 2)
        self.assertTrue(any(isinstance(event, DeathSaveNaturalOneEvent) for event in state.event_log))
        failure_event = next(event for event in state.event_log if isinstance(event, DeathSaveFailedEvent))
        self.assertEqual(failure_event.failures_added, 2)

    def test_death_save_natural_twenty_restores_one_hit_point(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)
        self._set_turn(state, 'player-1')
        state.random_counter = self._find_death_save_counter(runtime, lambda result: result.selected_roll == 20)

        self._resolve_death_save_start_of_turn(runtime, state)

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 1)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.ALIVE)
        self.assertEqual(actor.dying_state.death_save_successes, 0)
        self.assertEqual(actor.dying_state.death_save_failures, 0)
        self.assertFalse(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, DeathSaveNaturalTwentyEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, HealedFromZeroEvent) for event in state.event_log))

    def test_damage_at_zero_causes_failures_and_critical_hit_causes_two(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)

        self._apply_damage(runtime, state, target_id='player-1', damage_total=1)

        actor = state.actors['player-1']
        self.assertEqual(actor.dying_state.death_save_failures, 1)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.AT_0_HP_UNCONSCIOUS)

        runtime_two, state_two = self._build_state()
        self._drop_to_zero(runtime_two, state_two)
        self._apply_damage(runtime_two, state_two, target_id='player-1', damage_total=1, critical_hit=True)

        actor_two = state_two.actors['player-1']
        self.assertEqual(actor_two.dying_state.death_save_failures, 2)
        failure_event = next(event for event in state_two.event_log if isinstance(event, DeathSaveFailedEvent))
        self.assertEqual(failure_event.failures_added, 2)

    def test_damage_at_zero_equal_to_max_hit_points_kills_immediately(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)

        self._apply_damage(runtime, state, target_id='player-1', damage_total=state.actors['player-1'].max_hit_points)

        actor = state.actors['player-1']
        self.assertEqual(actor.dying_state.status, DyingStateStatus.DEAD)
        self.assertTrue(any(isinstance(event, InstantDeathTriggeredEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, DiedEvent) for event in state.event_log))

    def test_help_medicine_stabilizes_and_damage_breaks_stability(self) -> None:
        runtime, state = self._build_two_player_state()
        self._drop_to_zero(runtime, state, actor_id='player-1')
        self._set_turn(state, 'player-2', 'player-1')
        state.random_counter = self._find_check_counter(
            runtime,
            state,
            actor_id='player-2',
            ability=Ability.WIS,
            dc=10,
            skill_name='Medicine',
            predicate=lambda result: result.success,
        )
        ui = EncounterSlashCommandInterface(runtime.kernel)

        state, _ = ui.execute(state, '/help player-2 player-1')

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 0)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.STABLE_AT_0_HP)
        self.assertIn(actor.dying_state.stable_recovery_hours_remaining, {1, 2, 3, 4})
        self.assertTrue(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, StabilizedEvent) for event in state.event_log))

        self._apply_damage(runtime, state, target_id='player-1', damage_total=1)

        actor = state.actors['player-1']
        self.assertEqual(actor.dying_state.status, DyingStateStatus.AT_0_HP_UNCONSCIOUS)
        self.assertEqual(actor.dying_state.death_save_failures, 1)
        self.assertTrue(any(isinstance(event, StableBrokenByDamageEvent) for event in state.event_log))

    def test_healing_from_zero_resets_counters_and_leaves_prone(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)
        actor = state.actors['player-1']
        actor.dying_state = replace(actor.dying_state, death_save_successes=1, death_save_failures=2)

        runtime.kernel._apply_event(
            state,
            HealingAppliedEvent(source_actor_id='player-1', target_id='player-1', healing_total=3, target_hit_points_after=3),
        )

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 3)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.ALIVE)
        self.assertEqual(actor.dying_state.death_save_successes, 0)
        self.assertEqual(actor.dying_state.death_save_failures, 0)
        self.assertFalse(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(instance.condition_type == ConditionType.PRONE for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, HealedFromZeroEvent) for event in state.event_log))

    def test_temporary_hit_points_at_zero_do_not_restore_consciousness(self) -> None:
        runtime, state = self._build_state()
        self._drop_to_zero(runtime, state)

        runtime.kernel._apply_event(
            state,
            TemporaryHitPointsAppliedEvent(source_actor_id='player-1', target_id='player-1', temp_hit_points_total=5),
        )

        actor = state.actors['player-1']
        self.assertEqual(actor.current_hit_points, 0)
        self.assertEqual(actor.temp_hit_points, 5)
        self.assertEqual(actor.dying_state.status, DyingStateStatus.AT_0_HP_UNCONSCIOUS)
        self.assertTrue(any(instance.condition_type == ConditionType.UNCONSCIOUS for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, TemporaryHitPointsReceivedAtZeroEvent) for event in state.event_log))

    def test_death_save_flow_is_deterministic_for_same_seed_and_counter(self) -> None:
        runtime_one, state_one = self._build_state()
        runtime_two, state_two = self._build_state()
        self._drop_to_zero(runtime_one, state_one)
        self._drop_to_zero(runtime_two, state_two)
        self._set_turn(state_one, 'player-1')
        self._set_turn(state_two, 'player-1')
        counter = self._find_death_save_counter(runtime_one, lambda result: result.success and result.selected_roll not in {1, 20})
        state_one.random_counter = counter
        state_two.random_counter = counter

        self._resolve_death_save_start_of_turn(runtime_one, state_one)
        self._resolve_death_save_start_of_turn(runtime_two, state_two)

        roll_one = next(event for event in state_one.event_log if isinstance(event, DeathSaveRolledEvent))
        roll_two = next(event for event in state_two.event_log if isinstance(event, DeathSaveRolledEvent))
        self.assertEqual(roll_one.rolls, roll_two.rolls)
        self.assertEqual(roll_one.selected_roll, roll_two.selected_roll)
        self.assertEqual(state_one.actors['player-1'].dying_state, state_two.actors['player-1'].dying_state)


if __name__ == '__main__':
    unittest.main()
