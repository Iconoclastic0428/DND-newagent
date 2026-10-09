from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import unittest

from encounter_runtime.battlefield import BattlefieldRules
from rules_engine.battlefield_loader import load_battlefield_state_from_json
from shared_types.battlefield import (
    BattlefieldGridSpec,
    BattlefieldState,
    BattlefieldTile,
    CoverLevel,
    EdgeTransitionType,
    EdgeTraversalRequirement,
    LightingLevel,
    MovementIntentMode,
    ObscurementLevel,
    TraversalMode,
)
from shared_types.encounter_models import GridPosition


REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

CRAGMAW_MAP_PATH = REPO_ROOT / 'data' / 'maps' / 'cragmaw_hideout_map.json'
LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class CragmawHideoutMapTests(unittest.TestCase):
    def test_cragmaw_hideout_asset_uses_player_map_grid_metadata(self) -> None:
        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)

        self.assertEqual(battlefield.map_id, 'cragmaw_hideout_player_v1')
        self.assertEqual(battlefield.name, 'Cragmaw Hideout')
        self.assertIsNotNone(battlefield.grid)
        assert battlefield.grid is not None
        self.assertEqual((battlefield.grid.width, battlefield.grid.height), (30, 21))
        self.assertEqual(battlefield.grid.cell_size_feet, 5)
        self.assertEqual((battlefield.grid.min_x, battlefield.grid.min_y), (0, 0))
        self.assertEqual((battlefield.grid.max_x, battlefield.grid.max_y), (29, 20))

        image = battlefield.background_image
        self.assertIsNotNone(image)
        assert image is not None
        self.assertEqual(image.url, 'assets/maps/cragmaw-hideout-player.webp')
        self.assertEqual((image.width_px, image.height_px), (4500, 3136))
        self.assertEqual(image.grid_type, 'square')
        self.assertEqual(image.grid_size_px, 150)
        self.assertEqual((image.grid_offset_x_px, image.grid_offset_y_px), (-4, -7))
        self.assertEqual(image.source_internal_path, 'adventure/LMoP/Cragmaw Hideout (Player).webp')

    def test_cragmaw_hideout_map_has_authored_elevation_and_wall_cells(self) -> None:
        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        self.assertTrue(battlefield.has_authored_map)
        self.assertTrue(any(tile.elevation_ft > 0 for tile in battlefield.tiles.values()))

        rules = BattlefieldRules()
        cave_floor = rules.get_tile(battlefield, 13, 17)
        rock_wall = rules.get_tile(battlefield, 0, 0)
        self.assertTrue(cave_floor.traversable)
        self.assertTrue(cave_floor.occupiable)
        self.assertFalse(cave_floor.blocks_los)
        self.assertFalse(rock_wall.traversable)
        self.assertFalse(rock_wall.occupiable)
        self.assertTrue(rock_wall.blocks_los)
        self.assertTrue(rock_wall.blocks_loe)
        self.assertEqual(rock_wall.base_cover, CoverLevel.TOTAL)

    def test_cragmaw_stream_water_is_traversable_difficult_terrain(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        for x, y in ((10, 17), (10, 18), (10, 19)):
            water = rules.get_tile(battlefield, x, y)
            self.assertEqual(water.terrain_id, 'stream_water')
            self.assertTrue(water.traversable)
            self.assertTrue(water.occupiable)
            self.assertTrue(water.difficult_terrain)
            self.assertEqual(water.movement_cost_feet_per_5ft, 10)
            self.assertFalse(water.blocks_los)
            self.assertFalse(water.blocks_loe)

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        preview = session.runtime_services.kernel.battlefield_rules.preview_move(
            session.state,
            session.state.actors['player-1'],
            GridPosition(10, 17, 0),
            movement_intent_mode=MovementIntentMode.SAME_PLANE,
        )
        self.assertEqual(preview.outcome.value, 'reachable_same_plane')
        self.assertEqual(preview.total_cost_ft, 30)

    def test_cragmaw_visible_water_is_passable_difficult_terrain(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        visible_water_cells = (
            (17, 3),
            (18, 3),
            (19, 3),
            (20, 3),
            (23, 3),
            (24, 3),
            (16, 4),
            (17, 4),
            (18, 4),
            (19, 4),
            (20, 4),
            (21, 4),
            (22, 4),
            (23, 4),
            (24, 4),
            (25, 4),
            (14, 5),
            (22, 5),
            (23, 5),
            (24, 5),
            (25, 5),
            (26, 5),
            (13, 6),
            (14, 6),
            (22, 6),
            (23, 6),
            (24, 6),
            (25, 6),
            (26, 6),
            (27, 6),
            (12, 7),
            (13, 7),
            (24, 7),
            (25, 7),
            (26, 7),
            (27, 7),
            (12, 8),
            (26, 8),
            (27, 8),
            (12, 9),
            (12, 10),
            (12, 11),
            (12, 12),
            (12, 13),
            (11, 14),
            (12, 14),
            (10, 15),
            (11, 15),
            (10, 16),
            (11, 16),
            (10, 17),
            (11, 17),
            (10, 18),
            (11, 18),
            (10, 19),
            (11, 19),
            (10, 20),
            (11, 20),
        )
        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        for x, y in visible_water_cells:
            water = rules.get_tile(battlefield, x, y)
            self.assertEqual(water.terrain_id, 'stream_water', (x, y))
            self.assertTrue(water.traversable, (x, y))
            self.assertTrue(water.occupiable, (x, y))
            self.assertTrue(water.difficult_terrain, (x, y))
            self.assertEqual(water.movement_cost_feet_per_5ft, 10, (x, y))
            self.assertFalse(water.blocks_los, (x, y))
            self.assertFalse(water.blocks_loe, (x, y))

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        for destination in (
            GridPosition(12, 10, 0),
            GridPosition(14, 5, 0),
            GridPosition(24, 6, 0),
            GridPosition(10, 15, 0),
            GridPosition(10, 16, 0),
            GridPosition(10, 20, 0),
            GridPosition(11, 20, 0),
        ):
            preview = session.runtime_services.kernel.battlefield_rules.preview_move(
                session.state,
                session.state.actors['player-1'],
                destination,
                movement_intent_mode=MovementIntentMode.SAME_PLANE,
            )
            self.assertEqual(preview.outcome.value, 'reachable_same_plane', destination)
            assert preview.total_cost_ft is not None
            self.assertGreater(preview.total_cost_ft, 5)

    def test_cragmaw_tree_cells_are_passable_difficult_terrain(self) -> None:
        tree_cells = (
            (6, 14),
            (7, 14),
            (8, 14),
            (9, 14),
            (6, 15),
            (12, 15),
            (12, 16),
            (12, 17),
            (12, 18),
            (12, 19),
        )
        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        for x, y in tree_cells:
            tree = rules.get_tile(battlefield, x, y)
            self.assertEqual(tree.terrain_id, 'briars', (x, y))
            self.assertTrue(tree.traversable, (x, y))
            self.assertTrue(tree.occupiable, (x, y))
            self.assertTrue(tree.difficult_terrain, (x, y))
            self.assertEqual(tree.movement_cost_feet_per_5ft, 10, (x, y))
            self.assertTrue(tree.lightly_obscured, (x, y))
            self.assertFalse(tree.blocks_los, (x, y))
            self.assertFalse(tree.blocks_loe, (x, y))

    def test_cragmaw_lower_river_cells_are_reachable_by_move_command(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        actor = session.state.actors['player-1']
        actor.position = GridPosition(11, 18, 0)
        actor.remaining_movement_ft = 100
        actor.movement_spent_ft = 0

        for command, expected_position in (
            ('/move player-1 11 19', GridPosition(11, 19, 0)),
            ('/move player-1 11 20', GridPosition(11, 20, 0)),
        ):
            session.state, message = session.command_interface.execute(session.state, command)
            self.assertFalse(message.startswith('Error'), message)
            self.assertEqual(session.state.actors['player-1'].position, expected_position)

    def test_cragmaw_partial_water_wall_uses_edge_blocker_not_cell_los(self) -> None:
        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()

        mixed_cell = rules.get_tile(battlefield, 21, 4)
        self.assertEqual(mixed_cell.terrain_id, 'stream_water')
        self.assertTrue(mixed_cell.traversable)
        self.assertTrue(mixed_cell.occupiable)
        self.assertFalse(mixed_cell.blocks_los)
        self.assertFalse(mixed_cell.blocks_loe)

        left_edge = rules.get_edge_transition(battlefield, GridPosition(21, 4), GridPosition(20, 4))
        right_edge = rules.get_edge_transition(battlefield, GridPosition(21, 4), GridPosition(22, 4))
        south_edge = rules.get_edge_transition(battlefield, GridPosition(21, 4), GridPosition(21, 5))
        self.assertEqual(left_edge.transition_type, EdgeTransitionType.FLAT)
        self.assertEqual(left_edge.traversal_requirement, EdgeTraversalRequirement.NONE)
        self.assertEqual(right_edge.transition_type, EdgeTransitionType.FLAT)
        self.assertEqual(right_edge.traversal_requirement, EdgeTraversalRequirement.NONE)
        self.assertEqual(south_edge.transition_type, EdgeTransitionType.BLOCKED)
        self.assertEqual(south_edge.traversal_requirement, EdgeTraversalRequirement.BLOCKED)
        self.assertFalse(south_edge.blocks_los)
        self.assertFalse(south_edge.blocks_loe)

    def test_cragmaw_implicit_3d_structure_authors_elevations_and_under_bridge_passability(self) -> None:
        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()

        expected_elevations = {
            (13, 9): 0,
            (14, 8): 5,
            (15, 7): 10,
            (16, 6): 15,
            (17, 6): 20,
            (20, 5): 20,
            (23, 10): 20,
            (24, 10): 25,
            (24, 11): 30,
        }
        for coordinate, elevation_ft in expected_elevations.items():
            tile = rules.get_tile(battlefield, *coordinate)
            self.assertEqual(tile.terrain_id, 'cave_floor', coordinate)
            self.assertTrue(tile.traversable, coordinate)
            self.assertTrue(tile.occupiable, coordinate)
            self.assertEqual(tile.elevation_ft, elevation_ft, coordinate)

        for coordinate in ((15, 4), (16, 4), (15, 5), (16, 5)):
            tile = rules.get_tile(battlefield, *coordinate)
            self.assertTrue(tile.traversable, coordinate)
            self.assertTrue(tile.occupiable, coordinate)
            self.assertEqual(tile.elevation_ft, 10, coordinate)
            self.assertFalse(tile.blocks_los, coordinate)
            self.assertFalse(tile.blocks_loe, coordinate)

        bridge = battlefield.features.get('cragmaw_hideout_bridge_deck')
        self.assertIsNotNone(bridge)
        assert bridge is not None
        self.assertEqual(bridge.feature_type, 'bridge')
        self.assertEqual(bridge.bottom_ft, 15)
        self.assertEqual(bridge.top_ft, 20)
        self.assertTrue(bridge.traversable)
        self.assertTrue(bridge.occupiable)
        self.assertFalse(bridge.blocks_los)
        self.assertFalse(bridge.blocks_loe)
        self.assertEqual({(cell.x, cell.y) for cell in bridge.cells}, {(15, 4), (16, 4), (15, 5), (16, 5)})

    def test_cragmaw_gradual_elevation_edges_allow_plain_move_without_confirmation(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        rules = session.runtime_services.kernel.battlefield_rules
        actor = session.state.actors['player-1']
        actor.position = GridPosition(13, 9, 0)
        actor.remaining_movement_ft = 80
        actor.movement_spent_ft = 0

        left_stair_preview = rules.preview_move(
            session.state,
            actor,
            GridPosition(20, 5, 0),
            movement_intent_mode=MovementIntentMode.SAME_PLANE,
        )
        self.assertEqual(left_stair_preview.outcome.value, 'reachable_same_plane')
        self.assertEqual(left_stair_preview.target_elevation_ft, 20)
        self.assertFalse(left_stair_preview.requires_climb)
        self.assertTrue(left_stair_preview.plan)
        assert left_stair_preview.plan is not None
        self.assertTrue(left_stair_preview.plan.includes_elevation_change)

        session.state, _ = session.command_interface.execute(session.state, '/move player-1 20 5')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(20, 5, 20))

        actor = session.state.actors['player-1']
        actor.position = GridPosition(23, 10, 20)
        actor.remaining_movement_ft = 30
        actor.movement_spent_ft = 0
        right_stair_preview = rules.preview_move(
            session.state,
            actor,
            GridPosition(24, 11, 20),
            movement_intent_mode=MovementIntentMode.SAME_PLANE,
        )
        self.assertEqual(right_stair_preview.outcome.value, 'reachable_same_plane')
        self.assertEqual(right_stair_preview.target_elevation_ft, 30)
        self.assertFalse(right_stair_preview.requires_climb)

        session.state, _ = session.command_interface.execute(session.state, '/move player-1 24 11')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(24, 11, 30))

    def test_cragmaw_bridge_entrance_20_7_supports_lower_and_upper_surfaces(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        lower_entrance = rules.get_tile(battlefield, 20, 7)
        self.assertEqual(lower_entrance.terrain_id, 'cave_floor')
        self.assertTrue(lower_entrance.traversable)
        self.assertTrue(lower_entrance.occupiable)
        self.assertEqual(lower_entrance.elevation_ft, 0)

        upper_entrance = battlefield.features.get('cragmaw_hideout_bridge_approach_20_7')
        self.assertIsNotNone(upper_entrance)
        assert upper_entrance is not None
        self.assertEqual({(cell.x, cell.y) for cell in upper_entrance.cells}, {(20, 7)})
        self.assertTrue(upper_entrance.traversable)
        self.assertTrue(upper_entrance.occupiable)
        self.assertEqual(upper_entrance.top_ft, 20)

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        actor = session.state.actors['player-1']

        actor.position = GridPosition(21, 7, 0)
        actor.remaining_movement_ft = 30
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 20 7')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(20, 7, 0))

        actor = session.state.actors['player-1']
        actor.position = GridPosition(21, 8, 0)
        actor.remaining_movement_ft = 30
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 20 7')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(20, 7, 0))

        actor = session.state.actors['player-1']
        actor.position = GridPosition(20, 6, 20)
        actor.remaining_movement_ft = 30
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 20 7')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(20, 7, 20))

        actor = session.state.actors['player-1']
        actor.remaining_movement_ft = 30
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 20 6')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(20, 6, 20))

    def test_cragmaw_upper_tunnel_bridge_run_is_passable_at_20ft(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        for position in (
            GridPosition(19, 7, 20),
            GridPosition(18, 7, 20),
            GridPosition(17, 6, 20),
            GridPosition(16, 5, 20),
            GridPosition(15, 4, 20),
        ):
            self.assertIn(
                position,
                rules.supported_surface_positions(battlefield, position.x, position.y),
                position,
            )

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        actor = session.state.actors['player-1']
        actor.position = GridPosition(20, 7, 20)
        actor.remaining_movement_ft = 100
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 19 7')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(19, 7, 20))

        actor = session.state.actors['player-1']
        actor.position = GridPosition(20, 7, 20)
        actor.remaining_movement_ft = 100
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 19 7 20')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(19, 7, 20))

        for command, expected in (
            ('/move player-1 18 7', GridPosition(18, 7, 20)),
            ('/move player-1 17 6', GridPosition(17, 6, 20)),
            ('/move player-1 16 5', GridPosition(16, 5, 20)),
            ('/move player-1 15 4', GridPosition(15, 4, 20)),
        ):
            actor = session.state.actors['player-1']
            actor.remaining_movement_ft = 100
            actor.movement_spent_ft = 0
            session.state, _ = session.command_interface.execute(session.state, command)
            self.assertEqual(session.state.actors['player-1'].position, expected, command)

    def test_cragmaw_explicit_under_bridge_heights_resolve_to_supported_surface(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        rules = session.runtime_services.kernel.battlefield_rules
        actor = session.state.actors['player-1']

        self.assertEqual(
            rules.supported_surface_positions(session.state.battlefield, 16, 5),
            (GridPosition(16, 5, 10), GridPosition(16, 5, 20)),
        )

        actor.position = GridPosition(17, 6, 20)
        actor.remaining_movement_ft = 100
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 16 5 20')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(16, 5, 20))

        actor = session.state.actors['player-1']
        actor.remaining_movement_ft = 100
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 16 5 10')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(16, 5, 10))

        for command in ('/move player-1 16 5 0', '/move player-1 16 5 -10'):
            session.state.actors['player-1'].remaining_movement_ft = 100
            session.state.actors['player-1'].movement_spent_ft = 0
            session.state, _ = session.command_interface.execute(session.state, command)
            self.assertEqual(session.state.actors['player-1'].position, GridPosition(16, 5, 10), command)

        actor = session.state.actors['player-1']
        actor.remaining_movement_ft = 100
        actor.movement_spent_ft = 0
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 16 5 20')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(16, 5, 20))

        for command in ('/move player-1 16 5 0', '/move player-1 16 5 -10'):
            actor = session.state.actors['player-1']
            actor.position = GridPosition(16, 5, 20)
            actor.remaining_movement_ft = 100
            actor.movement_spent_ft = 0
            session.state, _ = session.command_interface.execute(session.state, command)
            self.assertEqual(session.state.actors['player-1'].position, GridPosition(16, 5, 10), command)

    def test_cragmaw_steep_cliff_is_climbable_and_blocks_los_across_edge(self) -> None:
        from encounter_runtime.vision import compute_actor_grid_vision
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        for x in (18, 19, 20):
            upper = rules.get_tile(battlefield, x, 12)
            lower = rules.get_tile(battlefield, x, 13)
            self.assertTrue(upper.traversable, (x, 12))
            self.assertTrue(upper.occupiable, (x, 12))
            self.assertTrue(lower.traversable, (x, 13))
            self.assertTrue(lower.occupiable, (x, 13))

            cliff_edge = rules.get_edge_transition(battlefield, GridPosition(x, 12), GridPosition(x, 13))
            self.assertEqual(cliff_edge.transition_type, EdgeTransitionType.CLIMBABLE_LEDGE, x)
            self.assertEqual(cliff_edge.traversal_requirement, EdgeTraversalRequirement.CLIMB, x)
            self.assertTrue(cliff_edge.blocks_los, x)
            self.assertTrue(cliff_edge.blocks_loe, x)

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        actor = session.state.actors['player-1']
        actor.position = GridPosition(18, 12, rules.get_tile(session.state.battlefield, 18, 12).elevation_ft)
        actor.remaining_movement_ft = 30
        self.assertFalse(
            rules.can_move_between_cells(
                session.state,
                actor,
                actor.position,
                GridPosition(18, 13, rules.get_tile(session.state.battlefield, 18, 13).elevation_ft),
                movement_intent_mode=MovementIntentMode.SAME_PLANE,
            )
        )
        self.assertTrue(
            rules.can_move_between_cells(
                session.state,
                actor,
                actor.position,
                GridPosition(18, 13, rules.get_tile(session.state.battlefield, 18, 13).elevation_ft),
                movement_intent_mode=MovementIntentMode.ALLOW_CLIMB,
            )
        )
        self.assertFalse(rules.has_line_of_sight_to_position(session.state, actor, GridPosition(18, 13, 0)))
        self.assertFalse(rules.has_line_of_effect_to_position(session.state, actor, GridPosition(18, 13, 0)))
        upper_view = compute_actor_grid_vision(session.state, actor, time_of_day='day')
        self.assertNotIn(GridPosition(18, 13), upper_view.visible_cells)

        actor.position = GridPosition(18, 13, rules.get_tile(session.state.battlefield, 18, 13).elevation_ft)
        lower_view = compute_actor_grid_vision(session.state, actor, time_of_day='day')
        self.assertNotIn(GridPosition(18, 12), lower_view.visible_cells)

    def test_cragmaw_wall_side_blocks_sight_between_17_6_and_18_6(self) -> None:
        from encounter_runtime.vision import compute_actor_grid_vision
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        side_edge = rules.get_edge_transition(battlefield, GridPosition(17, 6), GridPosition(18, 6))
        self.assertTrue(side_edge.blocks_los)
        self.assertTrue(side_edge.blocks_loe)
        self.assertEqual(side_edge.transition_type, EdgeTransitionType.FLAT)
        self.assertEqual(side_edge.traversal_requirement, EdgeTraversalRequirement.NONE)

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        actor = session.state.actors['player-1']
        actor.position = GridPosition(17, 6, rules.get_tile(session.state.battlefield, 17, 6).elevation_ft)
        self.assertFalse(rules.has_line_of_sight_to_position(session.state, actor, GridPosition(18, 6, 20)))
        self.assertFalse(rules.has_line_of_effect_to_position(session.state, actor, GridPosition(18, 6, 20)))
        left_view = compute_actor_grid_vision(session.state, actor, time_of_day='day')
        self.assertNotIn(GridPosition(18, 6), left_view.visible_cells)

        actor.position = GridPosition(18, 6, rules.get_tile(session.state.battlefield, 18, 6).elevation_ft)
        self.assertFalse(rules.has_line_of_sight_to_position(session.state, actor, GridPosition(17, 6, 20)))
        self.assertFalse(rules.has_line_of_effect_to_position(session.state, actor, GridPosition(17, 6, 20)))
        right_view = compute_actor_grid_vision(session.state, actor, time_of_day='day')
        self.assertNotIn(GridPosition(17, 6), right_view.visible_cells)

    def test_cragmaw_actor_grid_vision_cache_keeps_answer_and_runs_under_one_ms(self) -> None:
        from cragmaw_map_demo_server import apply_light_fog_crate_fixture
        from encounter_runtime.vision import compute_actor_grid_vision
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        apply_light_fog_crate_fixture(session)
        actor = session.state.actors['player-1']

        expected = compute_actor_grid_vision(session.state, actor, time_of_day='night')
        warm = compute_actor_grid_vision(session.state, actor, time_of_day='night')
        self.assertEqual(warm.visible_cells, expected.visible_cells)
        self.assertEqual(warm.normal_vision_cells, expected.normal_vision_cells)
        self.assertEqual(warm.night_vision_cells, expected.night_vision_cells)

        durations_ms: list[float] = []
        for _ in range(30):
            started = time.perf_counter_ns()
            actual = compute_actor_grid_vision(session.state, actor, time_of_day='night')
            durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)
            self.assertEqual(actual.visible_cells, expected.visible_cells)
            self.assertEqual(actual.normal_vision_cells, expected.normal_vision_cells)
            self.assertEqual(actual.night_vision_cells, expected.night_vision_cells)
        average_ms = sum(durations_ms) / len(durations_ms)
        self.assertLess(average_ms, 1.0, f'Average cached Cragmaw vision time was {average_ms:.3f} ms.')

    def test_cragmaw_actor_grid_vision_after_movement_runs_under_one_ms(self) -> None:
        from cragmaw_map_demo_server import apply_light_fog_crate_fixture
        from encounter_runtime.vision import compute_actor_grid_vision
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        apply_light_fog_crate_fixture(session)
        actor = session.state.actors['player-1']
        movement_destinations = (GridPosition(14, 17, 0), GridPosition(13, 17, 0), GridPosition(12, 17, 0))

        for destination in movement_destinations:
            session.state, _ = session.command_interface.execute(session.state, f'/move player-1 {destination.x} {destination.y}')
            actor = session.state.actors['player-1']
            durations_ms: list[float] = []
            for _ in range(5):
                started = time.perf_counter_ns()
                result = compute_actor_grid_vision(session.state, actor, time_of_day='night')
                durations_ms.append((time.perf_counter_ns() - started) / 1_000_000)
                self.assertIn(actor.position.horizontal(), result.visible_cells)
            average_ms = sum(durations_ms) / len(durations_ms)
            self.assertLess(average_ms, 1.0, f'Average Cragmaw vision after movement to {destination} was {average_ms:.3f} ms.')

    def test_cragmaw_printed_legend_cells_are_authored_as_walls(self) -> None:
        expected_legend_cells = {(x, y) for x in range(1, 6) for y in range(12, 21)}
        map_data = json.loads(CRAGMAW_MAP_PATH.read_text(encoding='utf-8'))
        legend_region = next(
            (
                region
                for region in map_data['terrainRegions']
                if region['id'] == 'cragmaw_hideout_printed_legend_walls'
            ),
            None,
        )
        self.assertIsNotNone(legend_region)
        assert legend_region is not None
        self.assertEqual(legend_region['terrain'], 'stone_wall')
        self.assertEqual({tuple(cell) for cell in legend_region['cells']}, expected_legend_cells)

        battlefield = load_battlefield_state_from_json(CRAGMAW_MAP_PATH)
        rules = BattlefieldRules()
        for x, y in expected_legend_cells:
            legend_tile = rules.get_tile(battlefield, x, y)
            self.assertEqual(legend_tile.terrain_id, 'stone_wall')
            self.assertFalse(legend_tile.traversable)
            self.assertFalse(legend_tile.occupiable)
            self.assertTrue(legend_tile.blocks_los)
            self.assertTrue(legend_tile.blocks_loe)
            self.assertEqual(legend_tile.base_cover, CoverLevel.TOTAL)

    def test_day_night_grid_vision_uses_radius_and_wall_blocking(self) -> None:
        from encounter_runtime.vision import compute_grid_vision

        battlefield = self._linear_test_battlefield()
        day = compute_grid_vision(
            battlefield,
            origin=GridPosition(1, 0),
            time_of_day='day',
            day_radius_ft=60,
            night_radius_ft=15,
        )
        night = compute_grid_vision(
            battlefield,
            origin=GridPosition(1, 0),
            time_of_day='night',
            day_radius_ft=60,
            night_radius_ft=15,
        )

        self.assertEqual(day.radius_ft, 60)
        self.assertEqual(night.radius_ft, 15)
        self.assertIn(GridPosition(9, 0), day.visible_cells)
        self.assertNotIn(GridPosition(9, 0), night.visible_cells)

        wall_test = compute_grid_vision(
            battlefield,
            origin=GridPosition(1, 1),
            time_of_day='day',
            day_radius_ft=60,
            night_radius_ft=15,
        )
        self.assertIn(GridPosition(5, 1), wall_test.visible_cells)
        self.assertNotIn(GridPosition(6, 1), wall_test.visible_cells)
        self.assertNotIn(GridPosition(9, 1), wall_test.visible_cells)

    def test_cragmaw_map_demo_projects_background_and_player_visibility(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        self.assertIsNotNone(view.map)
        assert view.map is not None
        self.assertEqual(view.map.map_id, 'cragmaw_hideout_player_v1')
        self.assertEqual(view.map.vision_time_of_day, 'day')
        self.assertEqual(view.map.vision_actor_ids, ('player-1',))
        self.assertIsNotNone(view.map.background)
        assert view.map.background is not None
        self.assertEqual(view.map.background.url, 'assets/maps/cragmaw-hideout-player.webp')
        self.assertLess(sum(1 for cell in view.map.cells if cell.visible), len(view.map.cells))
        self.assertTrue(any(token.actor_id == 'player-1' and token.is_active for token in view.map.tokens))

    def test_actor_grid_vision_distinguishes_normal_and_night_vision(self) -> None:
        from encounter_runtime.vision import vision_modes_for_actors
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        bright_cell = GridPosition(14, 17)
        dark_cell = GridPosition(15, 17)
        session.state.battlefield.tiles[bright_cell] = replace(
            session.state.battlefield.tiles[bright_cell],
            lighting=LightingLevel.DIM,
        )
        session.state.battlefield.tiles[dark_cell] = replace(
            session.state.battlefield.tiles[dark_cell],
            lighting=LightingLevel.DARKNESS,
        )

        actor = session.state.actors['player-1']
        actor.darkvision_radius_ft = 0
        normal_modes = vision_modes_for_actors(session.state, ('player-1',), time_of_day='night')
        self.assertEqual(normal_modes.get(bright_cell), 'normal')
        self.assertNotIn(dark_cell, normal_modes)

        actor.darkvision_radius_ft = 60
        night_modes = vision_modes_for_actors(session.state, ('player-1',), time_of_day='night')
        self.assertEqual(night_modes.get(bright_cell), 'normal')
        self.assertEqual(night_modes.get(dark_cell), 'night')

    def test_cragmaw_map_projection_labels_normal_and_night_vision_cells(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        bright_cell = GridPosition(14, 17)
        dark_cell = GridPosition(15, 17)
        session.state.battlefield.tiles[bright_cell] = replace(
            session.state.battlefield.tiles[bright_cell],
            lighting=LightingLevel.DIM,
        )
        session.state.battlefield.tiles[dark_cell] = replace(
            session.state.battlefield.tiles[dark_cell],
            lighting=LightingLevel.DARKNESS,
        )
        session.state.actors['player-1'].darkvision_radius_ft = 60

        view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert view.map is not None
        cells = {(cell.position.x, cell.position.y): cell for cell in view.map.cells}
        self.assertTrue(cells[(14, 17)].visible)
        self.assertEqual(cells[(14, 17)].vision_mode, 'normal')
        self.assertTrue(cells[(15, 17)].visible)
        self.assertEqual(cells[(15, 17)].vision_mode, 'night')

        session.state.actors['player-1'].darkvision_radius_ft = 0
        view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert view.map is not None
        cells = {(cell.position.x, cell.position.y): cell for cell in view.map.cells}
        self.assertFalse(cells[(15, 17)].visible)
        self.assertEqual(cells[(15, 17)].vision_mode, 'none')

    def test_light_effect_turns_dark_and_dim_cells_into_normal_vision(self) -> None:
        from encounter_runtime.vision import vision_modes_for_actors
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        light_origin = GridPosition(13, 17)
        dim_target = GridPosition(18, 17)
        for position in (light_origin, dim_target):
            session.state.battlefield.tiles[position] = replace(
                session.state.battlefield.tiles[position],
                lighting=LightingLevel.DARKNESS,
            )
        actor = session.state.actors['player-1']
        actor.darkvision_radius_ft = 0

        before = vision_modes_for_actors(session.state, ('player-1',), time_of_day='night')
        self.assertNotIn(dim_target, before)

        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 light 13 17')

        after = vision_modes_for_actors(session.state, ('player-1',), time_of_day='night')
        self.assertEqual(after.get(light_origin), 'normal')
        self.assertEqual(after.get(dim_target), 'normal')

    def test_fog_cloud_fogs_cells_but_remains_projected_as_visible_effect(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view
        from shared_types.encounter_models import RuntimeSpellState

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        spell_record = next(record for record in session.runtime_services.encounter_catalog.spells.values() if record.name == 'Fog Cloud' and record.source == 'XPHB')
        session.state.actors['player-1'].spells['fog-cloud'] = RuntimeSpellState(
            option_id='fog-cloud',
            name=spell_record.name,
            source=spell_record.source,
            action_cost=spell_record.action_cost,
            range_ft=spell_record.range_ft,
            remaining_uses=None,
            level=spell_record.level,
            casting_time_seconds=spell_record.casting_time_seconds,
            perceptibility=spell_record.perceptibility,
            can_cast_as_ritual=spell_record.can_cast_as_ritual,
            ritual_additional_cast_seconds=spell_record.ritual_additional_cast_seconds,
            effect_type=spell_record.effect_type,
            max_uses=None,
            concentration=spell_record.concentration,
            capability=spell_record.capability,
            runtime_support=spell_record.runtime_support,
        )
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 fog-cloud 14 17')

        view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert view.map is not None
        cells = {(cell.position.x, cell.position.y): cell for cell in view.map.cells}
        self.assertFalse(cells[(14, 17)].visible)
        self.assertEqual(cells[(14, 17)].vision_mode, 'none')
        fog_features = [feature for feature in view.map.features if feature.display_name == 'Fog Cloud']
        self.assertEqual(len(fog_features), 1)
        self.assertEqual(fog_features[0].feature_type, 'persistent-area')

    def test_created_physical_crate_blocks_map_vision_behind_it(self) -> None:
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view
        from shared_types.capabilities import CreatedObjectDefinition
        from shared_types.encounter_events import CreatedObjectSpawnedEvent
        from shared_types.encounter_models import CreatedObjectState, PersistentEffectFamily, PersistentEffectState

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        for x in range(13, 18):
            position = GridPosition(x, 17)
            session.state.battlefield.tiles[position] = replace(
                session.state.battlefield.tiles[position],
                lighting=LightingLevel.DIM,
            )
        definition = CreatedObjectDefinition(
            name='Wooden Crate',
            feature_type='crate',
            blocks_los=True,
            blocks_loe=True,
            cover_provided=CoverLevel.TOTAL,
            semantic_tags=('crate', 'wooden-crate'),
        )
        persistent = PersistentEffectState(
            persistent_effect_id='test-crate:persistent',
            family=PersistentEffectFamily.CREATED_OBJECT,
            source_effect_id='test-crate:effect',
            source_capability_id='test-create-crate',
            source_actor_id='player-1',
            anchor_position=GridPosition(15, 17, 0),
        )
        created_object = CreatedObjectState(
            persistent=persistent,
            object_id='test-crate',
            definition=definition,
            cells=(GridPosition(15, 17, 0),),
            linked_feature_id='test-crate:feature',
        )
        session.command_interface.kernel._apply_event(session.state, CreatedObjectSpawnedEvent(created_object=created_object))

        view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert view.map is not None
        cells = {(cell.position.x, cell.position.y): cell for cell in view.map.cells}
        self.assertTrue(cells[(15, 17)].visible)
        self.assertFalse(cells[(16, 17)].visible)
        self.assertFalse(cells[(17, 17)].visible)
        crate_features = [feature for feature in view.map.features if 'crate' in feature.tags]
        self.assertEqual(len(crate_features), 1)
        self.assertTrue(crate_features[0].blocks_los)

    def test_manual_vision_fixture_projects_light_fog_and_crate(self) -> None:
        from cragmaw_map_demo_server import apply_light_fog_crate_fixture
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import inspect_cell, project_encounter_session_view

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        apply_light_fog_crate_fixture(session)

        player_view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        dm_view = project_encounter_session_view(session, 'dm', session_id='map-test')
        assert player_view.map is not None
        assert dm_view.map is not None
        player_cells = {(cell.position.x, cell.position.y): cell for cell in player_view.map.cells}

        self.assertEqual(player_view.map.vision_time_of_day, 'night')
        self.assertEqual(player_cells[(13, 17)].vision_mode, 'normal')
        self.assertFalse(player_cells[(15, 17)].visible)
        self.assertFalse(player_cells[(16, 17)].visible)
        self.assertTrue(any(feature.display_name == 'Fog Cloud' for feature in dm_view.map.features))
        player_fog_features = [feature for feature in player_view.map.features if feature.display_name == 'Fog Cloud']
        self.assertEqual(len(player_fog_features), 1)
        self.assertIn((12, 14), {(cell.x, cell.y) for cell in player_fog_features[0].cells})
        self.assertEqual(player_cells[(13, 17)].lighting, 'bright')
        self.assertEqual(player_cells[(19, 17)].lighting, 'dim')
        self.assertEqual(player_cells[(24, 16)].lighting, 'darkness')
        dm_cells = {(cell.position.x, cell.position.y): cell for cell in dm_view.map.cells}
        self.assertEqual(dm_cells[(12, 14)].obscurement, 'heavy')
        bright_inspection = inspect_cell(session, 'player-1-controller', x=13, y=17)
        dim_inspection = inspect_cell(session, 'dm', x=19, y=17)
        dark_inspection = inspect_cell(session, 'dm', x=24, y=16)
        fog_inspection = inspect_cell(session, 'dm', x=12, y=14)
        self.assertEqual(bright_inspection.lighting, 'bright')
        self.assertEqual(dim_inspection.lighting, 'dim')
        self.assertEqual(dark_inspection.lighting, 'darkness')
        self.assertEqual(fog_inspection.obscurement, 'heavy')

    def test_manual_vision_fixture_fog_cloud_blocks_sight_beyond_cloud(self) -> None:
        from cragmaw_map_demo_server import apply_light_fog_crate_fixture
        from encounter_runtime.vision import compute_actor_grid_vision
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        apply_light_fog_crate_fixture(session)
        actor = session.state.actors['player-1']

        result = compute_actor_grid_vision(session.state, actor, time_of_day='night')
        self.assertNotIn(GridPosition(12, 9), result.visible_cells)
        self.assertNotIn(GridPosition(12, 8), result.visible_cells)
        self.assertFalse(session.runtime_services.kernel.battlefield_rules.has_line_of_sight_to_position(session.state, actor, GridPosition(12, 9, 0)))
        self.assertFalse(session.runtime_services.kernel.battlefield_rules.has_line_of_sight_to_position(session.state, actor, GridPosition(12, 8, 0)))
        self.assertTrue(session.runtime_services.kernel.battlefield_rules.has_line_of_effect_to_position(session.state, actor, GridPosition(12, 9, 0)))

        player_view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert player_view.map is not None
        player_cells = {(cell.position.x, cell.position.y): cell for cell in player_view.map.cells}
        for coordinate in ((12, 9), (12, 8)):
            self.assertFalse(player_cells[coordinate].visible, coordinate)
            self.assertEqual(player_cells[coordinate].vision_mode, 'none', coordinate)
        self.assertEqual(len([feature for feature in player_view.map.features if feature.display_name == 'Fog Cloud']), 1)

    def test_manual_vision_fixture_observer_inside_fog_cloud_cannot_see_out(self) -> None:
        from cragmaw_map_demo_server import apply_light_fog_crate_fixture
        from encounter_runtime.vision import compute_actor_grid_vision
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        apply_light_fog_crate_fixture(session)
        actor = session.state.actors['player-1']
        actor.position = GridPosition(12, 10, 0)

        result = compute_actor_grid_vision(session.state, actor, time_of_day='night')
        self.assertIn(GridPosition(12, 10), result.visible_cells)
        for coordinate in (GridPosition(12, 9), GridPosition(12, 8)):
            self.assertNotIn(coordinate, result.visible_cells)
            self.assertFalse(session.runtime_services.kernel.battlefield_rules.has_line_of_sight_to_position(session.state, actor, coordinate))
            self.assertTrue(session.runtime_services.kernel.battlefield_rules.has_line_of_effect_to_position(session.state, actor, coordinate))

        player_view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert player_view.map is not None
        player_cells = {(cell.position.x, cell.position.y): cell for cell in player_view.map.cells}
        self.assertTrue(player_cells[(12, 10)].visible)
        for coordinate in ((12, 9), (12, 8)):
            self.assertFalse(player_cells[coordinate].visible, coordinate)
            self.assertEqual(player_cells[coordinate].vision_mode, 'none', coordinate)
        self.assertEqual(len([feature for feature in player_view.map.features if feature.display_name == 'Fog Cloud']), 1)

    def test_manual_vision_fixture_keeps_dark_water_visible_after_movement(self) -> None:
        from cragmaw_map_demo_server import apply_light_fog_crate_fixture
        from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
        from session_server.web_projection import project_encounter_session_view

        session = build_cragmaw_hideout_map_demo_session(base_url=LOCAL_MIRROR_BASE_URL)
        apply_light_fog_crate_fixture(session)
        session.state, _ = session.command_interface.execute(session.state, '/move player-1 27 7')

        player_view = project_encounter_session_view(session, 'player-1-controller', session_id='map-test')
        assert player_view.map is not None
        player_cells = {(cell.position.x, cell.position.y): cell for cell in player_view.map.cells}

        self.assertEqual(session.state.actors['player-1'].darkvision_radius_ft, 60)
        for coordinate in ((26, 7), (27, 6), (24, 6), (27, 8)):
            cell = player_cells[coordinate]
            self.assertEqual(cell.terrain_id, 'stream_water', coordinate)
            self.assertFalse(cell.blocks_los, coordinate)
            self.assertTrue(cell.visible, coordinate)
            self.assertEqual(cell.vision_mode, 'night', coordinate)

    def _linear_test_battlefield(self) -> BattlefieldState:
        grid = BattlefieldGridSpec(
            cell_size_feet=5,
            width=12,
            height=3,
            origin='top_left',
            coordinates='x_right_y_down',
            min_x=0,
            min_y=0,
            max_x=11,
            max_y=2,
        )
        tiles: dict[GridPosition, BattlefieldTile] = {}
        for y in range(3):
            for x in range(12):
                wall = (x, y) == (5, 1)
                position = GridPosition(x, y)
                tiles[position] = BattlefieldTile(
                    position=position,
                    terrain_id='wall' if wall else 'floor',
                    elevation_ft=0,
                    ceiling_ft=20,
                    traversable=not wall,
                    occupiable=not wall,
                    movement_cost_feet_per_5ft=5,
                    difficult_terrain=False,
                    lightly_obscured=False,
                    lighting=LightingLevel.BRIGHT,
                    obscurement=ObscurementLevel.NONE,
                    blocks_los=wall,
                    blocks_loe=wall,
                    base_cover=CoverLevel.TOTAL if wall else CoverLevel.NONE,
                    supported_modes=(TraversalMode.WALK,),
                    tags=('wall',) if wall else ('floor',),
                )
        return BattlefieldState(
            map_id='vision-linear-test',
            name='Vision Linear Test',
            grid=grid,
            tiles=tiles,
            base_tiles=dict(tiles),
        )


if __name__ == '__main__':
    unittest.main()
