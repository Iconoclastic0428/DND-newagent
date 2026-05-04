from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, inject_local_spell


ITEM_ROOT = Path(__file__).resolve().parents[1]


class HoldPersonTests(EncounterLevel2SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug='hold-person', name='Hold Person')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 2, 0)
        session.state.actors['player-1'].spell_save_dc = 99
        return session

    def test_definition_metadata_is_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], 'Hold Person')
        self.assertEqual(definition['runtime_support_mode'], 'deterministic-capability')
        self.assertEqual(definition['blocker_status'], 'none')

    def test_failed_save_applies_paralyzed(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 hold-person monster-mage-1')
        self.assertTrue(any(instance.condition_type == ConditionType.PARALYZED for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertIsNotNone(session.state.actors['player-1'].concentrating_effect_id)

    def test_repeat_save_ends_single_target_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 hold-person monster-mage-1')
        session.state.actors['player-1'].spell_save_dc = 0
        self.advance_existing_turn(session, 'monster-mage-1')
        self.end_turn_and_resolve(session, 'monster-mage-1')
        self.assertFalse(any(instance.condition_type == ConditionType.PARALYZED for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertFalse(session.state.active_effects)

    def test_non_humanoid_targets_are_rejected(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 hold-person monster-skeleton-1')

    def test_low_slot_rejects_too_many_humanoids(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'humanoid'
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 hold-person --targets monster-mage-1,monster-skeleton-1 --slot-level 2')

    def test_higher_slot_creates_anchor_and_individual_target_effects(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'humanoid'
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 hold-person --targets monster-mage-1,monster-skeleton-1 --slot-level 3')
        self.assertEqual(len(session.state.active_effects), 3)
        self.assertTrue(any(effect.name == 'Hold Person (anchor)' for effect in session.state.active_effects.values()))
        self.assertTrue(any(effect.target_actor_ids == ('monster-mage-1',) for effect in session.state.active_effects.values()))
        self.assertTrue(any(effect.target_actor_ids == ('monster-skeleton-1',) for effect in session.state.active_effects.values()))

    def test_one_target_can_end_while_other_remains_paralyzed(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'humanoid'
        session.state.initiative_order = ('monster-mage-1', 'monster-skeleton-1', 'player-1')
        session.state.turn_index = 2
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 hold-person --targets monster-mage-1,monster-skeleton-1 --slot-level 3')
        session.state.actors['player-1'].spell_save_dc = 0
        self.end_turn_and_resolve(session, 'player-1')
        self.end_turn_and_resolve(session, 'monster-mage-1')
        self.assertFalse(any(instance.condition_type == ConditionType.PARALYZED for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertTrue(any(instance.condition_type == ConditionType.PARALYZED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertEqual(len(session.state.active_effects), 2)


if __name__ == '__main__':
    unittest.main()
