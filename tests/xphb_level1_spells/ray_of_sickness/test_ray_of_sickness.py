from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class RayOfSicknessSpellTests(EncounterLevel1SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Ray of Sickness')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-mage-1']
        player.position = GridPosition(0, 0, 0)
        target.position = GridPosition(3, 0, 0)
        self.advance_to_actor(session, 'player-1')
        return session

    def test_hit_deals_damage_and_applies_poisoned(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-mage-1'].armor_class = 0
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 ray-of-sickness monster-mage-1')
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, start_hp)
        self.assertTrue(any(instance.condition_type == ConditionType.POISONED for instance in session.state.actors['monster-mage-1'].condition_instances))

    def test_miss_applies_no_damage_or_poison(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = -50
        session.state.actors['monster-mage-1'].armor_class = 99
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 ray-of-sickness monster-mage-1')
        self.assertEqual(session.state.actors['monster-mage-1'].current_hit_points, start_hp)
        self.assertFalse(any(instance.condition_type == ConditionType.POISONED for instance in session.state.actors['monster-mage-1'].condition_instances))

    def test_poisoned_condition_expires_at_end_of_casters_next_turn(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-mage-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 ray-of-sickness monster-mage-1')
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(instance.condition_type == ConditionType.POISONED for instance in session.state.actors['monster-mage-1'].condition_instances))
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.assertFalse(any(instance.condition_type == ConditionType.POISONED for instance in session.state.actors['monster-mage-1'].condition_instances))


if __name__ == '__main__':
    unittest.main()
