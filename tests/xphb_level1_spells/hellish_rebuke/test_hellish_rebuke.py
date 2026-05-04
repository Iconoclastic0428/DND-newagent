from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent, SpellCastEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class HellishRebukeLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Hellish Rebuke'
    SPELL_SLUG = 'hellish-rebuke'
    COMMAND = '/cast player-1 hellish-rebuke monster-skeleton-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['player-1'].armor_class = 0
        session.state.actors['player-1'].current_hit_points = 20
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.actors['player-1'].spells.pop('shield', None)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'monster-skeleton-1')
        return session

    def _trigger_spell(self, session):
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/attack monster-skeleton-1 shortsword player-1')
        self.assertIsNotNone(session.state.pending_reaction_window)
        assert session.state.pending_reaction_window is not None
        self.assertEqual(session.state.pending_reaction_window.trigger_type.value, 'damage-taken')
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.actor_id == 'player-1')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        return [event for event in session.state.event_log[start_index:] if isinstance(event, DamageAppliedEvent)]

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_direct_cast_rejects_outside_a_damage_trigger_window(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        with self.assertRaisesRegex(EncounterValidationError, 'legal reaction window'):
            session.command_interface.execute(session.state, self.COMMAND)

    def test_damage_taken_opens_reaction_window_and_rebuke_damages_the_attacker(self) -> None:
        session = self._setup_session()
        damage_events = self._trigger_spell(session)
        self.assertFalse(session.state.actors['player-1'].reaction_available)
        self.assertTrue(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))
        self.assertTrue(any(event.target_id == 'monster-skeleton-1' and event.damage_type == 'fire' for event in damage_events))

    def test_successful_save_halves_the_fire_damage(self) -> None:
        failing = self._setup_session()
        failing.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -20
        fail_events = self._trigger_spell(failing)
        fail_damage = next(event.applied_damage_total for event in fail_events if event.target_id == 'monster-skeleton-1' and event.damage_type == 'fire')

        succeeding = self._setup_session()
        succeeding.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = 99
        success_events = self._trigger_spell(succeeding)
        success_damage = next(event.applied_damage_total for event in success_events if event.target_id == 'monster-skeleton-1' and event.damage_type == 'fire')

        self.assertLess(success_damage, fail_damage)

    def test_no_reaction_window_opens_if_the_caster_has_no_reaction_available(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].reaction_available = False
        session.state, _ = session.command_interface.execute(session.state, '/attack monster-skeleton-1 shortsword player-1')
        self.assertIsNone(session.state.pending_reaction_window)

    def test_reaction_window_opens_only_after_actual_damage_is_applied(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['player-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/attack monster-skeleton-1 shortsword player-1')
        self.assertLess(session.state.actors['player-1'].current_hit_points, start_hp)
        self.assertIsNotNone(session.state.pending_reaction_window)


if __name__ == '__main__':
    unittest.main()
