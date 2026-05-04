from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class BurningHandsLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Burning Hands'
    SPELL_SLUG = 'burning-hands'
    COMMAND = '/cast player-1 burning-hands 3 0'

    def _setup_session(
        self,
        *,
        skeleton_save_bonus: int = -50,
        mage_save_bonus: int = 99,
        skeleton_position: GridPosition = GridPosition(3, 0, 0),
        mage_position: GridPosition = GridPosition(0, 4, 0),
        caster_dc: int = 99,
    ):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = skeleton_position
        session.state.actors['monster-mage-1'].position = mage_position
        session.state.actors['player-1'].spell_save_dc = caster_dc
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = skeleton_save_bonus
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.DEX] = mage_save_bonus
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _damage_events(self, session):
        return [event for event in session.state.event_log if isinstance(event, DamageAppliedEvent)]

    def test_command_shape_uses_a_point_target_for_the_cone(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (3, 0))

    def test_failed_save_applies_fire_damage_to_creatures_in_the_cone(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        start_hp_outside = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertEqual(session.state.actors['monster-mage-1'].current_hit_points, start_hp_outside)
        damage_targets = {event.target_id for event in self._damage_events(session)}
        self.assertIn('monster-skeleton-1', damage_targets)
        self.assertNotIn('monster-mage-1', damage_targets)

    def test_successful_save_halves_the_fire_damage_taken(self) -> None:
        fail_session = self._setup_session(skeleton_save_bonus=-50)
        success_session = self._setup_session(skeleton_save_bonus=99)
        fail_start_hp = fail_session.state.actors['monster-skeleton-1'].current_hit_points
        success_start_hp = success_session.state.actors['monster-skeleton-1'].current_hit_points
        fail_session.state, _ = fail_session.command_interface.execute(fail_session.state, self.COMMAND)
        success_session.state, _ = success_session.command_interface.execute(success_session.state, self.COMMAND)
        self.assertGreater(fail_start_hp - fail_session.state.actors['monster-skeleton-1'].current_hit_points, success_start_hp - success_session.state.actors['monster-skeleton-1'].current_hit_points)

    def test_multiple_targets_in_the_cone_are_resolved_independently(self) -> None:
        session = self._setup_session(mage_position=GridPosition(2, 1, 0), mage_save_bonus=99)
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, session.state.actors['monster-skeleton-1'].max_hit_points)
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, session.state.actors['monster-mage-1'].max_hit_points)
        self.assertEqual(len([event for event in self._damage_events(session) if event.damage_type == 'fire']), 2)

    def test_creatures_outside_the_cone_are_untouched(self) -> None:
        session = self._setup_session(mage_position=GridPosition(0, 4, 0), mage_save_bonus=-50)
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['monster-mage-1'].current_hit_points, start_hp)

    def test_same_seed_and_setup_produce_the_same_damage_result(self) -> None:
        session_one = self._setup_session()
        session_two = self._setup_session()
        session_one.state, _ = session_one.command_interface.execute(session_one.state, self.COMMAND)
        session_two.state, _ = session_two.command_interface.execute(session_two.state, self.COMMAND)
        self.assertEqual(session_one.state.actors['monster-skeleton-1'].current_hit_points, session_two.state.actors['monster-skeleton-1'].current_hit_points)
        self.assertEqual(session_one.state.actors['monster-mage-1'].current_hit_points, session_two.state.actors['monster-mage-1'].current_hit_points)


if __name__ == '__main__':
    unittest.main()
