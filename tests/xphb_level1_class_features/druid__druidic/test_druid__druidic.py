from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class DruidDruidicFeatureTests(Level1ClassFeatureTestCase):
    def test_feature_name_is_recorded_in_the_character_record(self) -> None:
        record = self.complete_record('druid')
        self.assertIn('Druidic', record.class_feature_names)

    def test_feature_trait_is_present_in_the_character_record(self) -> None:
        record = self.complete_record('druid')
        self.assertIn('Druidic', ' '.join(record.traits))

    def test_feature_compiles_without_runtime_errors(self) -> None:
        actor = self.compile_actor(self.complete_record('druid'))
        self.assertEqual(actor.actor_id, 'player-1')


if __name__ == '__main__':
    unittest.main()
