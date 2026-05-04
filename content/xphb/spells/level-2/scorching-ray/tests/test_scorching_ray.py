from __future__ import annotations

import json
from pathlib import Path
import unittest

from tests.xphb_level2_spells.support import build_local_spell_capability


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'scorching-ray'


class ScorchingRayBlockedTests(unittest.TestCase):
    def test_executor_declines_to_build_a_capability(self) -> None:
        capability = build_local_spell_capability('scorching-ray', name='Scorching Ray')
        self.assertIsNone(capability)

    def test_definition_marks_the_spell_blocked(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['runtime_status'], 'blocked')
        self.assertEqual(definition['blocker_status'], 'needs-runtime-mechanic')

    def test_registry_marks_the_spell_blocked(self) -> None:
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(registry['runtime_status'], 'blocked')
        self.assertEqual(registry['test_path'], 'tests/test_scorching_ray.py')

    def test_readme_explains_split_targeting_and_upcasting(self) -> None:
        readme = (ITEM_ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('three rays', readme)
        self.assertIn('split targeting', readme)
        self.assertIn('Higher slots add one ray', readme)

    def test_implementation_doc_names_the_missing_multi_attack_primitive(self) -> None:
        implementation = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        self.assertIn('ordered duplicate or split per-ray targets', implementation)
        self.assertIn('one ranged spell attack per ray', implementation)

    def test_implementation_doc_records_the_slot_scaling_rule(self) -> None:
        implementation = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        self.assertIn('Upcasting increases ray count, not damage per hit', implementation)
        self.assertIn('one extra ray per slot level above 2', implementation)


if __name__ == '__main__':
    unittest.main()
