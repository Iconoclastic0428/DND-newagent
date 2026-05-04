from __future__ import annotations

import unittest

from rules_engine.encounter_math import grid_distance_ft
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase, find_non_one_counter


class ThornWhipCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Thorn Whip')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_attack_bonus = 99
        return session

    def test_hit_pulls_target_ten_feet_closer(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(player.position.x + 4, player.position.y, player.position.z)
        target.armor_class = 0
        session.state.random_counter = find_non_one_counter(session)
        start_distance = grid_distance_ft(target.position, player.position)
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 thorn-whip monster-skeleton-1')
        end_distance = grid_distance_ft(session.state.actors['monster-skeleton-1'].position, player.position)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertEqual(end_distance, start_distance - 10)

    def test_miss_does_not_pull_target(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(player.position.x + 4, player.position.y, player.position.z)
        target.armor_class = 99
        session.state.actors['player-1'].spell_attack_bonus = -50
        session.state.random_counter = find_non_one_counter(session)
        start_position = target.position
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 thorn-whip monster-skeleton-1')
        self.assertEqual(session.state.actors['monster-skeleton-1'].position, start_position)
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)

    def test_out_of_range_target_is_rejected(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        session.state.actors['monster-skeleton-1'].position = GridPosition(player.position.x + 20, player.position.y, player.position.z)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 thorn-whip monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
