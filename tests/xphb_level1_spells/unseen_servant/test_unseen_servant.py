from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent, ItemTransferredEvent
from shared_types.encounter_intents import StartEncounterIntent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class UnseenServantLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Unseen Servant'
    SPELL_SLUG = 'unseen-servant'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        return session

    def _apply_followups(self, session, events):
        for event in events:
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)

    def _servant_actor_id(self, session) -> str:
        return next(actor_id for actor_id in session.state.actors if actor_id not in ('player-1', 'monster-skeleton-1', 'monster-mage-1'))

    def _ability(self, label: str):
        from shared_types.models import Ability
        return Ability[label]

    def test_command_shape_targets_a_point_with_description(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 unseen-servant 1 0 --description Carry supplies')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (1, 0))
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {'description': 'Carry supplies'})

    def test_command_shape_supports_transferring_allied_inventory(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        servant_id = self._servant_actor_id(session)
        intent = session.command_interface.parse_command(f'/interact {servant_id} transfer player-1 goodberry')
        self.assertEqual(intent.actor_id, servant_id)
        self.assertEqual(intent.interaction_kind.value, 'transfer')
        self.assertEqual(intent.source_actor_id, 'player-1')
        self.assertEqual(intent.item_id, 'goodberry')

    def test_cast_creates_a_servant_actor_with_the_expected_statline(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        servant = session.state.actors[self._servant_actor_id(session)]
        self.assertEqual(servant.name, 'Unseen Servant')
        self.assertEqual(servant.armor_class, 10)
        self.assertEqual(servant.max_hit_points, 1)
        self.assertEqual(servant.ability_scores[self._ability('STR')], 2)
        self.assertEqual(servant.speed_ft, 15)
        self.assertFalse(servant.attacks)

    def test_owner_controller_receives_control_binding_for_the_servant(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        servant_id = self._servant_actor_id(session)
        session.view_for_controller('player-1-controller')
        self.assertEqual(session.control_runtime.actor_controllers[servant_id], 'player-1-controller')

    def test_cast_during_combat_adds_the_servant_to_initiative(self) -> None:
        session = self._setup_session()
        session.command_interface.kernel.dispatch(
            session.state,
            StartEncounterIntent(participant_actor_ids=('player-1', 'monster-skeleton-1')),
        )
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        servant_id = self._servant_actor_id(session)
        self.assertIn(servant_id, session.state.initiative_order)

    def test_servant_can_receive_an_allied_item_and_use_it_on_its_turn(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].carried_item_counts['goodberry'] = 1
        session.command_interface.kernel._apply_event(
            session.state,
            DamageAppliedEvent(
                source_actor_id='monster-skeleton-1',
                target_id='player-1',
                damage_total=3,
                applied_damage_total=3,
                target_hit_points_after=max(0, session.state.actors['player-1'].current_hit_points - 3),
                target_temp_hit_points_after=0,
                damage_type='bludgeoning',
            ),
        )
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        servant_id = self._servant_actor_id(session)
        session.command_interface.kernel.dispatch(
            session.state,
            StartEncounterIntent(participant_actor_ids=('player-1', 'monster-skeleton-1', servant_id)),
        )
        self.advance_existing_turn(session, servant_id)
        result = session.execute_for_controller('player-1-controller', f'/interact {servant_id} transfer player-1 goodberry')
        self.assertIsNotNone(result.view)
        self.assertEqual(session.state.actors['player-1'].carried_item_counts.get('goodberry', 0), 0)
        self.assertEqual(session.state.actors[servant_id].carried_item_counts.get('goodberry', 0), 1)
        servant_before = session.state.actors[servant_id].current_hit_points
        player_before = session.state.actors['player-1'].current_hit_points
        session.execute_for_controller('player-1-controller', f'/use {servant_id} goodberry player-1')
        self.assertEqual(session.state.actors[servant_id].carried_item_counts.get('goodberry', 0), 0)
        self.assertGreaterEqual(session.state.actors['player-1'].current_hit_points, player_before)
        self.assertEqual(session.state.actors[servant_id].current_hit_points, servant_before)
        self.assertTrue(any(isinstance(event, ItemTransferredEvent) for event in session.state.event_log))

    def test_recasting_replaces_the_previous_servant(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        first_actor_id = self._servant_actor_id(session)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'description': 'Carry more supplies'})
        second_actor_id = self._servant_actor_id(session)
        self.assertNotEqual(first_actor_id, second_actor_id)
        self.assertNotIn(first_actor_id, session.state.actors)
        self.assertEqual(len(session.state.summoned_creatures), 1)

    def test_servant_dropping_to_zero_removes_the_summon_and_effect(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Carry supplies'})
        servant_id = self._servant_actor_id(session)
        session.command_interface.kernel._apply_event(
            session.state,
            DamageAppliedEvent(
                source_actor_id='monster-skeleton-1',
                target_id=servant_id,
                damage_total=5,
                applied_damage_total=5,
                target_hit_points_after=0,
                target_temp_hit_points_after=0,
                damage_type='force',
            ),
        )
        followups = session.command_interface.kernel._effect_reconciliation_events(session.state, actor_id=servant_id)
        self._apply_followups(session, followups)
        self.assertNotIn(servant_id, session.state.actors)
        self.assertFalse(session.state.summoned_creatures)
        self.assertFalse(any(effect.name == 'Unseen Servant' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
