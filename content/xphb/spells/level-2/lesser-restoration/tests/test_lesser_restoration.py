from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'lesser-restoration'


class LesserRestorationTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Lesser Restoration'
    SPELL_SLUG = 'lesser-restoration'

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

    def test_capability_uses_bonus_action_touch(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'bonus')
        self.assertEqual(capability.targeting.range_ft, 5)
        self.assertIn(ConditionType.POISONED, capability.effect.allowed_condition_types)

    def test_cast_removes_blinded(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].condition_instances = (ConditionInstance(instance_id='test', condition_type=ConditionType.BLINDED, source_label='test'),)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 lesser-restoration player-1 --condition blinded')
        self.assertFalse(any(instance.condition_type == ConditionType.BLINDED for instance in session.state.actors['player-1'].condition_instances))

    def test_cast_removes_poisoned_by_default_when_it_is_the_only_condition(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].condition_instances = (ConditionInstance(instance_id='test', condition_type=ConditionType.POISONED, source_label='test'),)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 lesser-restoration player-1')
        self.assertFalse(any(instance.condition_type == ConditionType.POISONED for instance in session.state.actors['player-1'].condition_instances))

    def test_cast_can_target_another_creature(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].condition_instances = (ConditionInstance(instance_id='test', condition_type=ConditionType.DEAFENED, source_label='test'),)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 lesser-restoration monster-skeleton-1 --condition deafened')
        self.assertFalse(any(instance.condition_type == ConditionType.DEAFENED for instance in session.state.actors['monster-skeleton-1'].condition_instances))

    def test_invalid_condition_parameter_is_rejected(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 lesser-restoration player-1 --condition restrained')


if __name__ == '__main__':
    unittest.main()