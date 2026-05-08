
from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent, ItemConsumedEvent
from shared_types.errors import EncounterValidationError
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class ChromaticOrbLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Chromatic Orb'
    SPELL_SLUG = 'chromatic-orb'

    def _command(self, *, material: str = 'diamond', damage_type: str = 'fire', jump_target: str = 'monster-mage-1') -> str:
        return f'/cast player-1 chromatic-orb monster-skeleton-1 --damage-type {damage_type} --material {material} --jump-target {jump_target}'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.actors['monster-mage-1'].armor_class = 0
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 0, 0)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _diamond_item_id(self, session) -> str:
        for item in session.command_interface.kernel.item_catalog.values():
            if 'diamond' in item.name.casefold() and item.cost_cp >= 5000:
                return item.record_id
        for item in session.command_interface.kernel.item_catalog.values():
            if 'diamond' in item.name.casefold():
                return item.record_id
        raise AssertionError('Could not locate a diamond item in the local catalog.')

    def _grant_material(self, session) -> str:
        item_id = self._diamond_item_id(session)
        session.state.actors['player-1'].carried_item_counts[item_id] = 1
        return item_id

    def test_command_shape_includes_damage_type_material_and_jump_target_parameters(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self._command())
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')
        self.assertEqual(tuple((param.key, param.value) for param in intent.parameters), (('damage-type', 'fire'), ('material', 'diamond'), ('jump-target', 'monster-mage-1')))

    def test_cast_is_rejected_without_a_valid_material_component(self) -> None:
        session = self._setup_session()
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, '/cast player-1 chromatic-orb monster-skeleton-1 --damage-type fire --jump-target monster-mage-1')

    def test_cast_is_rejected_with_an_invalid_damage_type(self) -> None:
        session = self._setup_session()
        self._grant_material(session)
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, self._command(material=self._diamond_item_id(session), damage_type='force'))

    def test_successful_cast_uses_the_requested_damage_type_and_material_component(self) -> None:
        session = self._setup_session()
        item_id = self._grant_material(session)
        starting_count = session.state.actors['player-1'].carried_item_counts[item_id]
        session.state, _ = session.command_interface.execute(session.state, self._command(material=item_id))
        damage_events = [event for event in session.state.event_log if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-skeleton-1']
        self.assertTrue(damage_events)
        self.assertEqual(damage_events[-1].damage_type, 'fire')
        spell = session.state.actors['player-1'].spells[self.SPELL_SLUG]
        if spell.material_component_consumed:
            self.assertEqual(session.state.actors['player-1'].carried_item_counts[item_id], starting_count - 1)
            self.assertTrue(any(isinstance(event, ItemConsumedEvent) and event.item_id == item_id for event in session.state.event_log))
        else:
            self.assertEqual(session.state.actors['player-1'].carried_item_counts[item_id], starting_count)

    def test_jump_target_receives_damage_when_the_duplicate_seed_is_found(self) -> None:
        for counter in range(80):
            session = self._setup_session()
            item_id = self._grant_material(session)
            session.state.random_counter = counter
            session.state, _ = session.command_interface.execute(session.state, self._command(material=item_id))
            target_damage = [event for event in session.state.event_log if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-skeleton-1']
            jump_damage = [event for event in session.state.event_log if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-mage-1']
            if not target_damage:
                continue
            if jump_damage:
                self.assertEqual(jump_damage[-1].damage_type, 'fire')
                return
        self.fail('Could not find a deterministic Chromatic Orb seed that produced a valid jump target hit.')


if __name__ == '__main__':
    unittest.main()
