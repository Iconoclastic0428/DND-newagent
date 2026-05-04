from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, inject_local_spell


ITEM_ROOT = Path(__file__).resolve().parents[1]


class InvisibilityTests(EncounterLevel2SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug='invisibility', name='Invisibility')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 2, 0)
        return session

    def test_definition_metadata_documents_spell_break_conditions(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], 'Invisibility')
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertIn('casts a spell', definition['notes'])

    def test_single_target_cast_applies_invisible(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 invisibility player-1')
        self.assertTrue(any(instance.condition_type == ConditionType.INVISIBLE for instance in session.state.actors['player-1'].condition_instances))
        self.assertIsNotNone(session.state.actors['player-1'].concentrating_effect_id)

    def test_casting_any_spell_ends_single_target_invisibility(self) -> None:
        session = self._setup_session()
        self.grant_spell(session, 'Misty Step')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 invisibility player-1')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 misty-step 4 1')
        self.assertFalse(any(instance.condition_type == ConditionType.INVISIBLE for instance in session.state.actors['player-1'].condition_instances))
        self.assertFalse(session.state.active_effects)

    def test_higher_slot_creates_anchor_and_individual_target_effects(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 invisibility --targets player-1,monster-mage-1 --slot-level 3')
        self.assertEqual(len(session.state.active_effects), 3)
        self.assertTrue(any(effect.name == 'Invisibility (anchor)' for effect in session.state.active_effects.values()))
        self.assertTrue(any(effect.target_actor_ids == ('player-1',) for effect in session.state.active_effects.values()))
        self.assertTrue(any(effect.target_actor_ids == ('monster-mage-1',) for effect in session.state.active_effects.values()))

    def test_low_slot_rejects_multiple_targets(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 invisibility --targets player-1,monster-mage-1 --slot-level 2')

    def test_attacking_ends_only_the_attacking_targets_effect(self) -> None:
        session = self._setup_session()
        session.state.initiative_order = ('monster-mage-1', 'monster-skeleton-1', 'player-1')
        session.state.turn_index = 2
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 invisibility --targets monster-mage-1,monster-skeleton-1 --slot-level 3')
        self.end_turn_and_resolve(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/attack monster-mage-1 unarmed-strike player-1')
        self.assertFalse(any(instance.condition_type == ConditionType.INVISIBLE for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertTrue(any(instance.condition_type == ConditionType.INVISIBLE for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertEqual(len(session.state.active_effects), 2)

    def test_one_target_can_cast_a_spell_and_break_only_their_effect(self) -> None:
        session = self._setup_session()
        self.grant_spell(session, 'Misty Step')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 invisibility --targets player-1,monster-mage-1 --slot-level 3')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 misty-step 4 1')
        self.assertFalse(any(instance.condition_type == ConditionType.INVISIBLE for instance in session.state.actors['player-1'].condition_instances))
        self.assertTrue(any(instance.condition_type == ConditionType.INVISIBLE for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertEqual(len(session.state.active_effects), 2)


if __name__ == '__main__':
    unittest.main()
