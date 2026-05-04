from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class DruidPrimalOrderFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:druid:feature:primal-order'

    def test_feature_name_is_recorded(self) -> None:
        record = self.complete_record('druid', overrides={self.CHOICE_ID: ('magician',)})
        self.assertIn('Primal Order', record.class_feature_names)

    def test_magician_choice_is_recorded_in_traits(self) -> None:
        record = self.complete_record('druid', overrides={self.CHOICE_ID: ('magician',)})
        self.assertEqual(self.choice_ids(record, self.CHOICE_ID), ('magician',))
        self.assertIn('Primal Order: Magician', record.traits)

    def test_magician_grants_an_extra_druid_cantrip(self) -> None:
        record = self.complete_record('druid', overrides={self.CHOICE_ID: ('magician',)})
        class_cantrips = [selection for selection in record.spell_selections if selection.spell_level == 0 and selection.source.source_kind.value == 'class']
        self.assertEqual(len(class_cantrips), 3)


if __name__ == '__main__':
    unittest.main()
