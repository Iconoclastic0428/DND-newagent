from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from shared_types.encounter_models import GridPosition
from tests.xphb_cantrips.support import EncounterCantripTestCase


class SacredFlameCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Sacred Flame')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 99
        return session

    def test_failed_save_deals_radiant_damage(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].position = session.state.actors['player-1'].position
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 sacred-flame monster-skeleton-1')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)

    def test_successful_save_negates_the_damage(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Sacred Flame')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[__import__('shared_types.models', fromlist=['Ability']).Ability.DEX] = 99
        session.state.actors['monster-skeleton-1'].position = session.state.actors['player-1'].position
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 sacred-flame monster-skeleton-1')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)

    def test_out_of_range_target_is_rejected(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        session.state.actors['monster-skeleton-1'].position = GridPosition(player.position.x + 100, player.position.y, player.position.z)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 sacred-flame monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
