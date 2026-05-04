from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageRolledEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase


class FireBoltCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Fire Bolt')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_attack_bonus = 99
        return session

    def _damage_event(self, session):
        return next(
            event
            for event in reversed(session.state.event_log)
            if isinstance(event, DamageRolledEvent) and event.damage_type == 'fire'
        )

    def test_hit_deals_fire_damage(self) -> None:
        session = self._setup_session()
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.armor_class = 0
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 fire-bolt monster-skeleton-1')
        self.assertLess(target.current_hit_points, start_hp)
        self.assertEqual(self._damage_event(session).damage_type, 'fire')

    def test_miss_deals_no_damage(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 0
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.armor_class = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 fire-bolt monster-skeleton-1')
        self.assertEqual(target.current_hit_points, start_hp)

    def test_damage_scales_at_fifth_level(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].level = 5
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 fire-bolt monster-skeleton-1')
        self.assertEqual(len(self._damage_event(session).damage_rolls), 2)


if __name__ == '__main__':
    unittest.main()
