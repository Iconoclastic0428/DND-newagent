from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class RogueExpertiseFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:rogue:expertise'

    def _record(self):
        return self.complete_record('rogue', overrides={self.CHOICE_ID: ('acrobatics', 'thieves-tools'), 'class:rogue:weapon-mastery': ('dagger', 'shortbow')})

    def test_expertise_choices_persist_in_the_character_record(self) -> None:
        record = self._record()
        self.assertEqual(record.expertise_skill_ids, ('acrobatics',))
        self.assertEqual(record.expertise_tool_ids, ('thieves-tools',))

    def test_expertise_doubles_the_selected_skill_bonus(self) -> None:
        actor = self.compile_actor(self._record())
        self.assertEqual(actor.skill_bonuses['Acrobatics'], 6)

    def test_feature_name_is_recorded(self) -> None:
        record = self._record()
        self.assertIn('Expertise', record.class_feature_names)


if __name__ == '__main__':
    unittest.main()
