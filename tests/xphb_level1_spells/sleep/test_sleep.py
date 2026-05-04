from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class SleepLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Sleep'
    SPELL_SLUG = 'sleep'
    COMMAND = '/cast player-1 sleep 1 0'

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

    def _effect_names(self, session, actor_id: str = 'monster-skeleton-1'):
        return {effect.name for effect in session.state.active_effects.values() if actor_id in effect.target_actor_ids}

    def test_command_shape_uses_a_point_target(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual((intent.x, intent.y), (1, 0))

    def test_failed_initial_save_applies_the_drowsy_effect(self) -> None:
        session = self._setup_session()
        self.assertIn('Sleep (Drowsy)', self._effect_names(session))

    def test_successful_initial_save_avoids_all_sleep_effects(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['player-1'].spell_save_dc = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = 99
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertNotIn('Sleep (Drowsy)', self._effect_names(session))
        self.assertNotIn('Sleep', self._effect_names(session))

    def test_failed_followup_save_becomes_unconscious(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=-50)
        self.advance_existing_turn(session, 'monster-skeleton-1')
        self.end_turn_and_resolve(session, 'monster-skeleton-1')
        self.assertIn('Sleep', self._effect_names(session))

    def test_successful_followup_save_ends_the_drowsy_effect(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=99)
        self.advance_existing_turn(session, 'monster-skeleton-1')
        self.end_turn_and_resolve(session, 'monster-skeleton-1')
        self.assertNotIn('Sleep (Drowsy)', self._effect_names(session))
        self.assertNotIn('Sleep', self._effect_names(session))

    def test_damage_breaks_sleep_and_drowsy_effects(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=-50)
        target = session.state.actors['monster-skeleton-1']
        event = DamageAppliedEvent(source_actor_id='player-1', target_id='monster-skeleton-1', damage_total=1, applied_damage_total=1, target_hit_points_after=target.current_hit_points - 1, target_temp_hit_points_after=target.temp_hit_points, damage_type='bludgeoning')
        session.command_interface.kernel._apply_event(session.state, event)
        self.assertNotIn('Sleep (Drowsy)', self._effect_names(session))
        self.assertNotIn('Sleep', self._effect_names(session))

    def test_help_action_wakes_the_target_within_five_feet(self) -> None:
        session = self._setup_session(initial_save_bonus=-50, followup_save_bonus=-50)
        self.advance_existing_turn(session, 'monster-skeleton-1')
        self.end_turn_and_resolve(session, 'monster-skeleton-1')
        self.advance_existing_turn(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/help player-1 monster-skeleton-1')
        self.assertNotIn('Sleep', self._effect_names(session))


if __name__ == '__main__':
    unittest.main()
