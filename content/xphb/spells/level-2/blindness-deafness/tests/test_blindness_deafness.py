from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, inject_local_spell


ITEM_ROOT = Path(__file__).resolve().parents[1]


class BlindnessDeafnessTests(EncounterLevel2SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug='blindness-deafness', name='Blindness/Deafness')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 2, 0)
        session.state.actors['player-1'].spell_save_dc = 99
        return session

    def test_definition_metadata_matches_deterministic_support(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], 'Blindness/Deafness')
        self.assertEqual(definition['runtime_support_mode'], 'deterministic-capability')
        self.assertEqual(definition['blocker_status'], 'none')

    def test_cast_requires_condition_choice(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 blindness-deafness monster-mage-1')

    def test_blinded_mode_applies_blinded_without_concentration(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blindness-deafness monster-mage-1 --condition blinded')
        self.assertTrue(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertIsNone(session.state.actors['player-1'].concentrating_effect_id)

    def test_deafened_mode_applies_deafened(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blindness-deafness monster-mage-1 --condition deafened')
        self.assertTrue(any(instance.condition_type == ConditionType.DEAFENED for instance in session.state.actors['monster-mage-1'].condition_instances))

    def test_higher_slot_allows_two_targets_with_independent_effects(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blindness-deafness --targets monster-mage-1,monster-skeleton-1 --condition blinded --slot-level 3')
        self.assertEqual(len(session.state.active_effects), 2)
        self.assertTrue(any(effect.target_actor_ids == ('monster-mage-1',) for effect in session.state.active_effects.values()))
        self.assertTrue(any(effect.target_actor_ids == ('monster-skeleton-1',) for effect in session.state.active_effects.values()))

    def test_low_slot_rejects_too_many_targets(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 blindness-deafness --targets monster-mage-1,monster-skeleton-1 --condition blinded --slot-level 2')

    def test_one_target_can_end_while_other_remains(self) -> None:
        session = self._setup_session()
        session.state.initiative_order = ('monster-mage-1', 'monster-skeleton-1', 'player-1')
        session.state.turn_index = 2
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blindness-deafness --targets monster-mage-1,monster-skeleton-1 --condition blinded --slot-level 3')
        session.state.actors['player-1'].spell_save_dc = 0
        self.end_turn_and_resolve(session, 'player-1')
        self.end_turn_and_resolve(session, 'monster-mage-1')
        self.assertFalse(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-mage-1'].condition_instances))
        self.assertTrue(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertEqual(len(session.state.active_effects), 1)


if __name__ == '__main__':
    unittest.main()
