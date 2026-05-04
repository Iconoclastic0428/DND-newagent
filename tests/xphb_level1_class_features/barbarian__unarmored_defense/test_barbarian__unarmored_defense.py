from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class BarbarianUnarmoredDefenseFeatureTests(Level1ClassFeatureTestCase):
    def test_feature_name_is_recorded(self) -> None:
        record = self.complete_record('barbarian')
        self.assertIn('Unarmored Defense', record.class_feature_names)

    def test_default_unarmored_armor_class_uses_dexterity_and_constitution(self) -> None:
        record = self.complete_record('barbarian')
        actor = self.compile_actor(record)
        expected = 10 + record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'DEX')] + record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'CON')]
        self.assertEqual(actor.effective_armor_class, expected)

    def test_redistributing_dexterity_or_constitution_changes_unarmored_armor_class(self) -> None:
        lower = self.compile_actor(self.complete_record('barbarian', assign_command='/create ability assign 15 13 12 14 10 8')).effective_armor_class
        higher = self.compile_actor(self.complete_record('barbarian')).effective_armor_class
        self.assertGreater(higher, lower)


if __name__ == '__main__':
    unittest.main()
