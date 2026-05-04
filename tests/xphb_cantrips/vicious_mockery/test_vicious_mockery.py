from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_cantrips.support import EncounterCantripTestCase


class ViciousMockeryCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Vicious Mockery')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = session.state.actors['player-1'].position
        target.saving_throw_bonuses[Ability.WIS] = -50
        return session

    def test_failed_save_deals_damage_and_applies_disadvantage_effect(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 vicious-mockery monster-skeleton-1')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertTrue(any(effect.name == 'Vicious Mockery' and 'monster-skeleton-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_successful_save_avoids_damage_and_effect(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Vicious Mockery')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 1
        target = session.state.actors['monster-skeleton-1']
        target.position = session.state.actors['player-1'].position
        target.saving_throw_bonuses[Ability.WIS] = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 vicious-mockery monster-skeleton-1')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertFalse(any(effect.name == 'Vicious Mockery' and 'monster-skeleton-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_out_of_range_target_is_rejected(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        session.state.actors['monster-skeleton-1'].position = GridPosition(player.position.x + 20, player.position.y, player.position.z)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 vicious-mockery monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
