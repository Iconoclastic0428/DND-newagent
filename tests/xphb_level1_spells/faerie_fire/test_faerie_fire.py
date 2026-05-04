from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class FaerieFireSpellTests(EncounterLevel1SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Faerie Fire')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        player.position = GridPosition(0, 0, 0)
        target.position = GridPosition(3, 0, 0)
        self.advance_to_actor(session, 'player-1')
        return session

    def test_failed_save_applies_visible_outline_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -50
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 faerie-fire 3 0 0')
        self.assertTrue(any(effect.name == 'Faerie Fire' and 'monster-skeleton-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))
        self.assertTrue(session.command_interface.kernel._suppresses_invisible_benefits(session.state, 'monster-skeleton-1'))

    def test_successful_save_avoids_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = 99
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 faerie-fire 3 0 0')
        self.assertFalse(any(effect.name == 'Faerie Fire' and 'monster-skeleton-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_attacks_against_affected_target_gain_advantage(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -50
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 faerie-fire 3 0 0')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        modifiers = session.command_interface.kernel._attack_modifier_state(session.state, player, target, distance_ft=15, long_range_disadvantage=False)
        self.assertTrue(modifiers['advantage'])


if __name__ == '__main__':
    unittest.main()
