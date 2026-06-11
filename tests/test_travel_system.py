from __future__ import annotations

import unittest
from pathlib import Path

from rules_engine.hexmap_loader import HexMapLoader
from rules_engine.travel import HexTravelEngine
from shared_types.errors import EncounterValidationError
from shared_types.travel import AdvanceTravelIntent, HexCoord, PlanTravelRouteIntent, TravelStatus


class TravelSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.map_path = Path('campaigns/lmop/maps/high-road-region-hex.json')
        cls.travel_map = HexMapLoader.load(cls.map_path)
        cls.engine = HexTravelEngine(cls.travel_map)

    def test_lmop_fixture_loads_with_expected_landmarks_and_hooks(self) -> None:
        self.assertEqual(self.travel_map.map_id, 'lmop_high_road_region_v1')
        self.assertEqual(self.travel_map.region_id, 'high-road-to-phandalin')
        self.assertEqual(len(self.travel_map.cells), 10)
        self.assertEqual(len(self.travel_map.landmarks), 8)
        self.assertEqual(len(self.travel_map.hooks), 3)
        high_road_hook = next(hook for hook in self.travel_map.hooks if hook.hook_id == 'hook-high-road-journey')
        self.assertEqual(high_road_hook.suggested_visible_npc_ids, ())

    def test_lmop_fixture_loads_pabtso_player_region_background_and_render_grid(self) -> None:
        background = self.travel_map.background_image
        self.assertIsNotNone(background)
        assert background is not None
        self.assertEqual(background.url, 'assets/maps/pabtso-phandalin-region-player.webp')
        self.assertEqual(background.source_internal_path, 'adventure/PaBTSO/004-map-0.01-phandalin-region-player.webp')
        self.assertEqual((background.width_px, background.height_px), (1700, 2216))
        self.assertEqual(background.grid_type, 'hexColsOdd')
        self.assertEqual(background.grid_size_px, 240)
        self.assertEqual((background.grid_offset_x_px, background.grid_offset_y_px), (17, -35))
        self.assertEqual(background.grid_scale, 3)
        self.assertEqual(background.effective_grid_size_px, 80)
        self.assertEqual(background.units, 'miles')
        self.assertEqual(background.grid_bounds.as_tuple(), (0, 0, 28, 27))
        self.assertEqual(background.grid_cell_count, 812)
        self.assertEqual(self.travel_map.hex_scale_miles, 5)

        cells = {(cell.coord.q, cell.coord.r): cell for cell in self.travel_map.cells}
        self.assertEqual(cells[(0, 0)].render_coord.as_tuple(), (6, 13))
        self.assertEqual(cells[(4, 0)].render_coord.as_tuple(), (11, 19))
        self.assertEqual(cells[(5, 0)].render_coord.as_tuple(), (13, 20))
        self.assertEqual(cells[(6, 0)].render_coord.as_tuple(), (15, 21))

    def test_route_planning_to_phandalin_uses_lmop_fixture(self) -> None:
        state, _events = self.engine.initial_state(
            start_coord=HexCoord(0, 0),
            current_scene_id='scene-waterdeep-gundren-briefing',
            current_location_id='waterdeep',
        )
        route = self.engine.preview_route(
            state,
            PlanTravelRouteIntent(controller_id='player-1-controller', destination_location_id='phandalin'),
            dm_view=False,
        )
        self.assertEqual((route.destination.q, route.destination.r), (6, 0))
        self.assertEqual(route.destination_label, 'Phandalin')
        self.assertEqual(route.estimated_cost_units, 8)
        self.assertEqual(route.estimated_minutes, 480)
        self.assertEqual(len(route.path), 7)

    def test_hidden_hex_route_is_rejected_for_players_until_discovered(self) -> None:
        state, _events = self.engine.initial_state(
            start_coord=HexCoord(0, 0),
            current_scene_id='scene-waterdeep-gundren-briefing',
            current_location_id='waterdeep',
        )
        with self.assertRaises(EncounterValidationError):
            self.engine.preview_route(
                state,
                PlanTravelRouteIntent(controller_id='player-1-controller', destination=HexCoord(5, -1)),
                dm_view=False,
            )

    def test_advancing_along_route_discovers_and_interrupts_at_ambush(self) -> None:
        state, _events = self.engine.initial_state(
            start_coord=HexCoord(0, 0),
            current_scene_id='scene-waterdeep-gundren-briefing',
            current_location_id='waterdeep',
        )
        state, _plan_events = self.engine.plan_route(
            state,
            PlanTravelRouteIntent(controller_id='player-1-controller', destination_location_id='phandalin'),
            dm_view=False,
        )
        advanced, events = self.engine.advance(state, AdvanceTravelIntent(controller_id='player-1-controller', steps=5))
        self.assertEqual((advanced.party_coord.q, advanced.party_coord.r), (5, 0))
        self.assertEqual(advanced.status, TravelStatus.INTERRUPTED)
        self.assertIsNotNone(advanced.pending_hook)
        self.assertEqual(advanced.pending_hook.hook_id, 'hook-ambush-candidate')
        self.assertIn('ambush-horses', advanced.discovered_landmark_ids)
        self.assertTrue(any(event.__class__.__name__ == 'TravelInterruptedEvent' for event in events))
        self.assertTrue(any(event.__class__.__name__ == 'TravelEventHookTriggeredEvent' for event in events))


if __name__ == '__main__':
    unittest.main()
