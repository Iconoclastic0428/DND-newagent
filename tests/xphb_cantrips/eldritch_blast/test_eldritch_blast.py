from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageRolledEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase


class EldritchBlastCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Eldritch Blast')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_attack_bonus = 99
        return session

    def _damage_event(self, session):
        return next(
            event
            for event in reversed(session.state.event_log)
            if isinstance(event, DamageRolledEvent) and event.damage_type == 'force'
        )

    def test_hit_deals_force_damage(self) -> None:
        session = self._setup_session()
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.armor_class = 0
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 eldritch-blast monster-skeleton-1')
        self.assertLess(target.current_hit_points, start_hp)
        self.assertEqual(self._damage_event(session).damage_type, 'force')

    def test_miss_deals_no_damage(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 0
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.armor_class = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 eldritch-blast monster-skeleton-1')
        self.assertEqual(target.current_hit_points, start_hp)

    def test_out_of_range_target_is_rejected(self) -> None:
        session = self._setup_session()
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 200, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        with self.assertRaisesRegex(EncounterValidationError, 'range'):
            session.command_interface.execute(session.state, '/cast player-1 eldritch-blast monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
