
from __future__ import annotations

import unittest

from shared_types.encounter_events import TemporaryHitPointsAppliedEvent
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class FalseLifeLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'False Life'
    SPELL_SLUG = 'false-life'
    COMMAND = '/cast player-1 false-life'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_requires_no_target(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertIsNone(intent.target_id)

    def test_cast_applies_temporary_hit_points(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertTrue(any(isinstance(event, TemporaryHitPointsAppliedEvent) for event in session.state.event_log))
        self.assertGreater(session.state.actors['player-1'].temp_hit_points, 0)

    def test_cast_does_not_change_current_hit_points(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['player-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['player-1'].current_hit_points, start_hp)

    def test_cast_keeps_existing_higher_temporary_hit_points(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].temp_hit_points = 20
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['player-1'].temp_hit_points, 20)

    def test_granted_temporary_hit_points_stay_within_the_2d4_plus_4_bounds(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertGreaterEqual(session.state.actors['player-1'].temp_hit_points, 6)
        self.assertLessEqual(session.state.actors['player-1'].temp_hit_points, 12)


if __name__ == '__main__':
    unittest.main()
