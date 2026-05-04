from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class FighterFightingStyleFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:fighter:fighting-style'

    def test_selected_style_label_is_persisted(self) -> None:
        record = self.complete_record('fighter', overrides={self.CHOICE_ID: ('archery',)})
        self.assertEqual(record.fighting_style_names, ('Archery',))
        self.assertEqual(self.choice_labels(record, self.CHOICE_ID), ('Archery',))

    def test_dueling_adds_two_damage_to_one_handed_melee_attacks(self) -> None:
        record = self.complete_record('fighter', overrides={self.CHOICE_ID: ('dueling',)})
        actor = self.compile_actor(record)
        self.assertEqual(actor.attacks['flail-melee-str'].damage_bonus, 4)
        self.assertEqual(actor.attacks['greatsword-melee-str'].damage_bonus, 2)

    def test_feature_name_is_recorded(self) -> None:
        record = self.complete_record('fighter', overrides={self.CHOICE_ID: ('dueling',)})
        self.assertIn('Fighting Style', record.class_feature_names)


if __name__ == '__main__':
    unittest.main()
