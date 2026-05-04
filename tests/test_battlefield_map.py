from __future__ import annotations

from pathlib import Path
import unittest

from encounter_runtime import build_default_encounter_runtime
from encounter_runtime.battlefield import BattlefieldRules
from player_interface.encounter_commands import EncounterSlashCommandInterface
from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from session_server.bootstrap import build_default_character_record, build_goblin_ambush_encounter_session
from shared_types.battlefield import MovementIntentMode, MovementPreviewOutcome, UnreachableReason, CoverLevel
from shared_types.encounter_intents import MoveActorIntent
from shared_types.encounter_models import CharacterPlacement, EncounterPhase, GridPosition, MonsterPlacement
from shared_types.errors import EncounterMovementPreviewError, EncounterValidationError


LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class BattlefieldMapIntegrationTests(unittest.TestCase):
    def _build_runtime(self):
        return build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def _monster_id(self, runtime, *, name: str, source: str) -> str:
        for record_id, record in runtime.encounter_catalog.monsters.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f'Monster not found: {name} [{source}]')

    def _build_state(self, *, player_position: GridPosition, skeleton_position: GridPosition, mage_position: GridPosition):
        runtime = self._build_runtime()
        record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
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

    def test_json_asset_loading_and_defaults(self) -> None:
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        self.assertEqual(battlefield.map_id, 'triboar_trail_goblin_ambush_v1')
        self.assertEqual(battlefield.name, 'Triboar Trail - Goblin Ambush')
        assert battlefield.grid is not None
        self.assertEqual((battlefield.grid.width, battlefield.grid.height, battlefield.grid.cell_size_feet), (18, 26, 5))
        self.assertEqual(set(battlefield.spawn_zones), {'players', 'goblinNorth', 'goblinSouth'})
        self.assertEqual(len(battlefield.object_ids), 2)
        self.assertEqual(len(battlefield.blocker_ids), 6)
        self.assertEqual(battlefield.default_elevation_transition_rule.threshold_feet, 10)
        self.assertEqual(battlefield.default_elevation_transition_rule.transition_type.value, 'climbable_ledge')

    def test_region_expansion_and_elevation_queries(self) -> None:
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        rules = BattlefieldRules()
        upper_tile = rules.get_tile(battlefield, 0, 0)
        road_tile = rules.get_tile(battlefield, 12, 15)
        ramp_tile = rules.get_tile(battlefield, 11, 9)
        self.assertEqual((upper_tile.terrain_id, upper_tile.elevation_ft, upper_tile.movement_cost_feet_per_5ft), ('upper_forest_dense', 10, 10))
        self.assertEqual((road_tile.terrain_id, road_tile.elevation_ft, road_tile.movement_cost_feet_per_5ft), ('lower_road', 0, 5))
        self.assertEqual((ramp_tile.terrain_id, ramp_tile.elevation_ft), ('side_path_ramp', 5))
        self.assertEqual(rules.get_height_difference(battlefield, GridPosition(10, 14), GridPosition(10, 13)), 10)
        self.assertTrue(rules.does_edge_require_climb(battlefield, GridPosition(10, 14), GridPosition(10, 13)))

    def test_same_plane_default_requires_vertical_confirmation(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(10, 14), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        preview = runtime.kernel.battlefield_rules.preview_move(state, actor, GridPosition(10, 13), movement_intent_mode=MovementIntentMode.SAME_PLANE)
        self.assertEqual(preview.outcome, MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION)
        self.assertEqual(preview.unreachable_reason, UnreachableReason.REQUIRES_VERTICAL_CONFIRMATION)
        self.assertFalse(preview.requires_climb)
        self.assertEqual(preview.target_elevation_ft, 10)
        self.assertIsNotNone(preview.suggested_plan)

    def test_explicit_climb_makes_embankment_reachable(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(10, 14), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        rules = BattlefieldRules()
        self.assertFalse(rules.can_move_between_cells(state, actor, GridPosition(10, 14), GridPosition(10, 13), movement_intent_mode=MovementIntentMode.SAME_PLANE))
        self.assertTrue(rules.can_move_between_cells(state, actor, GridPosition(10, 14), GridPosition(10, 13), movement_intent_mode=MovementIntentMode.ALLOW_CLIMB))
        preview = rules.preview_move(state, actor, GridPosition(10, 13), movement_intent_mode=MovementIntentMode.ALLOW_CLIMB)
        self.assertEqual(preview.outcome, MovementPreviewOutcome.REACHABLE_WITH_CLIMB)
        self.assertEqual(preview.total_cost_ft, 20)
        self.assertTrue(preview.requires_climb)

    def test_ramp_override_supports_slope_preview_and_execution(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(11, 8), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        rules = BattlefieldRules()
        same_plane_preview = rules.preview_move(state, actor, GridPosition(11, 9), movement_intent_mode=MovementIntentMode.SAME_PLANE)
        self.assertEqual(same_plane_preview.outcome, MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION)
        slope_preview = rules.preview_move(state, actor, GridPosition(11, 9), movement_intent_mode=MovementIntentMode.ALLOW_ELEVATION)
        self.assertEqual(slope_preview.outcome, MovementPreviewOutcome.REACHABLE_WITH_SLOPE)
        self.assertEqual(slope_preview.total_cost_ft, 15)
        self.assertFalse(slope_preview.requires_climb)

    def test_implicit_five_foot_vertical_edge_is_impassable_without_override(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(10, 10), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        rules = BattlefieldRules()
        can_traverse, reason, segment = rules.can_traverse_edge(state, actor, GridPosition(10, 10), GridPosition(11, 10), movement_intent_mode=MovementIntentMode.ALLOW_CLIMB)
        self.assertFalse(can_traverse)
        self.assertEqual(reason, UnreachableReason.IMPASSABLE_EDGE)
        self.assertIsNone(segment)

    def test_climb_speed_reduces_climb_transition_cost(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(10, 14), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        rules = BattlefieldRules()
        normal_preview = rules.preview_move(state, actor, GridPosition(10, 13), movement_intent_mode=MovementIntentMode.ALLOW_CLIMB)
        actor.climb_speed_ft = 20
        climb_speed_preview = rules.preview_move(state, actor, GridPosition(10, 13), movement_intent_mode=MovementIntentMode.ALLOW_CLIMB)
        self.assertEqual(normal_preview.total_cost_ft, 20)
        self.assertEqual(climb_speed_preview.total_cost_ft, 10)
        self.assertEqual(climb_speed_preview.outcome, MovementPreviewOutcome.REACHABLE_WITH_CLIMB)

    def test_deterministic_preview_path_output(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(11, 8), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        first = runtime.kernel.battlefield_rules.preview_move(state, actor, GridPosition(12, 11), movement_intent_mode=MovementIntentMode.ALLOW_ELEVATION)
        second = runtime.kernel.battlefield_rules.preview_move(state, actor, GridPosition(12, 11), movement_intent_mode=MovementIntentMode.ALLOW_ELEVATION)
        self.assertEqual(first.outcome, MovementPreviewOutcome.REACHABLE_WITH_SLOPE)
        self.assertEqual(first.total_cost_ft, second.total_cost_ft)
        self.assertEqual(first.plan.path, second.plan.path)

    def test_move_intent_and_climb_command_parse_modes(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(10, 14), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        commands = EncounterSlashCommandInterface(runtime.kernel)
        self.assertEqual(commands.parse_command('/move player-1 10 13').movement_intent_mode, MovementIntentMode.SAME_PLANE)
        self.assertEqual(commands.parse_command('/move player-1 11 9 --allow-elevation').movement_intent_mode, MovementIntentMode.ALLOW_ELEVATION)
        self.assertEqual(commands.parse_command('/climb player-1 10 13').movement_intent_mode, MovementIntentMode.ALLOW_CLIMB)

    def test_kernel_raises_typed_preview_error_for_default_move(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(10, 14), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        state.phase = EncounterPhase.IN_PROGRESS
        state.initiative_order = ('player-1', 'monster-skeleton-1', 'monster-mage-1')
        state.active_actor_id = 'player-1'
        with self.assertRaises(EncounterMovementPreviewError) as ctx:
            runtime.kernel.dispatch(state, MoveActorIntent(actor_id='player-1', x=10, y=13))
        self.assertEqual(ctx.exception.preview.outcome, MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION)

    def test_dead_horse_and_tree_blockers_overlay_runtime_tiles(self) -> None:
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        rules = BattlefieldRules()
        dead_horse_tile = rules.get_tile(battlefield, 11, 15)
        tree_tile = rules.get_tile(battlefield, 1, 5)
        self.assertFalse(dead_horse_tile.traversable)
        self.assertFalse(dead_horse_tile.occupiable)
        self.assertEqual(dead_horse_tile.base_cover, CoverLevel.HALF)
        self.assertIn('dead_horse_1', dead_horse_tile.object_ids)
        self.assertFalse(tree_tile.traversable)
        self.assertFalse(tree_tile.occupiable)
        self.assertEqual(tree_tile.base_cover, CoverLevel.TOTAL)
        self.assertIn('north_tree_cluster_west', tree_tile.blocker_ids)
        tree_feature = battlefield.features['north_tree_cluster_west']
        self.assertTrue(tree_feature.blocks_los)
        self.assertTrue(tree_feature.blocks_loe)
        self.assertGreater(tree_feature.top_ft, tree_feature.bottom_ft)

    def test_los_loe_and_cover_use_authored_map(self) -> None:
        _, blocked_state = self._build_state(player_position=GridPosition(0, 5), skeleton_position=GridPosition(4, 5), mage_position=GridPosition(8, 20))
        rules = BattlefieldRules()
        self.assertFalse(rules.has_line_of_sight(blocked_state, blocked_state.actors['monster-skeleton-1'], blocked_state.actors['player-1']))
        self.assertFalse(rules.has_line_of_effect(blocked_state, blocked_state.actors['monster-skeleton-1'], blocked_state.actors['player-1']))
        with self.assertRaises(EncounterValidationError):
            rules.attack_legality(blocked_state, blocked_state.actors['monster-skeleton-1'], blocked_state.actors['player-1'], blocked_state.actors['monster-skeleton-1'].attacks['shortbow'])

        _, cover_state = self._build_state(player_position=GridPosition(13, 16), skeleton_position=GridPosition(10, 16), mage_position=GridPosition(8, 20))
        cover = rules.get_cover(cover_state, cover_state.actors['monster-skeleton-1'], cover_state.actors['player-1'])
        self.assertEqual(cover, CoverLevel.HALF)


    def test_flying_movement_supports_airspace_above_road(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(12, 15), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(8, 20))
        actor = state.actors['player-1']
        actor.fly_speed_ft = 30
        preview = runtime.kernel.battlefield_rules.preview_move(state, actor, GridPosition(12, 15, 10), movement_intent_mode=MovementIntentMode.ALLOW_FLY)
        self.assertEqual(preview.outcome, MovementPreviewOutcome.REACHABLE_WITH_FLY)
        self.assertEqual(preview.target_elevation_ft, 10)

    def test_tree_volume_blocks_low_airspace_but_not_high_airspace(self) -> None:
        _, low_state = self._build_state(player_position=GridPosition(0, 5, 10), skeleton_position=GridPosition(4, 5, 10), mage_position=GridPosition(8, 20))
        rules = BattlefieldRules()
        self.assertFalse(rules.has_line_of_sight(low_state, low_state.actors['monster-skeleton-1'], low_state.actors['player-1']))
        _, high_state = self._build_state(player_position=GridPosition(0, 5, 30), skeleton_position=GridPosition(4, 5, 30), mage_position=GridPosition(8, 20))
        self.assertTrue(rules.has_line_of_sight(high_state, high_state.actors['monster-skeleton-1'], high_state.actors['player-1']))

    def test_vertical_separation_can_trigger_leaving_reach(self) -> None:
        _, state = self._build_state(player_position=GridPosition(1, 15, 0), skeleton_position=GridPosition(0, 15, 0), mage_position=GridPosition(8, 20))
        rules = BattlefieldRules()
        triggered = rules.detect_leaving_reach_triggers(state.actors['monster-skeleton-1'], from_position=GridPosition(1, 15, 0), path=(GridPosition(1, 15, 10),), reach_ft=5)
        self.assertTrue(triggered)

    def test_public_battlefield_sync_integration_uses_authored_map(self) -> None:
        session = build_goblin_ambush_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)
        session.system_execute('/encounter start')
        dm_view = '\n'.join(session.view_for_controller('dm').summary_lines)
        player_view = '\n'.join(session.view_for_controller('player-1-controller').summary_lines)
        self.assertIn('Battlefield: Triboar Trail - Goblin Ambush', dm_view)
        self.assertIn('Battlefield: Triboar Trail - Goblin Ambush', player_view)
        self.assertIn('Tile lower_road @ 0 ft', dm_view)
        self.assertIn('Tile lower_road @ 0 ft', player_view)

    def test_teleport_ignores_path_cost_and_embankment_traversal(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(16, 20), skeleton_position=GridPosition(4, 10), mage_position=GridPosition(10, 14))
        actor = state.actors['monster-mage-1']
        actor.remaining_movement_ft = 0
        actor.movement_spent_ft = actor.max_path_speed_ft
        legality = runtime.kernel.battlefield_rules.teleport_legality(
            state,
            actor,
            GridPosition(10, 13, 10),
            range_ft=30,
            requires_visible_destination=True,
            requires_unoccupied_destination=True,
        )
        self.assertTrue(legality.destination_legal)
        self.assertEqual(legality.movement_cost_ft, 0)
        self.assertEqual(legality.distance_ft, 10)

    def test_teleport_visibility_requirement_uses_authored_map_los(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(16, 20), skeleton_position=GridPosition(10, 10), mage_position=GridPosition(4, 5))
        actor = state.actors['monster-mage-1']
        legality = runtime.kernel.battlefield_rules.teleport_legality(
            state,
            actor,
            GridPosition(0, 5, 10),
            range_ft=30,
            requires_visible_destination=True,
            requires_unoccupied_destination=True,
        )
        self.assertFalse(legality.destination_visible)
        self.assertFalse(legality.destination_legal)



if __name__ == '__main__':
    unittest.main()

