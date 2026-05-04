from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase



class DissonantWhispersLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Dissonant Whispers'
    SPELL_SLUG = 'dissonant-whispers'
    COMMAND = '/cast player-1 dissonant-whispers monster-skeleton-1'

    def _setup_session(self, *, target_save_bonus: int = -50, caster_dc: int = 99, reaction_available: bool = True, target_position: GridPosition = GridPosition(1, 0, 0)):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = target_position
        session.state.actors['monster-mage-1'].position = GridPosition(10, 0, 0)
        session.state.actors['player-1'].spell_save_dc = caster_dc
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = target_save_bonus
        session.state.actors['monster-skeleton-1'].reaction_available = reaction_available
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_the_single_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')
        self.assertEqual(tuple(intent.parameters), ())

    def test_failed_save_deals_full_psychic_damage_and_forces_a_reaction_move_away(self) -> None:
        session = self._setup_session(reaction_available=True)
        start_position = session.state.actors['monster-skeleton-1'].position
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertNotEqual(session.state.actors['monster-skeleton-1'].position, start_position)
        self.assertFalse(session.state.actors['monster-skeleton-1'].reaction_available)
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) and event.damage_type == 'psychic' for event in session.state.event_log))

    def test_successful_save_takes_half_damage_and_does_not_move(self) -> None:
        fail_session = self._setup_session(target_save_bonus=-50)
        success_session = self._setup_session(target_save_bonus=99, caster_dc=1)
        fail_start_hp = fail_session.state.actors['monster-skeleton-1'].current_hit_points
        success_start_hp = success_session.state.actors['monster-skeleton-1'].current_hit_points
        fail_session.state, _ = fail_session.command_interface.execute(fail_session.state, self.COMMAND)
        success_session.state, _ = success_session.command_interface.execute(success_session.state, self.COMMAND)
        self.assertGreater(fail_start_hp - fail_session.state.actors['monster-skeleton-1'].current_hit_points, success_start_hp - success_session.state.actors['monster-skeleton-1'].current_hit_points)
        self.assertEqual(success_session.state.actors['monster-skeleton-1'].position, GridPosition(1, 0, 0))

    def test_target_without_a_reaction_still_takes_damage_but_does_not_move(self) -> None:
        session = self._setup_session(reaction_available=True)
        session.state.actors['monster-skeleton-1'].reaction_available = False
        start_position = session.state.actors['monster-skeleton-1'].position
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertEqual(session.state.actors['monster-skeleton-1'].position, start_position)

    def test_same_seed_and_setup_produce_the_same_result(self) -> None:
        session_one = self._setup_session()
        session_two = self._setup_session()
        session_one.state, _ = session_one.command_interface.execute(session_one.state, self.COMMAND)
        session_two.state, _ = session_two.command_interface.execute(session_two.state, self.COMMAND)
        self.assertEqual(session_one.state.actors['monster-skeleton-1'].current_hit_points, session_two.state.actors['monster-skeleton-1'].current_hit_points)
        self.assertEqual(session_one.state.actors['monster-skeleton-1'].position, session_two.state.actors['monster-skeleton-1'].position)


if __name__ == '__main__':
    unittest.main()

