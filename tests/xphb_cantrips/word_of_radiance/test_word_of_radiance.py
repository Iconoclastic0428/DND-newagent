from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_cantrips.support import EncounterCantripTestCase


class WordOfRadianceCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Word of Radiance')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = session.state.actors['player-1'].position
        target.saving_throw_bonuses[Ability.CON] = -50
        return session

    def test_adjacent_creature_fails_save_and_takes_damage(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 word-of-radiance')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)

    def test_distant_creature_is_unaffected(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(player.position.x + 4, player.position.y, player.position.z)
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 word-of-radiance')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)

    def test_successful_save_avoids_damage(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Word of Radiance')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 1
        target = session.state.actors['monster-skeleton-1']
        target.position = session.state.actors['player-1'].position
        target.saving_throw_bonuses[Ability.CON] = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 word-of-radiance')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)


if __name__ == '__main__':
    unittest.main()
