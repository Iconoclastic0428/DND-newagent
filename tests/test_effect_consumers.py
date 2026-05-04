from __future__ import annotations

from pathlib import Path
import copy
import unittest

from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface
from session_server.bootstrap import build_default_character_record
from shared_types.battlefield import BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, FallReason, TraversalMode
from shared_types.conditions import ConditionType
from shared_types.effects import (
    CheckRequest,
    ConditionApplication,
    DamageEffect,
    DisplacementVector,
    EffectOutcome,
    EffectResolutionBranch,
    ForcedMovementEffect,
    ForcedMovementMode,
    ForcedMovementStopReason,
    HazardResolutionRequest,
    LiquidEntryMitigationChoice,
    ResolutionContext,
    SaveRequest,
)
from shared_types.encounter_events import (
    CheckRequestedEvent,
    FallMitigationCheckResolvedEvent,
    ForcedMovementStartedEvent,
    ForcedMovementStoppedEvent,
    HazardTriggeredEvent,
    LiquidEntryDetectedEvent,
    SaveRequestedEvent,
)
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from shared_types.models import Ability
from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from session_server.bootstrap import build_default_encounter_session

LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class EffectConsumerTests(unittest.TestCase):
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
        player_position: GridPosition = GridPosition(1, 0, 0),
        skeleton_position: GridPosition = GridPosition(0, 0, 0),
        mage_position: GridPosition = GridPosition(8, 2, 0),
        battlefield=None,
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
            battlefield=battlefield,
        )
        return runtime, state

    def _context(self, *, effect_id: str, target_actor_id: str, source_actor_id: str | None = None, reason: str) -> ResolutionContext:
        return ResolutionContext(effect_id=effect_id, source_actor_id=source_actor_id, target_actor_id=target_actor_id, reason=reason)

    def _water_battlefield(self) -> BattlefieldState:
        tile = BattlefieldTile(
            position=GridPosition(0, 0),
            terrain_id='water_pool',
            elevation_ft=0,
            ceiling_ft=40,
            traversable=True,
            occupiable=True,
            movement_cost_feet_per_5ft=5,
            difficult_terrain=False,
            lightly_obscured=False,
            blocks_los=False,
            blocks_loe=False,
            base_cover=CoverLevel.NONE,
            supported_modes=(TraversalMode.SWIM, TraversalMode.FLY),
            tags=('water', 'liquid'),
        )
        return BattlefieldState(
            map_id='test-water',
            name='Test Water',
            grid=BattlefieldGridSpec(
                cell_size_feet=5,
                width=1,
                height=1,
                origin='top-left',
                coordinates='xy',
                min_x=0,
                min_y=0,
                max_x=0,
                max_y=0,
            ),
            tiles={GridPosition(0, 0): tile},
        )

    def test_generic_save_consumer_emits_typed_events_and_partial_success_branch(self) -> None:
        runtime, state = self._build_state()
        preview = runtime.kernel.resolve_saving_throw(state, actor_id='player-1', ability=Ability.DEX, dc=10)
        dc = preview.result.total + 1
        request = SaveRequest(
            context=self._context(effect_id='partial-save', target_actor_id='player-1', reason='test save'),
            ability=Ability.DEX,
            dc=dc,
            partial_success_margin=1,
        )
        resolution, events = runtime.kernel.resolve_save_consumer(state, request, apply=True)
        self.assertEqual(resolution.branch, EffectResolutionBranch.PARTIAL_SUCCESS)
        self.assertTrue(any(isinstance(event, SaveRequestedEvent) for event in events))
        self.assertTrue(any(type(event).__name__ == 'SaveRolledEvent' for event in events))

    def test_generic_check_consumer_emits_typed_events(self) -> None:
        runtime, state = self._build_state()
        request = CheckRequest(
            context=self._context(effect_id='wis-check', target_actor_id='player-1', reason='test check'),
            ability=Ability.WIS,
            dc=5,
            skill_name='Perception',
        )
        resolution, events = runtime.kernel.resolve_check_consumer(state, request, apply=True)
        self.assertIn(resolution.branch, {EffectResolutionBranch.SUCCESS, EffectResolutionBranch.FAILURE})
        self.assertTrue(any(isinstance(event, CheckRequestedEvent) for event in events))
        self.assertTrue(any(type(event).__name__ == 'CheckRolledEvent' for event in events))

    def test_save_based_push_effect_repositions_target(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(1, 0, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        request = HazardResolutionRequest(
            context=self._context(effect_id='push-hazard', source_actor_id='monster-skeleton-1', target_actor_id='player-1', reason='save-based push'),
            save_request=SaveRequest(
                context=self._context(effect_id='push-hazard', source_actor_id='monster-skeleton-1', target_actor_id='player-1', reason='save-based push'),
                ability=Ability.STR,
                dc=99,
            ),
            failure_outcome=EffectOutcome(
                forced_movement=ForcedMovementEffect(
                    context=self._context(effect_id='push-hazard', source_actor_id='monster-skeleton-1', target_actor_id='player-1', reason='save-based push'),
                    mode=ForcedMovementMode.PUSH,
                    distance_ft=10,
                )
            ),
        )
        result, events = runtime.kernel.resolve_hazard(state, request, apply=True)
        self.assertEqual(state.actors['player-1'].position, GridPosition(3, 0, 0))
        self.assertIsNotNone(result.forced_movement_result)
        assert result.forced_movement_result is not None
        self.assertEqual(result.forced_movement_result.stop_reason, ForcedMovementStopReason.COMPLETED)
        self.assertTrue(any(isinstance(event, ForcedMovementStartedEvent) for event in events))
        self.assertTrue(any(isinstance(event, ForcedMovementStoppedEvent) for event in events))

    def test_forced_movement_blocked_by_occupied_space(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(1, 0, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(2, 0, 0))
        effect = ForcedMovementEffect(
            context=self._context(effect_id='blocked-push', source_actor_id='monster-skeleton-1', target_actor_id='player-1', reason='blocked push'),
            mode=ForcedMovementMode.PUSH,
            distance_ft=10,
        )
        result, _ = runtime.kernel.apply_forced_movement(state, effect)
        self.assertEqual(result.stop_reason, ForcedMovementStopReason.BLOCKED_OCCUPANCY)
        self.assertEqual(result.moved_distance_ft, 0)
        self.assertEqual(state.actors['player-1'].position, GridPosition(1, 0, 0))

    def test_forced_movement_over_ledge_causes_fall(self) -> None:
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        runtime, state = self._build_state(
            player_position=GridPosition(10, 13, 10),
            skeleton_position=GridPosition(10, 12, 10),
            mage_position=GridPosition(8, 20, 0),
            battlefield=battlefield,
        )
        effect = ForcedMovementEffect(
            context=self._context(effect_id='ledge-push', source_actor_id='monster-skeleton-1', target_actor_id='player-1', reason='ledge push'),
            mode=ForcedMovementMode.PUSH,
            distance_ft=5,
        )
        result, events = runtime.kernel.apply_forced_movement(state, effect)
        self.assertTrue(result.caused_fall)
        self.assertEqual(state.actors['player-1'].position, GridPosition(10, 14, 0))
        self.assertTrue(any(type(event).__name__ == 'FallStartedEvent' for event in events))

    def test_hazard_triggered_check_failure_can_apply_condition(self) -> None:
        runtime, state = self._build_state()
        request = HazardResolutionRequest(
            context=self._context(effect_id='study-trap', target_actor_id='player-1', reason='hazard check'),
            check_request=CheckRequest(
                context=self._context(effect_id='study-trap', target_actor_id='player-1', reason='hazard check'),
                ability=Ability.WIS,
                dc=99,
                skill_name='Perception',
            ),
            failure_outcome=EffectOutcome(
                conditions=(ConditionApplication(condition_type=ConditionType.PRONE, source_label='study-trap'),),
            ),
        )
        result, events = runtime.kernel.resolve_hazard(state, request, apply=True)
        self.assertEqual(result.branch, EffectResolutionBranch.FAILURE)
        self.assertIn(ConditionType.PRONE, {instance.condition_type for instance in state.actors['player-1'].condition_instances})
        self.assertTrue(any(isinstance(event, HazardTriggeredEvent) for event in events))

    def test_falling_into_water_mitigation_halves_damage_on_success(self) -> None:
        battlefield = self._water_battlefield()
        runtime_one, state_one = self._build_state(player_position=GridPosition(0, 0, 20), skeleton_position=GridPosition(20, 0, 0), mage_position=GridPosition(20, 2, 0), battlefield=battlefield)
        runtime_two, state_two = self._build_state(player_position=GridPosition(0, 0, 20), skeleton_position=GridPosition(20, 0, 0), mage_position=GridPosition(20, 2, 0), battlefield=copy.deepcopy(battlefield))

        events_fail = runtime_one.kernel.reconcile_support_state(state_one, actor_id='player-1', reason=FallReason.UNSUPPORTED_RELOCATION)
        events_success = runtime_two.kernel.reconcile_support_state(
            state_two,
            actor_id='player-1',
            reason=FallReason.UNSUPPORTED_RELOCATION,
            liquid_choice=LiquidEntryMitigationChoice(attempt=True, ability=Ability.DEX, skill_name='Acrobatics', dc=1),
        )
        mitigation_event = next(event for event in events_success if isinstance(event, FallMitigationCheckResolvedEvent))
        self.assertTrue(mitigation_event.resolution.success)
        self.assertTrue(any(isinstance(event, LiquidEntryDetectedEvent) for event in events_success))
        self.assertGreater(state_two.actors['player-1'].current_hit_points, state_one.actors['player-1'].current_hit_points)

    def test_sync_safe_state_transitions_reflect_forced_movement_publicly(self) -> None:
        session = build_default_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)
        session.system_execute('/encounter start')
        effect = ForcedMovementEffect(
            context=self._context(effect_id='sync-push', source_actor_id='monster-skeleton-1', target_actor_id='player-1', reason='sync push'),
            mode=ForcedMovementMode.REPOSITION,
            distance_ft=15,
            destination=GridPosition(3, 0, 0),
        )
        session.command_interface.kernel.apply_forced_movement(session.state, effect)
        dm_view = '\n'.join(session.view_for_controller('dm').summary_lines)
        player_view = '\n'.join(session.view_for_controller('player-1-controller').summary_lines)
        self.assertIn('player-1: PC level-1-character [player] Pos (3,0,0); Status active', dm_view)
        self.assertIn('player-1: PC level-1-character [player] HP 7/7; Temp 0; AC 12; Pos (3,0,0); Move 30; Action yes; Bonus yes; Reaction yes', player_view)


if __name__ == '__main__':
    unittest.main()
