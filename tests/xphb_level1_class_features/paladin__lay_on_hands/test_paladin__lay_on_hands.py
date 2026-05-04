from __future__ import annotations

import unittest

from shared_types.conditions import ConditionInstance, ConditionType
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class PaladinLayOnHandsFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        session = self.build_session(self.complete_record('paladin', assign_command='/create ability assign 15 10 13 8 12 14'))
        self.advance_to_actor(session, 'player-1')
        return session

    def test_feature_name_and_pool_compile(self) -> None:
        record = self.complete_record('paladin', assign_command='/create ability assign 15 10 13 8 12 14')
        actor = self.compile_actor(record)
        self.assertIn('Lay on Hands', record.class_feature_names)
        self.assertEqual(actor.resource_pools['lay-on-hands'].current, 5)

    def test_lay_on_hands_heals_from_the_pool(self) -> None:
        session = self._session()
        session.state.actors['player-1'].current_hit_points = 3
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 lay-on-hands player-1 --amount 2')
        self.assertEqual(session.state.actors['player-1'].current_hit_points, 5)
        self.assertEqual(session.state.actors['player-1'].resource_pools['lay-on-hands'].current, 3)

    def test_lay_on_hands_can_remove_poisoned(self) -> None:
        session = self._session()
        actor = session.state.actors['player-1']
        actor.condition_instances = (
            ConditionInstance(instance_id='player-1:poisoned:test', condition_type=ConditionType.POISONED, source_label='test'),
        )
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 lay-on-hands player-1 --remove-condition poisoned')
        self.assertFalse(any(instance.condition_type == ConditionType.POISONED for instance in session.state.actors['player-1'].condition_instances))
        self.assertEqual(session.state.actors['player-1'].resource_pools['lay-on-hands'].current, 0)


if __name__ == '__main__':
    unittest.main()
