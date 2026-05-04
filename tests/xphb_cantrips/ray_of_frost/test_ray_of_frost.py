from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from shared_types.encounter_models import GridPosition
from tests.xphb_cantrips.support import EncounterCantripTestCase


class RayOfFrostCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Ray of Frost')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_attack_bonus = 99
        return session

    def test_hit_deals_cold_damage_and_slows_target(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].armor_class = 0
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 ray-of-frost monster-skeleton-1')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Ray of Frost')
        self.assertEqual(effect.definition.speed_penalty_ft, 10)

    def test_miss_does_not_apply_the_speed_penalty(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = -50
        session.state.actors['monster-skeleton-1'].armor_class = 99
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 ray-of-frost monster-skeleton-1')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertFalse(any(effect.name == 'Ray of Frost' for effect in session.state.active_effects.values()))

    def test_out_of_range_target_is_rejected(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        session.state.actors['monster-skeleton-1'].position = GridPosition(player.position.x + 100, player.position.y, player.position.z)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 ray-of-frost monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
