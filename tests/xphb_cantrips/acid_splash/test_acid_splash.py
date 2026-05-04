from __future__ import annotations

import unittest

from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType
from shared_types.encounter_events import DamageRolledEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_cantrips.support import EncounterCantripTestCase


class AcidSplashCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Acid Splash')
        self.advance_to_actor(session, 'player-1')
        return session

    def _damage_event(self, session):
        return next(
            event
            for event in reversed(session.state.event_log)
            if isinstance(event, DamageRolledEvent) and event.damage_type == 'acid'
        )

    def test_failed_save_deals_acid_damage_in_the_selected_area(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 acid-splash {target.position.x} {target.position.y}')
        self.assertLess(target.current_hit_points, start_hp)
        self.assertEqual(self._damage_event(session).damage_type, 'acid')

    def test_successful_save_negates_the_damage(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Acid Splash')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 1
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.saving_throw_bonuses[Ability.DEX] = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 acid-splash {target.position.x} {target.position.y}')
        self.assertEqual(target.current_hit_points, start_hp)

    def test_cantrip_damage_scales_at_fifth_level(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].level = 5
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 acid-splash {target.position.x} {target.position.y}')
        self.assertEqual(len(self._damage_event(session).damage_rolls), 2)


if __name__ == '__main__':
    unittest.main()
