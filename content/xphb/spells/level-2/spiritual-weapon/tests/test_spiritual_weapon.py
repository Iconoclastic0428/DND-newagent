from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

from tests.xphb_level2_spells.support import load_local_spell_record


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'spiritual-weapon'
SPELL_NAME = 'Spiritual Weapon'
SOURCE_ID = 'XPHB:spell:spiritual-weapon'
IMPLEMENTATION_FAMILY = 'bonus-action-force-weapon'
PLANNED_CAST_SYNTAX = '/cast player-1 spiritual-weapon 5 2 --target monster-skeleton-1'
BLOCKER_PHRASE = 'floating weapon command primitive'


def load_executor_module():
    spec = importlib.util.spec_from_file_location('spiritual_weapon_executor', ITEM_ROOT / 'executor.py')
    if spec is None or spec.loader is None:
        raise AssertionError('Could not load Spiritual Weapon executor module.')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SpiritualWeaponBlockerContractTests(unittest.TestCase):
    def test_definition_records_blocked_runtime_and_precise_blocker(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['source_id'], SOURCE_ID)
        self.assertEqual(definition['runtime_status'], 'blocked')
        self.assertEqual(definition['implementation_family'], IMPLEMENTATION_FAMILY)
        self.assertEqual(definition['cast_syntax'], PLANNED_CAST_SYNTAX)
        self.assertIn(BLOCKER_PHRASE, definition['notes'])

    def test_registry_points_to_the_local_blocker_test_module(self) -> None:
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(registry['runtime_status'], 'blocked')
        self.assertEqual(registry['executor'], 'executor.py')
        self.assertEqual(
            registry['test_path'],
            'content/xphb/spells/level-2/spiritual-weapon/tests/test_spiritual_weapon.py',
        )

    def test_executor_returns_none_for_the_exact_local_spell(self) -> None:
        module = load_executor_module()
        raw_spell = load_local_spell_record(SPELL_NAME)
        self.assertIsNone(module.build_capability_definition(raw_spell))
        self.assertIn(BLOCKER_PHRASE, module.BLOCKER_REASON)

    def test_executor_ignores_non_matching_spell_records(self) -> None:
        module = load_executor_module()
        other_spell = load_local_spell_record('Heat Metal')
        self.assertIsNone(module.build_capability_definition(other_spell))

    def test_readme_lists_exact_behavior_and_missing_primitive(self) -> None:
        text = (ITEM_ROOT / 'README.md').read_text(encoding='utf-8')
        for snippet in (
            'Bonus action, 60 feet, concentration up to 1 minute.',
            'floating spectral weapon at a point you choose in range',
            'immediately make a melee spell attack',
            '1d8 + your spellcasting ability modifier force damage',
            'move the weapon up to 20 feet',
            BLOCKER_PHRASE,
        ):
            self.assertIn(snippet, text)

    def test_implementation_doc_keeps_the_blocker_contract_explicit(self) -> None:
        text = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        for snippet in (
            'Runtime status stays `blocked`.',
            '`build_capability_definition(...)` intentionally returns `None`',
            BLOCKER_PHRASE,
            'no non-initiative floating-weapon command model',
            'make the immediate melee spell attack on cast',
        ):
            self.assertIn(snippet, text)

    def test_local_xphb_record_matches_the_blocked_summary(self) -> None:
        raw_spell = load_local_spell_record(SPELL_NAME)
        self.assertEqual(raw_spell['time'][0]['unit'], '附赠动作')
        self.assertEqual(raw_spell['range']['distance']['amount'], 60)
        self.assertTrue(raw_spell['duration'][0]['concentration'])
        self.assertEqual(raw_spell['duration'][0]['duration']['amount'], 1)
        self.assertIn('1d8', raw_spell['entries'][0])
        self.assertIn('20 尺', raw_spell['entries'][1])
        self.assertIn('1d8', raw_spell['entriesHigherLevel'][0]['entries'][0])


if __name__ == '__main__':
    unittest.main()
