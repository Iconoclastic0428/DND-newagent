from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class TashasHideousLaughterLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = "Tasha's Hideous Laughter"
    SPELL_SLUG = 'tasha-s-hideous-laughter'
    COMMAND = "/cast player-1 tasha-s-hideous-laughter monster-skeleton-1"

    def _setup_session(self, *, initial_save_bonus: int = -50, followup_save_bonus: int = -50):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = initial_save_bonus
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = followup_save_bonus
        return session

    def _condition_types(self, session):
        return {instance.condition_type for instance in session.state.actors['monster-skeleton-1'].condition_instances}

    def test_command_shape_uses_single_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_failed_initial_save_applies_prone_and_incapacitated(self) -> None:
        session = self._setup_session(initial_save_bonus=-50)
        self.assertIn(ConditionType.PRONE, self._condition_types(session))
        self.assertIn(ConditionType.INCAPACITATED, self._condition_types(session))
        self.assertTrue(any(effect.name == self.SPELL_NAME for effect in session.state.active_effects.values()))

    def test_successful_initial_save_avoids_the_effect(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['player-1'].spell_save_dc = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = 99
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertFalse(any(effect.name == self.SPELL_NAME for effect in session.state.active_effects.values()))

    def test_end_of_turn_successful_save_ends_the_effect(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=99)
        self.advance_existing_turn(session, 'monster-skeleton-1')
        self.end_turn_and_resolve(session, 'monster-skeleton-1')
        self.assertFalse(any(effect.name == self.SPELL_NAME for effect in session.state.active_effects.values()))

    def test_damage_triggers_an_advantage_save_that_can_end_the_effect(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=-50)
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = 99
        target = session.state.actors['monster-skeleton-1']
        event = DamageAppliedEvent(source_actor_id='player-1', target_id='monster-skeleton-1', damage_total=1, applied_damage_total=1, target_hit_points_after=target.current_hit_points - 1, target_temp_hit_points_after=target.temp_hit_points, damage_type='bludgeoning')
        session.command_interface.kernel._apply_event(session.state, event)
        self.assertFalse(any(effect.name == self.SPELL_NAME for effect in session.state.active_effects.values()))

    def test_failed_damage_save_keeps_the_effect_active(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=-50)
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = -50
        target = session.state.actors['monster-skeleton-1']
        event = DamageAppliedEvent(source_actor_id='player-1', target_id='monster-skeleton-1', damage_total=1, applied_damage_total=1, target_hit_points_after=target.current_hit_points - 1, target_temp_hit_points_after=target.temp_hit_points, damage_type='bludgeoning')
        session.command_interface.kernel._apply_event(session.state, event)
        self.assertTrue(any(effect.name == self.SPELL_NAME for effect in session.state.active_effects.values()))

    def test_same_seed_and_setup_produce_the_same_initial_result(self) -> None:
        session_one = self._setup_session(initial_save_bonus=-50)
        session_two = self._setup_session(initial_save_bonus=-50)
        self.assertEqual(self._condition_types(session_one), self._condition_types(session_two))


if __name__ == '__main__':
    unittest.main()
