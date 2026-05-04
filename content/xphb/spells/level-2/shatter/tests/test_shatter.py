from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[6]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.xphb_level2_spells.support import build_local_spell_capability


ITEM_ROOT = Path(__file__).resolve().parents[1]


class ShatterBlockerTests(unittest.TestCase):
    SPELL_NAME = 'Shatter'
    SPELL_SLUG = 'shatter'

    def _read_json(self, filename: str) -> dict[str, object]:
        return json.loads((ITEM_ROOT / filename).read_text(encoding='utf-8'))

    def test_executor_returns_none_for_local_xphb_text(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertIsNone(capability)

    def test_definition_metadata_marks_the_spell_blocked(self) -> None:
        data = self._read_json('definition.json')
        self.assertEqual(data['runtime_status'], 'blocked')
        self.assertEqual(data['blocker_status'], 'needs-unattended-object-damage-primitive')
        self.assertEqual(data['implementation_family'], 'unattended-object-damage')

    def test_registry_metadata_marks_the_spell_blocked(self) -> None:
        data = self._read_json('registry.json')
        self.assertEqual(data['runtime_status'], 'blocked')
        self.assertEqual(data['blocker_status'], 'needs-unattended-object-damage-primitive')
        self.assertEqual(data['test_path'], 'content/xphb/spells/level-2/shatter/tests/test_shatter.py')

    def test_readme_mentions_the_blocker(self) -> None:
        text = (ITEM_ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('unattended-object damage primitive', text)
        self.assertIn('/cast player-1 shatter 5 2', text)

    def test_implementation_note_mentions_the_blocker(self) -> None:
        text = (ITEM_ROOT / 'IMPLEMENTATION.md').read_text(encoding='utf-8')
        self.assertIn('unattended-object damage primitive', text)
        self.assertIn('construct disadvantage', text)


if __name__ == '__main__':
    unittest.main()
