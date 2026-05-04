from __future__ import annotations

import unittest

from shared_types.models import Ability
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class SorcererSpellcastingFeatureTestsTests(Level1ClassFeatureTestCase):
    def test_feature_name_is_recorded_in_the_character_record(self) -> None:
        record = self.complete_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15')
        self.assertIn('Spellcasting', record.class_feature_names)

    def test_level_one_record_contains_spell_selections(self) -> None:
        record = self.complete_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15')
        self.assertTrue(record.spell_selections)
        self.assertTrue(any(selection.spell_level in {0, 1} for selection in record.spell_selections))

    def test_compiled_actor_has_spellcasting_stats_and_slots(self) -> None:
        record = self.complete_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15')
        actor = self.compile_actor(record)
        self.assertEqual(actor.spellcasting_ability, Ability.CHA)
        self.assertIn('spell-slot-1', actor.resource_pools)
        self.assertTrue(actor.spells)


if __name__ == '__main__':
    unittest.main()
