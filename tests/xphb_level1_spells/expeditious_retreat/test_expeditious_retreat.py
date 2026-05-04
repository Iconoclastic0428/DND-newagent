from __future__ import annotations

import unittest

from shared_types.encounter_events import ActionEffectEvent, ActiveEffectEndedEvent, ActiveEffectStartedEvent
from shared_types.encounter_models import CombatActionType
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase



class ExpeditiousRetreatLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Expeditious Retreat'
    SPELL_SLUG = 'expeditious-retreat'
    COMMAND = '/cast player-1 expeditious-retreat player-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _active_effect(self, session):
        return next((effect for effect in session.state.active_effects.values() if effect.name == 'Expeditious Retreat'), None)

    def test_command_shape_uses_the_supported_self_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_cast_creates_the_active_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertIsNotNone(self._active_effect(session))
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Expeditious Retreat' for event in session.state.event_log))

    def test_cast_immediately_grants_bonus_action_dash_and_movement_budget(self) -> None:
        session = self._setup_session()
        actor = session.state.actors['player-1']
        start_remaining = actor.remaining_movement_ft
        start_dash_bonus = actor.dash_bonus_ft
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        actor = session.state.actors['player-1']
        self.assertTrue(actor.can_dash_as_bonus_action)
        self.assertGreater(actor.remaining_movement_ft, start_remaining)
        self.assertGreater(actor.dash_bonus_ft, start_dash_bonus)
        self.assertTrue(any(isinstance(event, ActionEffectEvent) and event.actor_id == 'player-1' and event.dash_bonus_ft is not None for event in session.state.event_log))

    def test_effect_definition_tracks_concentration_and_ten_minute_duration(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        effect = self._active_effect(session)
        assert effect is not None
        self.assertTrue(effect.definition.concentration)
        self.assertEqual(effect.definition.duration.rounds, 100)

    def test_effect_persists_through_a_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertIsNotNone(self._active_effect(session))

    def test_concentration_break_ends_the_bonus_dash_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        effect = self._active_effect(session)
        assert effect is not None
        for event in session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end'):
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertIsNone(self._active_effect(session))
        self.assertFalse(session.state.actors['player-1'].can_dash_as_bonus_action)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'test-end' for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
