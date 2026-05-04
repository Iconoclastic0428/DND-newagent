from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class ColorSpraySpellTests(EncounterLevel1SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Color Spray')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        player.position = GridPosition(0, 0, 0)
        target.position = GridPosition(1, 0, 0)
        self.advance_to_actor(session, 'player-1')
        return session

    def test_failed_save_blinds_target_until_end_of_next_turn(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.CON] = -50
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 color-spray 1 0 0')
        self.assertTrue(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-skeleton-1'].condition_instances))

    def test_successful_save_avoids_blindness(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.CON] = 99
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 color-spray 1 0 0')
        self.assertFalse(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertFalse(any(effect.name == 'Color Spray' for effect in session.state.active_effects.values()))

    def test_blindness_expires_at_end_of_casters_next_turn(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.CON] = -50
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 color-spray 1 0 0')
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.assertFalse(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertFalse(any(effect.name == 'Color Spray' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
