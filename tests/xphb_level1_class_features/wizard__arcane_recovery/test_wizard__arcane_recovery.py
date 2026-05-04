from __future__ import annotations

import unittest

from shared_types.rest import RestState, RestStateStatus
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class WizardArcaneRecoveryFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        return self.build_session(self.complete_record('wizard', assign_command='/create ability assign 8 14 13 15 12 10', overrides={'class:wizard:spells': ('alarm', 'burning-hands', 'charm-person', 'detect-magic')}))

    def test_feature_name_and_resource_pool_compile(self) -> None:
        record = self.complete_record('wizard', assign_command='/create ability assign 8 14 13 15 12 10', overrides={'class:wizard:spells': ('alarm', 'burning-hands', 'charm-person', 'detect-magic')})
        actor = self.compile_actor(record)
        self.assertIn('Arcane Recovery', record.class_feature_names)
        self.assertIn('arcane-recovery', actor.resource_pools)

    def test_arcane_recovery_requires_a_completed_short_rest(self) -> None:
        session = self._session()
        with self.assertRaisesRegex(Exception, 'after completing a short rest'):
            session.command_interface.execute(session.state, '/feature player-1 arcane-recovery --slot-level 1')

    def test_arcane_recovery_restores_a_level_one_slot_and_spends_its_pool(self) -> None:
        session = self._session()
        actor = session.state.actors['player-1']
        actor.resource_pools['spell-slot-1'].current = 0
        actor.rest_state = RestState(status=RestStateStatus.SHORT_REST_COMPLETED)
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 arcane-recovery --slot-level 1')
        self.assertEqual(session.state.actors['player-1'].resource_pools['spell-slot-1'].current, 1)
        self.assertEqual(session.state.actors['player-1'].resource_pools['arcane-recovery'].current, 0)


if __name__ == '__main__':
    unittest.main()
