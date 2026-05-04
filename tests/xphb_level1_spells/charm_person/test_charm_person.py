from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.d20 import D20RollMode
from shared_types.encounter_events import SaveRolledEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class CharmPersonLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Charm Person'
    SPELL_SLUG = 'charm-person'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 0, 0)
        return session

    def test_command_shape_targets_a_visible_humanoid(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 charm-person monster-mage-1')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-mage-1')

    def test_failed_save_applies_charmed_effect_for_one_hour(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.WIS] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Charm Person')
        self.assertEqual(effect.remaining_rounds, 600)
        conditions = {instance.condition_type for instance in session.state.actors['monster-mage-1'].condition_instances}
        self.assertIn(ConditionType.CHARMED, conditions)

    def test_successful_save_avoids_the_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.WIS] = 99
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1')
        self.assertFalse(any(effect.name == 'Charm Person' for effect in session.state.active_effects.values()))
        self.assertFalse(any(instance.condition_type == ConditionType.CHARMED for instance in session.state.actors['monster-mage-1'].condition_instances))

    def test_non_humanoid_target_is_rejected(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        with self.assertRaises(EncounterValidationError):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')

    def test_hostile_target_rolls_the_save_with_advantage(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.WIS] = 0
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1')
        save_event = next(event for event in session.state.event_log if isinstance(event, SaveRolledEvent))
        self.assertEqual(save_event.resolution.result.roll_mode, D20RollMode.ADVANTAGE)

    def test_damage_from_caster_side_ends_the_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.WIS] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Charm Person')
        events = session.command_interface.kernel._end_effects_on_source_side_damage(
            session.state,
            source_actor_id='player-1',
            target_id='monster-mage-1',
        )
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertFalse(any(active.effect_instance_id == effect.effect_instance_id for active in session.state.active_effects.values()))

    def test_effect_payload_notes_that_the_target_knows_afterward(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.WIS] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Charm Person')
        payload = effect.definition.information_payloads[0]
        self.assertIn('knows it was charmed', payload.detail)
        self.assertIn('friendly', payload.tags)


if __name__ == '__main__':
    unittest.main()
