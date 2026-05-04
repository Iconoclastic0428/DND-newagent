from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class RogueWeaponMasteryFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:rogue:weapon-mastery'

    def _record(self):
        return self.complete_record('rogue', overrides={'class:rogue:expertise': ('acrobatics', 'thieves-tools'), self.CHOICE_ID: ('dagger', 'shortbow')})

    def test_feature_name_is_recorded_in_the_character_record(self) -> None:
        record = self._record()
        self.assertIn('Weapon Mastery', record.class_feature_names)

    def test_selected_weapon_masteries_persist_in_the_record(self) -> None:
        record = self._record()
        self.assertEqual(record.weapon_mastery_item_ids, ('dagger', 'shortbow'))
        self.assertEqual(record.weapon_mastery_item_ids, self.choice_ids(record, self.CHOICE_ID))

    def test_selected_mastery_items_compile_into_known_attacks(self) -> None:
        actor = self.compile_actor(self._record())
        attack_item_ids = {attack.source_item_id for attack in actor.attacks.values() if attack.source_item_id is not None}
        self.assertTrue({'dagger', 'shortbow'}.issubset(attack_item_ids))


if __name__ == '__main__':
    unittest.main()
