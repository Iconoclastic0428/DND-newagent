from __future__ import annotations

import unittest

from encounter_runtime.conditions import (
    add_condition,
    apply_damage_modifiers,
    get_ability_check_modifiers_or_auto_fail,
    get_attack_roll_modifiers,
    get_condition_state,
    get_effective_speed,
    get_initiative_modifiers,
    get_saving_throw_modifiers_or_auto_fail,
    get_targeting_visibility_legality,
    has_condition,
    validate_frightened_movement,
    validate_hostile_targeting,
)
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.encounter_events import ConcentrationBrokenEvent, ConditionAddedEvent, ConditionRemovedEvent, MovementSpentEvent
from shared_types.encounter_intents import MoveActorIntent, TakeCombatActionIntent
from shared_types.encounter_models import CombatActionType, EncounterPhase, GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.test_encounter_kernel import EncounterKernelTests


class ConditionRuntimeTests(unittest.TestCase):
    def _build_state(self):
        helper = EncounterKernelTests()
        helper.setUp = lambda: None
        return helper._build_state(player_position=GridPosition(0, 0), skeleton_position=GridPosition(1, 0), mage_position=GridPosition(8, 2))

    def _instance(self, actor_id: str, condition_type: ConditionType, **kwargs) -> ConditionInstance:
        source_token = kwargs.get('source_effect_id') or kwargs.get('source_label') or condition_type.value
        source_actor_id = kwargs.get('source_actor_id') or 'test-source'
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

    def test_blinded_deafened_and_poisoned_core_effects(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        actor.condition_instances = (
            self._instance(actor.actor_id, ConditionType.BLINDED),
            self._instance(actor.actor_id, ConditionType.DEAFENED),
            self._instance(actor.actor_id, ConditionType.POISONED),
        )
        sight_check = get_ability_check_modifiers_or_auto_fail(actor, Ability.WIS, requires_sight=True)
        hearing_check = get_ability_check_modifiers_or_auto_fail(actor, Ability.WIS, requires_hearing=True)
        attack_mods = get_attack_roll_modifiers(actor, state.actors['monster-skeleton-1'], distance_ft=5, encounter_state=state)
        self.assertTrue(sight_check.auto_fail)
        self.assertTrue(hearing_check.auto_fail)
        self.assertTrue(attack_mods.disadvantage)

    def test_charmed_blocks_charmer_targeting_and_grants_social_advantage(self) -> None:
        _, state = self._build_state()
        actor = state.actors['player-1']
        charmer = state.actors['monster-mage-1']
        actor.condition_instances = (self._instance(actor.actor_id, ConditionType.CHARMED, charmer_actor_id=charmer.actor_id),)
        with self.assertRaises(EncounterValidationError):
            validate_hostile_targeting(actor, charmer, is_damaging=True, is_magical=False)
        with self.assertRaises(EncounterValidationError):
            validate_hostile_targeting(actor, charmer, is_damaging=True, is_magical=True)
        social_mods = get_ability_check_modifiers_or_auto_fail(charmer, Ability.CHA, encounter_state=state, interacting_with_actor_id=actor.actor_id, skill_name='Persuasion')
        self.assertTrue(social_mods.advantage)

    def test_exhaustion_progression_speed_penalty_and_death_at_level_six(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        for level in range(6):
            runtime.kernel._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=self._instance(actor.actor_id, ConditionType.EXHAUSTION, source_label=f'exhaustion-{level}')))
        condition_state = get_condition_state(actor)
        attack_mods = get_attack_roll_modifiers(actor, state.actors['monster-skeleton-1'], distance_ft=5, encounter_state=state)
        self.assertEqual(condition_state.exhaustion_level, 6)
        self.assertEqual(get_effective_speed(actor), 0)
        self.assertEqual(attack_mods.modifier, -12)
        self.assertEqual(actor.current_hit_points, 0)

    def test_frightened_disadvantage_and_movement_restriction(self) -> None:
        _, state = self._build_state()
        actor = state.actors['player-1']
        fear_source = state.actors['monster-skeleton-1']
        actor.condition_instances = (self._instance(actor.actor_id, ConditionType.FRIGHTENED, fear_source_actor_id=fear_source.actor_id),)
        attack_mods = get_attack_roll_modifiers(actor, fear_source, distance_ft=5, encounter_state=state)
        self.assertTrue(attack_mods.disadvantage)
        with self.assertRaises(EncounterValidationError):
            validate_frightened_movement(actor, state, GridPosition(1, 0))

    def test_grappled_source_tracking_dragging_and_attack_limit(self) -> None:
        runtime, state = self._build_state()
        target = state.actors['player-1']
        grappler = state.actors['monster-skeleton-1']
        target.condition_instances = (
            self._instance(target.actor_id, ConditionType.GRAPPLED, grappler_actor_id=grappler.actor_id, source_actor_id=grappler.actor_id),
        )
        self.assertEqual(get_effective_speed(target), 0)
        attack_mods = get_attack_roll_modifiers(target, state.actors['monster-mage-1'], distance_ft=35, encounter_state=state)
        self.assertTrue(attack_mods.disadvantage)
        state.phase = EncounterPhase.IN_PROGRESS
        state.active_actor_id = grappler.actor_id
        runtime.kernel._apply_event(state, ConditionAddedEvent(actor_id=target.actor_id, instance=self._instance(target.actor_id, ConditionType.GRAPPLED, grappler_actor_id=grappler.actor_id, source_actor_id=grappler.actor_id, source_label='grapple-apply')))
        start_target_position = target.position
        runtime.kernel._apply_event(state, MovementSpentEvent(actor_id=grappler.actor_id, from_position=grappler.position, to_position=GridPosition(2, 0), distance_ft=10, remaining_movement_ft=20))
        self.assertEqual(target.position.x - start_target_position.x, 1)

    def test_incapacitated_family_breaks_concentration_and_blocks_actions(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        actor.concentrating_effect_id = 'hold-person'
        runtime.kernel._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=self._instance(actor.actor_id, ConditionType.PARALYZED)))
        self.assertTrue(has_condition(actor, ConditionType.INCAPACITATED))
        self.assertIsNone(actor.concentrating_effect_id)
        self.assertTrue(any(isinstance(event, ConcentrationBrokenEvent) for event in state.event_log))
        state.phase = EncounterPhase.IN_PROGRESS
        state.active_actor_id = actor.actor_id
        with self.assertRaises(EncounterValidationError):
            runtime.kernel.dispatch(state, TakeCombatActionIntent(actor_id=actor.actor_id, action_type=CombatActionType.DODGE))

    def test_invisible_visibility_and_initiative_interactions(self) -> None:
        _, state = self._build_state()
        actor = state.actors['player-1']
        target = state.actors['monster-skeleton-1']
        actor.condition_instances = (self._instance(actor.actor_id, ConditionType.INVISIBLE),)
        init_mods = get_initiative_modifiers(actor)
        targeting = get_targeting_visibility_legality(target, actor, requires_target_to_be_seen=True)
        attack_mods = get_attack_roll_modifiers(actor, target, distance_ft=5, encounter_state=state)
        self.assertTrue(init_mods.advantage)
        self.assertFalse(targeting.legal)
        self.assertTrue(attack_mods.advantage)
        target.can_see_invisible = True
        seen_attack_mods = get_attack_roll_modifiers(actor, target, distance_ft=5, encounter_state=state)
        self.assertFalse(seen_attack_mods.advantage)

    def test_paralyzed_petrified_restrained_and_unconscious_effects(self) -> None:
        _, state = self._build_state()
        target = state.actors['player-1']
        target.condition_instances = (
            self._instance(target.actor_id, ConditionType.PARALYZED),
            self._instance(target.actor_id, ConditionType.RESTRAINED),
            self._instance(target.actor_id, ConditionType.PETRIFIED),
        )
        save_mods = get_saving_throw_modifiers_or_auto_fail(target, Ability.DEX)
        attack_mods = get_attack_roll_modifiers(state.actors['monster-skeleton-1'], target, distance_ft=5, encounter_state=state)
        damage = apply_damage_modifiers(target, 11, 'slashing')
        self.assertTrue(save_mods.auto_fail)
        self.assertTrue(save_mods.disadvantage)
        self.assertTrue(attack_mods.advantage)
        self.assertEqual(damage.final_damage, 5)
        with self.assertRaises(EncounterValidationError):
            add_condition(target, self._instance(target.actor_id, ConditionType.POISONED))

        target.condition_instances = (self._instance(target.actor_id, ConditionType.UNCONSCIOUS),)
        unconscious_attack_mods = get_attack_roll_modifiers(state.actors['monster-skeleton-1'], target, distance_ft=5, encounter_state=state)
        self.assertTrue(unconscious_attack_mods.critical_on_hit)

    def test_prone_distance_and_movement_cost(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        target = state.actors['monster-skeleton-1']
        actor.condition_instances = (self._instance(actor.actor_id, ConditionType.PRONE),)
        target.condition_instances = (self._instance(target.actor_id, ConditionType.PRONE),)
        adjacent_mods = get_attack_roll_modifiers(actor, target, distance_ft=5, encounter_state=state)
        far_mods = get_attack_roll_modifiers(state.actors['monster-mage-1'], target, distance_ft=35, encounter_state=state)
        self.assertTrue(adjacent_mods.disadvantage)
        self.assertTrue(far_mods.disadvantage)
        state.phase = EncounterPhase.IN_PROGRESS
        state.active_actor_id = actor.actor_id
        actor.remaining_movement_ft = 10
        state = runtime.kernel.dispatch(state, __import__('shared_types.encounter_intents', fromlist=['MoveActorIntent']).MoveActorIntent(actor_id=actor.actor_id, x=0, y=1))
        self.assertEqual(state.actors[actor.actor_id].remaining_movement_ft, 0)

    def test_non_exhaustion_condition_sources_do_not_stack_and_same_source_replaces(self) -> None:
        _, state = self._build_state()
        actor = state.actors['player-1']
        blinded_one = self._instance(actor.actor_id, ConditionType.BLINDED, source_actor_id='a', source_effect_id='spell-1')
        blinded_two_same = self._instance(actor.actor_id, ConditionType.BLINDED, source_actor_id='a', source_effect_id='spell-1', source_label='refresh')
        blinded_three_other = self._instance(actor.actor_id, ConditionType.BLINDED, source_actor_id='b', source_effect_id='spell-2')
        actor.condition_instances = add_condition(actor, blinded_one).condition_instances
        actor.condition_instances = add_condition(actor, blinded_two_same).condition_instances
        self.assertEqual(len(actor.condition_instances), 1)
        actor.condition_instances = add_condition(actor, blinded_three_other).condition_instances
        self.assertEqual(len(actor.condition_instances), 2)
        self.assertTrue(has_condition(actor, ConditionType.BLINDED))

    def test_unconscious_removal_leaves_prone(self) -> None:
        runtime, state = self._build_state()
        actor = state.actors['player-1']
        runtime.kernel._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=self._instance(actor.actor_id, ConditionType.UNCONSCIOUS)))
        runtime.kernel._apply_event(state, ConditionRemovedEvent(actor_id=actor.actor_id, condition_type=ConditionType.UNCONSCIOUS))
        self.assertFalse(has_condition(actor, ConditionType.UNCONSCIOUS))
        self.assertTrue(has_condition(actor, ConditionType.PRONE))


if __name__ == '__main__':
    unittest.main()








