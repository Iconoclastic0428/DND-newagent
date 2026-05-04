from __future__ import annotations

import unittest

from shared_types.encounter_events import PersistentAreaCreatedEvent, PersistentAreaEndedEvent
from shared_types.encounter_models import GridPosition, TimingEntryKind
from shared_types.models import Ability
from shared_types.capabilities import TriggerTiming
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class GreaseLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Grease'
    SPELL_SLUG = 'grease'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        return session

    def _apply_events(self, session, events):
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)

    def _area(self, session):
        return next(iter(session.state.persistent_areas.values()))

    def test_command_shape_is_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 grease 2 0')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y, intent.z), (2, 0, None))

    def test_cast_creates_persistent_area_and_difficult_terrain(self) -> None:
        session = self._setup_session()
        events = self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0))
        self.assertTrue(any(isinstance(event, PersistentAreaCreatedEvent) for event in events))
        self.assertEqual(self._area(session).definition.name, 'Grease')
        self.assertTrue(self._area(session).definition.difficult_terrain)

    def test_creature_in_area_on_cast_can_fall_prone(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0))
        prone = {instance.condition_type.value for instance in session.state.actors['monster-skeleton-1'].condition_instances}
        self.assertIn('prone', prone)

    def test_creature_entering_area_makes_save(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.DEX] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0))
        events = session.command_interface.kernel._persistent_area_transition_events(
            session.state,
            actor_id='monster-mage-1',
            from_position=GridPosition(9, 9, 0),
            to_position=GridPosition(2, 0, 0),
        )
        self._apply_events(session, events)
        prone = {instance.condition_type.value for instance in session.state.actors['monster-mage-1'].condition_instances}
        self.assertIn('prone', prone)

    def test_end_of_turn_tick_rechecks_creature_standing_in_area(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0))
        entries = session.command_interface.kernel.effect_executor.collect_turn_boundary_entries(
            session.state,
            actor_id='monster-skeleton-1',
            timing=TriggerTiming.END_OF_TURN,
        )
        tick_entry = next(entry for entry in entries if entry.kind == TimingEntryKind.PERSISTENT_AREA_TICK)
        tick_events = session.command_interface.kernel.effect_executor.resolve_turn_boundary_entry(session.state, tick_entry)
        self._apply_events(session, tick_events)
        self.assertTrue(any(event.__class__.__name__ == 'PersistentAreaTickedEvent' for event in tick_events))

    def test_ending_effect_clears_area_and_overlay(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0))
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Grease')
        events = session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end')
        self._apply_events(session, events)
        self.assertFalse(session.state.persistent_areas)
        self.assertFalse(session.state.battlefield.difficult_terrain_positions)
        self.assertTrue(any(isinstance(event, PersistentAreaEndedEvent) for event in events))


if __name__ == '__main__':
    unittest.main()
