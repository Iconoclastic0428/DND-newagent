from __future__ import annotations

import unittest
from pathlib import Path

from tests.xphb_level2_spells.support import build_local_spell_capability


class DragonSBreathLevel2SpellTests(unittest.TestCase):
    SPELL_NAME = "Dragon's Breath"
    SPELL_SLUG = 'dragon-s-breath'

    def test_executor_is_blocked_for_the_local_xphb_text(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertIsNone(capability)

    def test_definition_metadata_marks_the_spell_blocked(self) -> None:
        data = Path(__file__).resolve().parents[3] / 'content' / 'xphb' / 'spells' / 'level-2' / self.SPELL_SLUG / 'definition.json'
        self.assertIn('"runtime_status": "blocked"', data.read_text(encoding='utf-8'))

    def test_registry_metadata_marks_the_spell_blocked(self) -> None:
        data = Path(__file__).resolve().parents[3] / 'content' / 'xphb' / 'spells' / 'level-2' / self.SPELL_SLUG / 'registry.json'
        self.assertIn('"runtime_status": "blocked"', data.read_text(encoding='utf-8'))

    def test_readme_mentions_the_blocker(self) -> None:
        data = Path(__file__).resolve().parents[3] / 'content' / 'xphb' / 'spells' / 'level-2' / self.SPELL_SLUG / 'README.md'
        self.assertIn('Blocked:', data.read_text(encoding='utf-8'))

    def test_implementation_note_mentions_the_blocker(self) -> None:
        data = Path(__file__).resolve().parents[3] / 'content' / 'xphb' / 'spells' / 'level-2' / self.SPELL_SLUG / 'IMPLEMENTATION.md'
        text = data.read_text(encoding='utf-8')
        self.assertIn('Blocked:', text)
        self.assertIn('shared primitive', text)

if __name__ == '__main__':
    unittest.main()
