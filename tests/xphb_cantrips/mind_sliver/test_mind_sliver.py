from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageRolledEvent
from shared_types.encounter_models import GridPosition
from shared_types.effects import ResolutionContext, SaveRequest
from shared_types.models import Ability
from tests.xphb_cantrips.support import EncounterCantripTestCase


class MindSliverCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Mind Sliver')
        self.advance_to_actor(session, 'player-1')
        return session

    def _damage_event(self, session):
        return next(
            event
            for event in reversed(session.state.event_log)
            if isinstance(event, DamageRolledEvent) and event.damage_type == 'psychic'
        )

    def test_failed_save_deals_psychic_damage_and_applies_the_next_save_penalty(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mind-sliver monster-skeleton-1')
        self.assertLess(target.current_hit_points, start_hp)
        modifier, events = session.command_interface.kernel._saving_throw_effect_modifier(session.state, actor_id='monster-skeleton-1')
        self.assertLess(modifier, 0)
        self.assertTrue(events)

    def test_successful_save_negates_damage_and_penalty(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 1
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        target.saving_throw_bonuses[Ability.INT] = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mind-sliver monster-skeleton-1')
        self.assertEqual(target.current_hit_points, start_hp)
        modifier, events = session.command_interface.kernel._saving_throw_effect_modifier(session.state, actor_id='monster-skeleton-1')
        self.assertEqual(modifier, 0)
        self.assertFalse(events)

    def test_next_saving_throw_consumes_the_penalty(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mind-sliver monster-skeleton-1')
        request = SaveRequest(
            context=ResolutionContext(effect_id='mind-sliver-followup', source_actor_id='player-1', target_actor_id='monster-skeleton-1', reason='Mind Sliver follow-up save'),
            ability=Ability.DEX,
            dc=10,
        )
        _, _ = session.command_interface.kernel.resolve_save_consumer(session.state, request, apply=True)
        modifier, events = session.command_interface.kernel._saving_throw_effect_modifier(session.state, actor_id='monster-skeleton-1')
        self.assertEqual(modifier, 0)
        self.assertFalse(events)


if __name__ == '__main__':
    unittest.main()

