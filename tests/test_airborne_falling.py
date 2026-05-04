from __future__ import annotations

from pathlib import Path
import unittest

from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface
from session_server.bootstrap import build_default_character_record
from shared_types.battlefield import FallReason, SupportStateType
from shared_types.conditions import ConditionType
from shared_types.encounter_events import (
    ConditionAddedEvent,
    FallDamageRolledEvent,
    FallLandedEvent,
    FallStartedEvent,
    SupportStateEvaluatedEvent,
    TeleportResolvedEvent,
)
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from shared_types.errors import EncounterValidationError


LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class AirborneFallingTests(unittest.TestCase):
    def _build_runtime(self):
        return build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def _monster_id(self, runtime, *, name: str, source: str) -> str:
        for record_id, record in runtime.encounter_catalog.monsters.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f'Monster not found: {name} [{source}]')

    def _build_state(
        self,
        *,
        player_position: GridPosition = GridPosition(0, 0, 0),
        skeleton_position: GridPosition = GridPosition(20, 0, 0),
        mage_position: GridPosition = GridPosition(8, 2, 0),
    ):
        runtime = self._build_runtime()
        record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        mage_id = self._monster_id(runtime, name='Mage', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=player_position),),
            monsters=(
                MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=skeleton_position),
                MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=mage_position),
            ),
        )
        return runtime, state

    def _advance_to_actor(self, ui: EncounterSlashCommandInterface, state, actor_id: str):
        guard = 0
        while state.active_actor_id != actor_id:
            guard += 1
            if guard > 10:
                raise AssertionError(f'Could not reach actor turn: {actor_id}')
            state, _ = ui.execute(state, f'/endturn {state.active_actor_id}')
        return state

    def _condition_instance(self, runtime, actor_id: str, condition_type: ConditionType):
        return runtime.kernel._make_condition_instance(
            target_actor_id=actor_id,
            condition_type=condition_type,
            source_label=f'test-{condition_type.value}',
        )

    def test_misty_step_into_open_air_triggers_fall_and_keeps_movement_unspent(self) -> None:
        runtime, state = self._build_state(mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'monster-mage-1')
        mage_before = state.actors['monster-mage-1']
        start_movement = mage_before.remaining_movement_ft

        state, _ = ui.execute(state, '/cast monster-mage-1 misty-step 5 2 10')

        mage = state.actors['monster-mage-1']
        self.assertEqual(mage.position, GridPosition(5, 2, 0))
        self.assertEqual(mage.remaining_movement_ft, start_movement)
        self.assertFalse(mage.bonus_action_available)
        self.assertEqual(mage.support_state, SupportStateType.GROUNDED)
        self.assertTrue(any(isinstance(event, TeleportResolvedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, FallStartedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, FallLandedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, FallDamageRolledEvent) for event in state.event_log))
        self.assertIn(ConditionType.PRONE, {instance.condition_type for instance in mage.condition_instances})

    def test_misty_step_to_supported_surface_does_not_fall(self) -> None:
        runtime, state = self._build_state(mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'monster-mage-1')

        state, _ = ui.execute(state, '/cast monster-mage-1 misty-step 5 2 0')

        mage = state.actors['monster-mage-1']
        self.assertEqual(mage.position, GridPosition(5, 2, 0))
        self.assertEqual(mage.support_state, SupportStateType.GROUNDED)
        self.assertFalse(any(isinstance(event, FallStartedEvent) for event in state.event_log))

    def test_flying_actor_remains_aloft_after_reconciliation(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0, 10))
        actor = state.actors['player-1']
        actor.fly_speed_ft = 30

        events = runtime.kernel.reconcile_support_state(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE)

        self.assertEqual(actor.support_state, SupportStateType.FLYING)
        self.assertTrue(any(isinstance(event, SupportStateEvaluatedEvent) for event in events))
        self.assertFalse(any(isinstance(event, FallStartedEvent) for event in events))

    def test_hovering_actor_does_not_fall_when_prone_or_incapacitated(self) -> None:
        for condition_type in (ConditionType.PRONE, ConditionType.INCAPACITATED):
            with self.subTest(condition=condition_type.value):
                runtime, state = self._build_state(player_position=GridPosition(0, 0, 10))
                actor = state.actors['player-1']
                actor.fly_speed_ft = 30
                actor.hover = True
                runtime.kernel.reconcile_support_state(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE)

                runtime.kernel._apply_event(
                    state,
                    ConditionAddedEvent(
                        actor_id=actor.actor_id,
                        instance=self._condition_instance(runtime, actor.actor_id, condition_type),
                    ),
                )

                self.assertEqual(actor.position, GridPosition(0, 0, 10))
                self.assertEqual(actor.support_state, SupportStateType.HOVERING)
                self.assertFalse(any(isinstance(event, FallStartedEvent) for event in state.event_log))

    def test_flying_actor_becomes_prone_and_falls_without_hover(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0, 10))
        actor = state.actors['player-1']
        actor.fly_speed_ft = 30
        runtime.kernel.reconcile_support_state(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE)

        runtime.kernel._apply_event(
            state,
            ConditionAddedEvent(
                actor_id=actor.actor_id,
                instance=self._condition_instance(runtime, actor.actor_id, ConditionType.PRONE),
            ),
        )

        self.assertEqual(actor.position, GridPosition(0, 0, 0))
        self.assertEqual(actor.support_state, SupportStateType.GROUNDED)
        self.assertTrue(any(isinstance(event, FallStartedEvent) for event in state.event_log))

    def test_flying_actor_becomes_incapacitated_and_falls_without_hover(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0, 10))
        actor = state.actors['player-1']
        actor.fly_speed_ft = 30
        runtime.kernel.reconcile_support_state(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE)

        runtime.kernel._apply_event(
            state,
            ConditionAddedEvent(
                actor_id=actor.actor_id,
                instance=self._condition_instance(runtime, actor.actor_id, ConditionType.INCAPACITATED),
            ),
        )

        self.assertEqual(actor.position, GridPosition(0, 0, 0))
        self.assertEqual(actor.support_state, SupportStateType.GROUNDED)
        self.assertTrue(any(isinstance(event, FallStartedEvent) for event in state.event_log))

    def test_losing_fly_speed_causes_fall_without_hover(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(0, 0, 10))
        actor = state.actors['player-1']
        actor.fly_speed_ft = 30
        runtime.kernel.reconcile_support_state(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE)

        actor.fly_speed_ft = 0
        events = runtime.kernel.reconcile_support_state(state, actor_id=actor.actor_id, reason=FallReason.FLY_SPEED_ZERO)

        self.assertEqual(actor.position, GridPosition(0, 0, 0))
        self.assertEqual(actor.support_state, SupportStateType.GROUNDED)
        self.assertTrue(any(isinstance(event, FallStartedEvent) for event in events))

    def test_fall_distance_and_damage_are_deterministic(self) -> None:
        runtime_one, state_one = self._build_state(player_position=GridPosition(0, 0, 20))
        runtime_two, state_two = self._build_state(player_position=GridPosition(0, 0, 20))
        actor_one = state_one.actors['player-1']
        actor_two = state_two.actors['player-1']

        events_one = runtime_one.kernel.reconcile_support_state(state_one, actor_id=actor_one.actor_id, reason=FallReason.UNSUPPORTED_RELOCATION)
        events_two = runtime_two.kernel.reconcile_support_state(state_two, actor_id=actor_two.actor_id, reason=FallReason.UNSUPPORTED_RELOCATION)

        roll_one = next(event for event in events_one if isinstance(event, FallDamageRolledEvent))
        roll_two = next(event for event in events_two if isinstance(event, FallDamageRolledEvent))
        self.assertEqual(roll_one.distance_ft, 20)
        self.assertEqual(roll_one.damage_rolls, roll_two.damage_rolls)
        self.assertEqual(roll_one.damage_total, roll_two.damage_total)
        self.assertEqual(actor_one.position, actor_two.position)
        self.assertEqual(actor_one.current_hit_points, actor_two.current_hit_points)

    def test_teleport_still_validates_destination_range_before_fall_resolution(self) -> None:
        runtime, state = self._build_state(mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'monster-mage-1')

        with self.assertRaises(EncounterValidationError):
            ui.execute(state, '/cast monster-mage-1 misty-step 20 2 10')


if __name__ == '__main__':
    unittest.main()
