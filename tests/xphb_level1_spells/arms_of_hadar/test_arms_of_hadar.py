from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class ArmsOfHadarSpellTests(EncounterLevel1SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Arms of Hadar', actor_id='monster-mage-1')
        mage = session.state.actors['monster-mage-1']
        player = session.state.actors['player-1']
        skeleton = session.state.actors['monster-skeleton-1']
        mage.position = GridPosition(0, 0, 0)
        player.position = GridPosition(1, 0, 0)
        skeleton.position = GridPosition(5, 0, 0)
        mage.saving_throw_bonuses[Ability.STR] = 99
        self.advance_to_actor(session, 'monster-mage-1')
        return session

    def test_failed_save_deals_full_damage_and_blocks_reactions(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].spell_save_dc = 99
        session.state.actors['player-1'].saving_throw_bonuses[Ability.STR] = -50
        start_hp = session.state.actors['player-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast monster-mage-1 arms-of-hadar')
        self.assertLess(session.state.actors['player-1'].current_hit_points, start_hp)
        self.assertTrue(session.state.actors['player-1'].cannot_take_reactions)

    def test_successful_save_only_takes_half_damage(self) -> None:
        fail_session = self._setup_session()
        fail_session.state.actors['monster-mage-1'].spell_save_dc = 99
        fail_session.state.actors['player-1'].saving_throw_bonuses[Ability.STR] = -50
        fail_session.state, _ = fail_session.command_interface.execute(fail_session.state, '/cast monster-mage-1 arms-of-hadar')
        failure_damage = self.latest_damage_events(fail_session, target_id='player-1')[-1].applied_damage_total

        success_session = self._setup_session()
        success_session.state.actors['monster-mage-1'].spell_save_dc = 99
        success_session.state.actors['player-1'].saving_throw_bonuses[Ability.STR] = 99
        success_session.state, _ = success_session.command_interface.execute(success_session.state, '/cast monster-mage-1 arms-of-hadar')
        success_damage = self.latest_damage_events(success_session, target_id='player-1')[-1].applied_damage_total

        self.assertGreater(failure_damage, success_damage)
        self.assertGreater(success_damage, 0)
        self.assertFalse(success_session.state.actors['player-1'].cannot_take_reactions)

    def test_creature_outside_the_emanation_is_unaffected(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].spell_save_dc = 99
        session.state.actors['player-1'].position = GridPosition(3, 0, 0)
        start_hp = session.state.actors['player-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast monster-mage-1 arms-of-hadar')
        self.assertEqual(session.state.actors['player-1'].current_hit_points, start_hp)


if __name__ == '__main__':
    unittest.main()
