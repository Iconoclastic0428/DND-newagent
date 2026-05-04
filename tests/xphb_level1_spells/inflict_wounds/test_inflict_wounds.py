from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class InflictWoundsSpellTests(EncounterLevel1SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Inflict Wounds')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-mage-1']
        player.position = GridPosition(0, 0, 0)
        target.position = GridPosition(1, 0, 0)
        self.advance_to_actor(session, 'player-1')
        return session

    def test_failed_save_deals_full_necrotic_damage(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.CON] = -50
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 inflict-wounds monster-mage-1')
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, start_hp)

    def test_successful_save_only_takes_half_damage(self) -> None:
        fail_session = self._setup_session()
        fail_session.state.actors['player-1'].spell_save_dc = 99
        fail_session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.CON] = -50
        fail_session.state, _ = fail_session.command_interface.execute(fail_session.state, '/cast player-1 inflict-wounds monster-mage-1')
        failure_damage = self.latest_damage_events(fail_session, target_id='monster-mage-1')[-1].applied_damage_total

        success_session = self._setup_session()
        success_session.state.actors['player-1'].spell_save_dc = 99
        success_session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.CON] = 99
        success_session.state, _ = success_session.command_interface.execute(success_session.state, '/cast player-1 inflict-wounds monster-mage-1')
        success_damage = self.latest_damage_events(success_session, target_id='monster-mage-1')[-1].applied_damage_total

        self.assertGreater(failure_damage, success_damage)
        self.assertGreater(success_damage, 0)

    def test_target_out_of_touch_range_is_rejected(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 inflict-wounds monster-mage-1')


if __name__ == '__main__':
    unittest.main()
