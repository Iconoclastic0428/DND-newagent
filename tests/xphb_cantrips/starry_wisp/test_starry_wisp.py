from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from shared_types.encounter_models import GridPosition
from tests.xphb_cantrips.support import EncounterCantripTestCase


class StarryWispCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Starry Wisp')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-skeleton-1'].position = session.state.actors['player-1'].position
        return session

    def test_hit_deals_radiant_damage_and_suppresses_invisible_benefits(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].armor_class = 0
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 starry-wisp monster-skeleton-1')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertTrue(session.command_interface.kernel._suppresses_invisible_benefits(session.state, 'monster-skeleton-1'))

    def test_miss_does_not_suppress_invisible_benefits(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = -50
        session.state.actors['monster-skeleton-1'].armor_class = 99
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 starry-wisp monster-skeleton-1')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertFalse(session.command_interface.kernel._suppresses_invisible_benefits(session.state, 'monster-skeleton-1'))

    def test_out_of_range_target_is_rejected(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        session.state.actors['monster-skeleton-1'].position = GridPosition(player.position.x + 100, player.position.y, player.position.z)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 starry-wisp monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
