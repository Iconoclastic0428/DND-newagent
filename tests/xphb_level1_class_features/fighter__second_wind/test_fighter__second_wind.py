from __future__ import annotations

import unittest

from shared_types.encounter_events import HealingAppliedEvent
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class FighterSecondWindFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        session = self.build_session(self.complete_record('fighter'))
        self.advance_to_actor(session, 'player-1')
        return session

    def test_feature_name_and_capability_compile(self) -> None:
        record = self.complete_record('fighter')
        actor = self.compile_actor(record)
        self.assertIn('Second Wind', record.class_feature_names)
        self.assertIn('second-wind', actor.capabilities)

    def test_second_wind_heals_and_consumes_the_bonus_action(self) -> None:
        session = self._session()
        session.state.actors['player-1'].current_hit_points = 3
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 second-wind')
        self.assertGreater(session.state.actors['player-1'].current_hit_points, 3)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(self.events_since(session, start_index, HealingAppliedEvent))

    def test_second_wind_spends_a_use(self) -> None:
        session = self._session()
        uses_before = session.state.actors['player-1'].capabilities['second-wind'].remaining_uses
        session.state.actors['player-1'].current_hit_points = 3
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 second-wind')
        self.assertEqual(session.state.actors['player-1'].capabilities['second-wind'].remaining_uses, uses_before - 1)


if __name__ == '__main__':
    unittest.main()
