from __future__ import annotations

import unittest

from shared_types.battlefield import TraversalMode
from shared_types.encounter_events import ActiveEffectEndedEvent, MovementSpentEvent
from shared_types.encounter_intents import DismountActorIntent, MountActorIntent, StartEncounterIntent
from shared_types.encounter_models import GridPosition
from shared_types.models import ItemRecord
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class TenserSFloatingDiskLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = "Tenser's Floating Disk"
    SPELL_SLUG = 'tenser-s-floating-disk'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        return session

    def _apply_followups(self, session, events):
        for event in events:
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)

    def _disk_actor_id(self, session) -> str:
        return next(actor_id for actor_id in session.state.actors if actor_id not in ('player-1', 'monster-skeleton-1', 'monster-mage-1'))

    def _add_weighted_item(self, session, *, item_id: str, name: str, weight_lb: float) -> None:
        session.command_interface.kernel.item_catalog[item_id] = ItemRecord(
            record_id=item_id,
            name=name,
            source='XPHB',
            edition='2024',
            official=True,
            homebrew=False,
            cost_cp=0,
            weight_lb=weight_lb,
            is_magical=False,
            tags=('test-item',),
        )
        session.state.actors['player-1'].carried_item_counts[item_id] = 1

    def test_command_shape_targets_a_point_with_description(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 tenser-s-floating-disk 1 0 --description Lift cargo')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (1, 0))
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {'description': 'Lift cargo'})
        mount_intent = session.command_interface.parse_command('/mount rider disk-actor')
        self.assertEqual(mount_intent.actor_id, 'rider')
        self.assertEqual(mount_intent.mount_actor_id, 'disk-actor')
        dismount_intent = session.command_interface.parse_command('/dismount rider')
        self.assertEqual(dismount_intent.actor_id, 'rider')

    def test_cast_creates_a_floating_disk_actor(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        disk_id = self._disk_actor_id(session)
        disk = session.state.actors[disk_id]
        self.assertEqual(disk.name, "Tenser's Floating Disk")
        self.assertEqual(disk.summon_owner_actor_id, 'player-1')
        self.assertFalse(disk.attacks)
        self.assertEqual(disk.position, GridPosition(1, 0, 0))

    def test_disk_follows_with_transferred_cargo_under_the_weight_limit(self) -> None:
        session = self._setup_session()
        self._add_weighted_item(session, item_id='disk-cargo', name='Disk Cargo', weight_lb=120)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        disk_id = self._disk_actor_id(session)
        session.execute_for_controller('player-1-controller', f'/interact {disk_id} transfer player-1 disk-cargo')
        self.assertEqual(session.state.actors[disk_id].carried_item_counts.get('disk-cargo', 0), 1)
        move = MovementSpentEvent(
            actor_id='player-1',
            from_position=session.state.actors['player-1'].position,
            to_position=GridPosition(6, 0, 0),
            distance_ft=30,
            remaining_movement_ft=0,
            movement_mode=TraversalMode.WALK,
            movement_spent_ft=30,
        )
        session.command_interface.kernel._apply_event(session.state, move)
        disk = session.state.actors[self._disk_actor_id(session)]
        distance_ft = session.command_interface.kernel.battlefield_rules.get_distance3d(session.state.actors['player-1'].position, disk.position)
        self.assertLessEqual(distance_ft, 20)
        self.assertEqual(disk.position, GridPosition(2, 0, 0))
        self.assertEqual(disk.carried_item_counts.get('disk-cargo', 0), 1)

    def test_rider_moves_with_the_disk(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        disk_id = self._disk_actor_id(session)
        rider = session.state.actors['monster-mage-1']
        rider.body_weight_lb = 180
        rider.position = session.state.actors[disk_id].position
        session.command_interface.kernel.dispatch(session.state, MountActorIntent(actor_id='monster-mage-1', mount_actor_id=disk_id))
        self.assertEqual(rider.mounted_on_actor_id, disk_id)
        move = MovementSpentEvent(
            actor_id='player-1',
            from_position=session.state.actors['player-1'].position,
            to_position=GridPosition(6, 0, 0),
            distance_ft=30,
            remaining_movement_ft=0,
            movement_mode=TraversalMode.WALK,
            movement_spent_ft=30,
        )
        session.command_interface.kernel._apply_event(session.state, move)
        self.assertEqual(session.state.actors[disk_id].position, rider.position)
        session.command_interface.kernel.dispatch(session.state, DismountActorIntent(actor_id='monster-mage-1'))
        self.assertIsNone(rider.mounted_on_actor_id)

    def test_overloaded_disk_by_cargo_ends_the_spell_and_drops_the_cargo(self) -> None:
        session = self._setup_session()
        self._add_weighted_item(session, item_id='disk-cargo', name='Disk Cargo', weight_lb=510)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        disk_id = self._disk_actor_id(session)
        session.execute_for_controller('player-1-controller', f'/interact {disk_id} transfer player-1 disk-cargo')
        move = MovementSpentEvent(
            actor_id='player-1',
            from_position=session.state.actors['player-1'].position,
            to_position=GridPosition(6, 0, 0),
            distance_ft=30,
            remaining_movement_ft=0,
            movement_mode=TraversalMode.WALK,
            movement_spent_ft=30,
        )
        session.command_interface.kernel._apply_event(session.state, move)
        self.assertFalse(session.state.summoned_creatures)
        self.assertFalse(any(actor_id.endswith(':actor') for actor_id in session.state.actors))
        self.assertTrue(any(ground_item.item_id == 'disk-cargo' for ground_item in session.state.ground_items.values()))

    def test_overloaded_disk_by_rider_weight_ends_the_spell(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        disk_id = self._disk_actor_id(session)
        rider = session.state.actors['monster-mage-1']
        rider.body_weight_lb = 510
        rider.position = session.state.actors[disk_id].position
        session.command_interface.kernel.dispatch(session.state, MountActorIntent(actor_id='monster-mage-1', mount_actor_id=disk_id))
        move = MovementSpentEvent(
            actor_id='player-1',
            from_position=session.state.actors['player-1'].position,
            to_position=GridPosition(6, 0, 0),
            distance_ft=30,
            remaining_movement_ft=0,
            movement_mode=TraversalMode.WALK,
            movement_spent_ft=30,
        )
        session.command_interface.kernel._apply_event(session.state, move)
        self.assertFalse(session.state.summoned_creatures)
        self.assertFalse(any(actor_id.endswith(':actor') for actor_id in session.state.actors))
        self.assertIsNone(rider.mounted_on_actor_id)

    def test_owner_moving_more_than_one_hundred_feet_ends_the_spell(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        move = MovementSpentEvent(
            actor_id='player-1',
            from_position=session.state.actors['player-1'].position,
            to_position=GridPosition(25, 0, 0),
            distance_ft=125,
            remaining_movement_ft=0,
            movement_mode=TraversalMode.WALK,
            movement_spent_ft=125,
        )
        session.command_interface.kernel._apply_event(session.state, move)
        self.assertFalse(session.state.summoned_creatures)
        self.assertFalse(any(actor_id.endswith(':actor') for actor_id in session.state.actors))

    def test_disk_is_not_added_to_initiative_during_combat(self) -> None:
        session = self._setup_session()
        session.command_interface.kernel.dispatch(
            session.state,
            StartEncounterIntent(participant_actor_ids=('player-1', 'monster-skeleton-1')),
        )
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        disk_id = self._disk_actor_id(session)
        self.assertNotIn(disk_id, session.state.initiative_order)

    def test_ending_the_effect_removes_the_disk_actor(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(1, 0, 0), parameters={'description': 'Lift cargo'})
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == self.SPELL_NAME)
        events = session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end')
        self._apply_followups(session, events)
        self.assertFalse(session.state.summoned_creatures)
        self.assertFalse(any(actor_id.endswith(':actor') for actor_id in session.state.actors))
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) for event in events))


if __name__ == '__main__':
    unittest.main()
