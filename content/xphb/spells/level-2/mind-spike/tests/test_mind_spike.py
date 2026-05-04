from __future__ import annotations

import json
from pathlib import Path
import unittest

from tests.xphb_level2_spells.support import build_local_spell_capability, load_local_spell_executor, load_local_spell_record


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'mind-spike'
SPELL_NAME = 'Mind Spike'
SPELL_SLUG = 'mind-spike'
CAST_SYNTAX = '/cast player-1 mind-spike monster-skeleton-1'
BLOCKER = 'Exact Mind Spike needs an authoritative tracking payload that can reveal location while suppressing stealth in the way the spell text specifies.'


class MindSpikeBlockedContractTests(unittest.TestCase):
    def test_local_record_matches_the_expected_spell(self) -> None:
        record = load_local_spell_record(SPELL_NAME)
        self.assertEqual(record['ENG_name'], SPELL_NAME)
        self.assertEqual(record['source'], 'XPHB')
        self.assertEqual(record['level'], 2)

    def test_executor_module_declines_to_build_capability(self) -> None:
        module = load_local_spell_executor(SPELL_SLUG)
        self.assertIsNone(module.build_capability_definition(load_local_spell_record(SPELL_NAME)))

    def test_convenience_builder_declines_to_build_capability(self) -> None:
        self.assertIsNone(build_local_spell_capability(SPELL_SLUG, name=SPELL_NAME))

    def test_definition_and_registry_remain_blocked(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['runtime_status'], 'blocked')
        self.assertEqual(definition['blocker_status'], 'needs-runtime-mechanic')
        self.assertEqual(registry['runtime_status'], 'blocked')
        self.assertEqual(registry['blocker_status'], 'needs-runtime-mechanic')

    def test_docs_record_the_blocker_contract_and_cast_syntax(self) -> None:
        readme = (ITEM_ROOT / 'README.md').read_text(encoding='utf-8')
        implementation = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        self.assertIn(CAST_SYNTAX, readme)
        self.assertIn(CAST_SYNTAX, implementation)
        self.assertIn(BLOCKER, readme)
        self.assertIn(BLOCKER, implementation)


if __name__ == '__main__':
    unittest.main()
