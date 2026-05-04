from __future__ import annotations

import unittest

from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent, DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class WitchBoltLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Witch Bolt'
    SPELL_SLUG = 'witch-bolt'
    COMMAND = '/cast player-1 witch-bolt monster-skeleton-1'
    SUSTAIN_COMMAND = '/cast player-1 witch-bolt monster-skeleton-1 --mode sustain'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(3, 0, 0)
        session.state.actors['monster-skeleton-1'].armor_class = 10
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _active_effect(self, session):
        return next((effect for effect in session.state.active_effects.values() if effect.name == 'Witch Bolt'), None)

    def test_command_shapes_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        cast_intent = session.command_interface.parse_command(self.COMMAND)
        sustain_intent = session.command_interface.parse_command(self.SUSTAIN_COMMAND)
        self.assertEqual(cast_intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(sustain_intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(sustain_intent.parameters[0].key, 'mode')
        self.assertEqual(sustain_intent.parameters[0].value, 'sustain')

    def test_hit_deals_damage_and_starts_the_linked_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-skeleton-1'].armor_class = 0
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertIsNotNone(self._active_effect(session))
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Witch Bolt' for event in session.state.event_log))

    def test_miss_still_starts_the_linked_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = -99
        session.state.actors['monster-skeleton-1'].armor_class = 99
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertIsNotNone(self._active_effect(session))

    def test_sustain_deals_follow_up_damage_and_spends_bonus_action(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        start_index = len(session.state.event_log)
        target_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, self.SUSTAIN_COMMAND)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, target_hp)
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-skeleton-1' and event.damage_type == 'lightning' for event in session.state.event_log[start_index:]))

    def test_sustain_rejects_without_an_active_witch_bolt_effect(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(EncounterValidationError, 'no active Witch Bolt effect'):
            session.command_interface.execute(session.state, self.SUSTAIN_COMMAND)

    def test_link_ends_when_the_target_moves_out_of_range(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state.actors['monster-skeleton-1'].position = GridPosition(20, 0, 0)
        events = session.command_interface.kernel._effect_reconciliation_events(session.state, actor_id='player-1')
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertIsNone(self._active_effect(session))
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'target-out-of-range' for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
