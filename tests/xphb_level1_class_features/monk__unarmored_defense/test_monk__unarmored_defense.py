from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class MonkUnarmoredDefenseFeatureTests(Level1ClassFeatureTestCase):
    def _record(self, assign_command='/create ability assign 8 15 13 10 14 12'):
        return self.complete_record('monk', assign_command=assign_command)

    def test_feature_name_is_recorded(self) -> None:
        record = self._record()
        self.assertIn('Unarmored Defense', record.class_feature_names)

    def test_armor_class_uses_dexterity_and_wisdom(self) -> None:
        record = self._record()
        actor = self.compile_actor(record)
        expected = 10 + record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'DEX')] + record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'WIS')]
        self.assertEqual(actor.effective_armor_class, expected)

    def test_higher_wisdom_increases_armor_class(self) -> None:
        baseline = self.compile_actor(self._record(assign_command='/create ability assign 8 15 13 10 12 14')).effective_armor_class
        boosted = self.compile_actor(self._record(assign_command='/create ability assign 8 15 13 10 14 12')).effective_armor_class
        self.assertGreater(boosted, baseline)


if __name__ == '__main__':
    unittest.main()
