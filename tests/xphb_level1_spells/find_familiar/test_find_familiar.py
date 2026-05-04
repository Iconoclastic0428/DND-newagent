from __future__ import annotations

import unittest

from session_server.web_projection import _observer_actor_ids
from shared_types.conditions import ConditionType
from shared_types.encounter_events import DamageAppliedEvent, HealingAppliedEvent, ItemConsumedEvent
from shared_types.encounter_intents import ContinueTimingIntent, StartEncounterIntent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class FindFamiliarLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Find Familiar'
    SPELL_SLUG = 'find-familiar'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].carried_item_counts['spell-incense'] = 2
        return session

    def _apply_followups(self, session, events):
        for event in events:
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)

    def _summoned_actor_ids(self, session) -> list[str]:
        return [actor_id for actor_id in session.state.actors if actor_id not in ('player-1', 'monster-skeleton-1', 'monster-mage-1')]

    def test_command_shape_supports_form_type_and_material(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 find-familiar 1 0 --form owl --type celestial --material incense')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (1, 0))
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {
            'form': 'owl',
            'type': 'celestial',
            'material': 'incense',
        })
        sense_intent = session.command_interface.parse_command('/sense player-1 familiar-actor')
        self.assertEqual(sense_intent.actor_id, 'player-1')
        self.assertEqual(sense_intent.familiar_actor_id, 'familiar-actor')

    def test_material_component_requires_incense(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        actor = session.state.actors['player-1']
        spell = actor.spells[self.SPELL_SLUG]
        with self.assertRaises(EncounterValidationError):
            session.command_interface.kernel._spell_material_events(actor, spell, parameters={'material': 'incense'})

    def test_material_component_can_be_consumed(self) -> None:
        session = self._setup_session()
        actor = session.state.actors['player-1']
        spell = actor.spells[self.SPELL_SLUG]
        events = session.command_interface.kernel._spell_material_events(actor, spell, parameters={'material': 'incense'})
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ItemConsumedEvent)
        self.assertEqual(events[0].item_id, 'spell-incense')

    def test_cast_creates_a_familiar_actor_owned_by_the_caster_and_shared_sense_proxy(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(
            session,
            spell_id=self.SPELL_SLUG,
            point=GridPosition(1, 0, 0),
            parameters={'form': 'owl', 'type': 'celestial', 'material': 'incense'},
        )
        summon = next(iter(session.state.summoned_creatures.values()))
        self.assertIsNotNone(summon.linked_actor_id)
        familiar = session.state.actors[summon.linked_actor_id]
        self.assertEqual(familiar.creature_type, 'celestial')
        self.assertEqual(familiar.summon_owner_actor_id, 'player-1')
        self.assertEqual(familiar.shared_sense_owner_actor_id, 'player-1')
        self.assertFalse(familiar.attacks)
        self.assertIn('familiar', summon.definition.semantic_tags)

    def test_recasting_replaces_the_previous_familiar(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'form': 'owl', 'type': 'celestial', 'material': 'incense'})
        first_actor_id = self._summoned_actor_ids(session)[0]
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'form': 'cat', 'type': 'fey', 'material': 'incense'})
        self.assertEqual(len(session.state.summoned_creatures), 1)
        second_actor_id = self._summoned_actor_ids(session)[0]
        self.assertNotEqual(first_actor_id, second_actor_id)
        self.assertNotIn(first_actor_id, session.state.actors)
        self.assertEqual(session.state.actors[second_actor_id].creature_type, 'fey')

    def test_cast_during_combat_adds_the_familiar_to_initiative_and_shared_senses_expire_at_next_turn(self) -> None:
        session = self._setup_session()
        session.command_interface.kernel.dispatch(
            session.state,
            StartEncounterIntent(participant_actor_ids=('player-1', 'monster-skeleton-1')),
        )
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'form': 'owl', 'type': 'celestial', 'material': 'incense'})
        familiar_id = self._summoned_actor_ids(session)[0]
        self.assertIn(familiar_id, session.state.initiative_order)
        self.advance_existing_turn(session, 'player-1')
        result = session.execute_for_controller('player-1-controller', f'/sense player-1 {familiar_id}')
        self.assertIsNotNone(result.view)
        owner = session.state.actors['player-1']
        self.assertFalse(owner.bonus_action_available)
        self.assertEqual(owner.shared_senses_actor_id, familiar_id)
        self.assertEqual(_observer_actor_ids(session, 'player-1-controller'), (familiar_id,))
        condition_types = {instance.condition_type for instance in owner.condition_instances}
        self.assertIn(ConditionType.BLINDED, condition_types)
        self.assertIn(ConditionType.DEAFENED, condition_types)
        self.end_turn_and_resolve(session, 'player-1')
        while session.state.active_actor_id != 'player-1':
            current_actor_id = session.state.active_actor_id
            session.state, _ = session.command_interface.execute(session.state, f'/endturn {current_actor_id}')
            while session.state.pending_timing_queue is not None:
                session.state = session.command_interface.kernel.dispatch(
                    session.state,
                    ContinueTimingIntent(actor_id=session.state.pending_timing_queue.actor_id),
                )
        owner = session.state.actors['player-1']
        self.assertIsNone(owner.shared_senses_actor_id)
        condition_types = {instance.condition_type for instance in owner.condition_instances}
        self.assertNotIn(ConditionType.BLINDED, condition_types)
        self.assertNotIn(ConditionType.DEAFENED, condition_types)

    def test_familiar_can_deliver_touch_spell_through_shared_senses(self) -> None:
        session = self._setup_session()
        self.grant_spell(session, 'Cure Wounds')
        self.apply_spell_events(
            session,
            spell_id=self.SPELL_SLUG,
            point=GridPosition(1, 0, 0),
            parameters={'form': 'owl', 'type': 'celestial', 'material': 'incense'},
        )
        familiar_id = self._summoned_actor_ids(session)[0]
        familiar = session.state.actors[familiar_id]
        familiar.position = GridPosition(1, 0, 0)
        target = session.state.actors['monster-mage-1']
        target.position = GridPosition(2, 0, 0)
        target.max_hit_points = max(target.max_hit_points, 10)
        target.current_hit_points = 1
        events = self.apply_spell_events(
            session,
            spell_id='cure-wounds',
            target_id='monster-mage-1',
            parameters={'through': familiar_id},
        )
        healing_events = [event for event in events if isinstance(event, HealingAppliedEvent)]
        self.assertEqual(len(healing_events), 1)
        self.assertEqual(healing_events[0].source_actor_id, 'player-1')
        self.assertEqual(healing_events[0].target_id, 'monster-mage-1')
        self.assertGreater(session.state.actors['monster-mage-1'].current_hit_points, 1)
        self.assertFalse(session.state.actors[familiar_id].reaction_available)
        with self.assertRaises(EncounterValidationError):
            self.apply_spell_events(
                session,
                spell_id='cure-wounds',
                target_id='monster-mage-1',
                parameters={'through': familiar_id},
            )

    def test_familiar_dropping_to_zero_removes_the_summon_and_effect(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'form': 'owl', 'type': 'celestial', 'material': 'incense'})
        familiar_id = self._summoned_actor_ids(session)[0]
        session.command_interface.kernel.dispatch(session.state, session.command_interface.parse_command(f'/sense player-1 {familiar_id}'))
        session.command_interface.kernel._apply_event(
            session.state,
            DamageAppliedEvent(
                source_actor_id='monster-skeleton-1',
                target_id=familiar_id,
                damage_total=5,
                applied_damage_total=5,
                target_hit_points_after=0,
                target_temp_hit_points_after=0,
                damage_type='force',
            ),
        )
        followups = session.command_interface.kernel._effect_reconciliation_events(session.state, actor_id=familiar_id)
        self._apply_followups(session, followups)
        self.assertNotIn(familiar_id, session.state.actors)
        self.assertFalse(session.state.summoned_creatures)
        self.assertFalse(any(effect.name == 'Find Familiar' for effect in session.state.active_effects.values()))
        owner = session.state.actors['player-1']
        self.assertIsNone(owner.shared_senses_actor_id)
        condition_types = {instance.condition_type for instance in owner.condition_instances}
        self.assertNotIn(ConditionType.BLINDED, condition_types)
        self.assertNotIn(ConditionType.DEAFENED, condition_types)


if __name__ == '__main__':
    unittest.main()
