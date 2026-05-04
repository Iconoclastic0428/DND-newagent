from __future__ import annotations

import json
from pathlib import Path
import unittest

from tests.xphb_level2_spells.support import build_local_spell_capability


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'ray-of-enfeeblement'


class RayOfEnfeeblementBlockedTests(unittest.TestCase):
    def test_executor_declines_to_build_a_capability(self) -> None:
        capability = build_local_spell_capability('ray-of-enfeeblement', name='Ray of Enfeeblement')
        self.assertIsNone(capability)

    def test_definition_marks_the_spell_blocked(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['runtime_status'], 'blocked')
        self.assertEqual(definition['blocker_status'], 'needs-runtime-mechanic')

    def test_registry_marks_the_spell_blocked(self) -> None:
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(registry['runtime_status'], 'blocked')
        self.assertEqual(registry['test_path'], 'tests/test_ray_of_enfeeblement.py')

    def test_readme_explains_the_local_text_summary(self) -> None:
        readme = (ITEM_ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('Status: blocked', readme)
        self.assertIn('next attack roll', readme)
        self.assertIn('Strength-based D20 tests', readme)

    def test_implementation_doc_names_the_missing_shared_primitive(self) -> None:
        implementation = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        self.assertIn('ability-keyed D20-test disadvantage', implementation)
        self.assertIn('damage-roll penalty modifier', implementation)

    def test_implementation_doc_records_the_per_damage_component_requirement(self) -> None:
        implementation = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        self.assertIn('each rolled damage component', implementation)
        self.assertIn('fixed damage that is not rolled', implementation)


if __name__ == '__main__':
    unittest.main()
