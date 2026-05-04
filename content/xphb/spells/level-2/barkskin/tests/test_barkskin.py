from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'barkskin'


class BarkskinTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Barkskin'
    SPELL_SLUG = 'barkskin'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 1, 0)
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_uses_bonus_action_touch_and_ac_floor(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'bonus')
        self.assertEqual(capability.targeting.range_ft, 5)
        self.assertEqual(capability.effect.active_effect.armor_class_minimum, 17)
        self.assertFalse(capability.effect.active_effect.concentration)

    def test_cast_raises_low_armor_class_to_seventeen(self) -> None:
        session = self._setup_session()
        baseline = session.state.actors['player-1'].effective_armor_class
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 barkskin player-1')
        self.assertGreaterEqual(session.state.actors['player-1'].effective_armor_class, 17)
        self.assertGreaterEqual(session.state.actors['player-1'].effective_armor_class, baseline)

    def test_cast_does_not_lower_an_already_higher_armor_class(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].armor_class_modifier += 10
        baseline = session.state.actors['player-1'].effective_armor_class
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 barkskin player-1')
        self.assertEqual(session.state.actors['player-1'].effective_armor_class, baseline)

    def test_cast_can_protect_a_touch_range_ally(self) -> None:
        session = self._setup_session()
        ally = copy.deepcopy(session.state.actors['player-1'])
        ally.actor_id = 'player-2'
        ally.name = 'Player 2'
        ally.position = GridPosition(1, 2, 0)
        session.state.actors['player-2'] = ally
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 barkskin player-2')
        self.assertGreaterEqual(session.state.actors['player-2'].effective_armor_class, 17)

    def test_enemy_targets_are_rejected_by_the_willing_creature_model(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 barkskin monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()