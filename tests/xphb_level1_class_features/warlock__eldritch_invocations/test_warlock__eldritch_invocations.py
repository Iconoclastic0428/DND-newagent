from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class WarlockEldritchInvocationsFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:warlock:feature:eldritch-invocation-options'

    def _record(self):
        return self.complete_record('warlock', assign_command='/create ability assign 10 14 13 12 8 15', overrides={self.CHOICE_ID: ('armor-of-shadows',)})

    def test_feature_name_is_recorded(self) -> None:
        record = self._record()
        self.assertIn('Eldritch Invocations', record.class_feature_names)

    def test_selected_invocation_label_is_recorded(self) -> None:
        record = self._record()
        self.assertEqual(self.choice_labels(record, self.CHOICE_ID), ('Armor of Shadows',))

    def test_selected_invocation_is_reflected_in_traits(self) -> None:
        record = self._record()
        self.assertIn('Armor of Shadows', ' '.join(record.traits))


if __name__ == '__main__':
    unittest.main()
