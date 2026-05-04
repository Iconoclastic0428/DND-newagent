from __future__ import annotations

from dataclasses import replace
import heapq

from shared_types.encounter_events import (
    HexDiscoveredEvent,
    HexMapLoadedEvent,
    LandmarkDiscoveredEvent,
    LocationReachedEvent,
    TravelEventHookTriggeredEvent,
    TravelInterruptedEvent,
    TravelModeProjectionUpdatedEvent,
    TravelPaceChangedEvent,
    TravelResumedEvent,
    TravelRoutePlannedEvent,
    TravelStartedEvent,
    TravelStepAdvancedEvent,
)
from shared_types.errors import EncounterValidationError
from shared_types.travel import (
    AXIAL_DIRECTIONS,
    PACE_PROFILES,
    AdvanceTravelIntent,
    HexCoord,
    HexLandmarkDefinition,
    HexMapDefinition,
    PlanTravelRouteIntent,
    PlannedTravelRoute,
    ResumeTravelIntent,
    SetTravelPaceIntent,
    TravelHexInspection,
    TravelHookDefinition,
    TravelHookTrigger,
    TravelPace,
    TravelState,
    TravelStatus,
    unique_coords,
    unique_strings,
)


class HexTravelEngine:
    def __init__(self, travel_map: HexMapDefinition) -> None:
        self.travel_map = travel_map
        self.cells = {cell.coord: cell for cell in travel_map.cells}
        self.landmarks = {landmark.landmark_id: landmark for landmark in travel_map.landmarks}
        self.location_landmarks = {
            landmark.location_id: landmark
            for landmark in travel_map.landmarks
            if landmark.location_id is not None
        }
        self.location_cells = {
            cell.location_id: cell.coord
            for cell in travel_map.cells
            if cell.location_id is not None
        }

    def initial_state(self, *, start_coord: HexCoord, current_scene_id: str | None, current_location_id: str | None) -> tuple[TravelState, list[object]]:
        if start_coord not in self.cells:
            raise EncounterValidationError('Travel start hex is not present on the map.')
        discovered_hexes = tuple(cell.coord for cell in self.travel_map.cells if cell.discovered_by_default)
        discovered_landmarks = tuple(landmark.landmark_id for landmark in self.travel_map.landmarks if landmark.revealed_by_default)
        known_locations = tuple(
            location_id
            for location_id, coord in self.location_cells.items()
            if coord in discovered_hexes
        )
        state = TravelState(
            map_id=self.travel_map.map_id,
            party_coord=start_coord,
            discovered_hexes=unique_coords(discovered_hexes + (start_coord,)),
            discovered_landmark_ids=unique_strings(discovered_landmarks),
            known_location_ids=unique_strings(known_locations + ((current_location_id,) if current_location_id else ())),
            pace=TravelPace.NORMAL,
            status=TravelStatus.IDLE,
            planned_route=None,
            elapsed_minutes=0,
            pending_hook=None,
            triggered_hook_ids=(),
            current_scene_id=current_scene_id,
            current_location_id=current_location_id,
            metadata={},
        )
        events: list[object] = [HexMapLoadedEvent(map_id=self.travel_map.map_id, region_id=self.travel_map.region_id)]
        state, discovery_events = self._apply_discovery(state, center=start_coord)
        events.extend(discovery_events)
        events.append(TravelModeProjectionUpdatedEvent(map_id=self.travel_map.map_id, status=state.status))
        return state, events

    def inspect_hex(self, state: TravelState, *, coord: HexCoord, dm_view: bool) -> TravelHexInspection:
        cell = self.cells.get(coord)
        if cell is None:
            raise EncounterValidationError('Unknown hex coordinate.')
        discovered = coord in state.discovered_hexes
        if not dm_view and not discovered:
            raise EncounterValidationError('That hex is not currently known to the party.')
        visible_landmarks = tuple(
            landmark.landmark_id
            for landmark in self.landmarks.values()
            if landmark.coord == coord and (dm_view or landmark.landmark_id in state.discovered_landmark_ids)
        )
        return TravelHexInspection(
            coord=coord,
            terrain=cell.terrain,
            travel_cost_units=self._cell_cost_units(coord),
            route_kind=cell.route_kind,
            discovered=discovered,
            traversable=cell.traversable,
            location_id=cell.location_id,
            landmark_ids=visible_landmarks,
            tags=cell.tags,
            reachable_by_known_route=(dm_view or discovered),
        )

    def preview_route(self, state: TravelState, intent: PlanTravelRouteIntent, *, dm_view: bool) -> PlannedTravelRoute:
        destination = self._resolve_destination(intent)
        if not dm_view and destination not in state.discovered_hexes:
            landmark = self._landmark_at_coord(destination)
            if landmark is None or landmark.landmark_id not in state.discovered_landmark_ids:
                raise EncounterValidationError('Players may only route to discovered hexes or known landmarks.')
        path = self._shortest_path(state.party_coord, destination, restrict_to_known=(not dm_view), known_hexes=state.discovered_hexes)
        return self._route_from_path(path)

    def plan_route(self, state: TravelState, intent: PlanTravelRouteIntent, *, dm_view: bool) -> tuple[TravelState, list[object]]:
        route = self.preview_route(state, intent, dm_view=dm_view)
        new_state = replace(
            state,
            planned_route=route,
            status=TravelStatus.ROUTE_PLANNED,
            pending_hook=None,
        )
        events: list[object] = [TravelRoutePlannedEvent(route=route)]
        if state.status == TravelStatus.IDLE:
            events.append(TravelStartedEvent(map_id=self.travel_map.map_id, start_coord=state.party_coord, destination=route.destination))
        events.append(TravelModeProjectionUpdatedEvent(map_id=self.travel_map.map_id, status=new_state.status))
        return new_state, events

    def set_pace(self, state: TravelState, intent: SetTravelPaceIntent) -> tuple[TravelState, list[object]]:
        if state.pace == intent.pace:
            return state, []
        new_state = replace(state, pace=intent.pace)
        if state.planned_route is not None:
            refreshed = self._shortest_path(state.party_coord, state.planned_route.destination, restrict_to_known=False, known_hexes=state.discovered_hexes)
            new_state = replace(new_state, planned_route=self._route_from_path(refreshed, pace=intent.pace))
        return new_state, [TravelPaceChangedEvent(old_pace=state.pace, new_pace=intent.pace), TravelModeProjectionUpdatedEvent(map_id=self.travel_map.map_id, status=new_state.status)]

    def advance(self, state: TravelState, intent: AdvanceTravelIntent) -> tuple[TravelState, list[object]]:
        if intent.steps <= 0:
            raise EncounterValidationError('Travel advance requires at least one step.')
        if state.pending_hook is not None:
            raise EncounterValidationError('Travel is interrupted by a pending hook and must be resumed or resolved first.')
        if state.planned_route is None or len(state.planned_route.path) < 2:
            raise EncounterValidationError('There is no planned travel route to advance.')
        work = state
        events: list[object] = []
        if state.status != TravelStatus.IN_PROGRESS:
            events.append(TravelStartedEvent(map_id=self.travel_map.map_id, start_coord=state.party_coord, destination=state.planned_route.destination))
        for _ in range(intent.steps):
            if work.planned_route is None or len(work.planned_route.path) < 2:
                break
            next_coord = work.planned_route.path[1]
            minutes_elapsed = self._travel_minutes_for_coord(next_coord, work.pace)
            remaining_path = work.planned_route.path[1:]
            route_after_step = None if len(remaining_path) <= 1 else self._route_from_path(remaining_path, pace=work.pace)
            work = replace(
                work,
                party_coord=next_coord,
                planned_route=route_after_step,
                elapsed_minutes=work.elapsed_minutes + minutes_elapsed,
                status=TravelStatus.IN_PROGRESS if route_after_step is not None else TravelStatus.IDLE,
            )
            events.append(
                TravelStepAdvancedEvent(
                    map_id=self.travel_map.map_id,
                    from_coord=state.party_coord if not events or not isinstance(events[-1], TravelStepAdvancedEvent) else events[-1].to_coord,
                    to_coord=next_coord,
                    minutes_elapsed=minutes_elapsed,
                    total_elapsed_minutes=work.elapsed_minutes,
                )
            )
            work, discovery_events = self._apply_discovery(work, center=next_coord)
            events.extend(discovery_events)
            work, progress_events = self._apply_progress_hooks(work, entered_coord=next_coord)
            events.extend(progress_events)
            if work.pending_hook is not None:
                break
        events.append(TravelModeProjectionUpdatedEvent(map_id=self.travel_map.map_id, status=work.status))
        return work, events

    def resume(self, state: TravelState, intent: ResumeTravelIntent) -> tuple[TravelState, list[object]]:
        if state.pending_hook is None and state.status != TravelStatus.INTERRUPTED:
            raise EncounterValidationError('Travel is not currently interrupted.')
        status = TravelStatus.IN_PROGRESS if state.planned_route is not None else TravelStatus.IDLE
        new_state = replace(state, pending_hook=None, status=status)
        return new_state, [TravelResumedEvent(map_id=self.travel_map.map_id, current_coord=state.party_coord), TravelModeProjectionUpdatedEvent(map_id=self.travel_map.map_id, status=new_state.status)]

    def _apply_discovery(self, state: TravelState, *, center: HexCoord) -> tuple[TravelState, list[object]]:
        pace_profile = PACE_PROFILES[state.pace]
        visible_hexes = self._hexes_within_radius(center, pace_profile.discovery_radius)
        discovered = set(state.discovered_hexes)
        events: list[object] = []
        for coord in visible_hexes:
            if coord not in self.cells or coord in discovered:
                continue
            discovered.add(coord)
            events.append(HexDiscoveredEvent(coord=coord))
        discovered_landmarks = set(state.discovered_landmark_ids)
        known_locations = set(state.known_location_ids)
        for landmark in self.travel_map.landmarks:
            if landmark.landmark_id in discovered_landmarks:
                continue
            if self._landmark_is_discovered(landmark, center=center, discovered_hexes=tuple(discovered)):
                discovered_landmarks.add(landmark.landmark_id)
                events.append(LandmarkDiscoveredEvent(landmark_id=landmark.landmark_id, name=landmark.name, coord=landmark.coord))
                if landmark.location_id is not None:
                    known_locations.add(landmark.location_id)
        return replace(
            state,
            discovered_hexes=unique_coords(tuple(discovered)),
            discovered_landmark_ids=unique_strings(tuple(discovered_landmarks)),
            known_location_ids=unique_strings(tuple(known_locations)),
        ), events

    def _apply_progress_hooks(self, state: TravelState, *, entered_coord: HexCoord) -> tuple[TravelState, list[object]]:
        triggered_hook_ids = set(state.triggered_hook_ids)
        events: list[object] = []
        pending_hook = state.pending_hook
        cell = self.cells[entered_coord]
        if cell.location_id is not None and cell.location_id != state.current_location_id:
            events.append(LocationReachedEvent(location_id=cell.location_id, name=self._location_name(cell.location_id), coord=entered_coord))
        for hook in self.travel_map.hooks:
            if hook.once and hook.hook_id in triggered_hook_ids:
                continue
            if hook.trigger == TravelHookTrigger.ENTER_HEX and hook.coord == entered_coord:
                events.append(TravelEventHookTriggeredEvent(hook=hook))
                triggered_hook_ids.add(hook.hook_id)
                if pending_hook is None and hook.interrupts_travel:
                    pending_hook = hook
            elif hook.trigger == TravelHookTrigger.LOCATION_REACHED and hook.location_id is not None and hook.location_id == cell.location_id:
                events.append(TravelEventHookTriggeredEvent(hook=hook))
                triggered_hook_ids.add(hook.hook_id)
                if pending_hook is None and hook.interrupts_travel:
                    pending_hook = hook
            elif hook.trigger == TravelHookTrigger.LANDMARK_DISCOVERED and hook.landmark_id is not None and hook.landmark_id in state.discovered_landmark_ids:
                events.append(TravelEventHookTriggeredEvent(hook=hook))
                triggered_hook_ids.add(hook.hook_id)
                if pending_hook is None and hook.interrupts_travel:
                    pending_hook = hook
        new_state = replace(
            state,
            triggered_hook_ids=unique_strings(tuple(triggered_hook_ids)),
            pending_hook=pending_hook,
            current_location_id=cell.location_id or state.current_location_id,
            status=TravelStatus.INTERRUPTED if pending_hook is not None else state.status,
        )
        if pending_hook is not None:
            events.append(TravelInterruptedEvent(map_id=self.travel_map.map_id, reason=pending_hook.summary, hook_id=pending_hook.hook_id))
        return new_state, events

    def _resolve_destination(self, intent: PlanTravelRouteIntent) -> HexCoord:
        if intent.destination is not None:
            if intent.destination not in self.cells:
                raise EncounterValidationError('Destination hex is not present on the map.')
            return intent.destination
        if intent.destination_location_id is not None:
            coord = self.location_cells.get(intent.destination_location_id)
            if coord is None:
                landmark = self.location_landmarks.get(intent.destination_location_id)
                if landmark is None:
                    raise EncounterValidationError('Unknown travel destination location.')
                return landmark.coord
            return coord
        raise EncounterValidationError('Travel route planning requires a destination hex or location id.')

    def _shortest_path(self, start: HexCoord, destination: HexCoord, *, restrict_to_known: bool, known_hexes: tuple[HexCoord, ...]) -> tuple[HexCoord, ...]:
        allowed = set(known_hexes)
        frontier: list[tuple[int, int, HexCoord, tuple[HexCoord, ...]]] = [(0, 0, start, (start,))]
        visited: dict[HexCoord, int] = {}
        counter = 0
        while frontier:
            cost, _, coord, path = heapq.heappop(frontier)
            if coord == destination:
                return path
            if coord in visited and visited[coord] <= cost:
                continue
            visited[coord] = cost
            for neighbor in self._neighbors(coord):
                cell = self.cells.get(neighbor)
                if cell is None or not cell.traversable:
                    continue
                if restrict_to_known and neighbor not in allowed and neighbor != destination:
                    continue
                counter += 1
                heapq.heappush(frontier, (cost + self._cell_cost_units(neighbor), counter, neighbor, path + (neighbor,)))
        raise EncounterValidationError('No legal travel route exists to that destination.')

    def _route_from_path(self, path: tuple[HexCoord, ...], *, pace: TravelPace | None = None) -> PlannedTravelRoute:
        if len(path) < 1:
            raise EncounterValidationError('Travel routes must include at least one hex.')
        final_coord = path[-1]
        effective_pace = pace or TravelPace.NORMAL
        estimated_cost_units = sum(self._cell_cost_units(coord) for coord in path[1:])
        estimated_minutes = estimated_cost_units * PACE_PROFILES[effective_pace].minutes_per_cost_unit
        return PlannedTravelRoute(
            destination=final_coord,
            destination_label=self._destination_label(final_coord),
            path=path,
            estimated_cost_units=estimated_cost_units,
            estimated_minutes=estimated_minutes,
        )

    def _neighbors(self, coord: HexCoord) -> tuple[HexCoord, ...]:
        return tuple(coord.neighbor(direction) for direction in AXIAL_DIRECTIONS if coord.neighbor(direction) in self.cells)

    def _hexes_within_radius(self, center: HexCoord, radius: int) -> tuple[HexCoord, ...]:
        if radius <= 0:
            return (center,)
        visible: list[HexCoord] = []
        for coord in self.cells:
            if self._axial_distance(center, coord) <= radius:
                visible.append(coord)
        return tuple(visible)

    def _landmark_is_discovered(self, landmark: HexLandmarkDefinition, *, center: HexCoord, discovered_hexes: tuple[HexCoord, ...]) -> bool:
        if landmark.revealed_by_default:
            return True
        if landmark.hidden:
            return landmark.coord == center
        if landmark.coord in discovered_hexes:
            return True
        return self._axial_distance(center, landmark.coord) <= landmark.discovery_radius

    def _destination_label(self, coord: HexCoord) -> str:
        landmark = self._landmark_at_coord(coord)
        if landmark is not None:
            return landmark.name
        cell = self.cells[coord]
        if cell.location_id is not None:
            return self._location_name(cell.location_id)
        return f'Hex {coord.q},{coord.r}'

    def _location_name(self, location_id: str) -> str:
        landmark = self.location_landmarks.get(location_id)
        if landmark is not None:
            return landmark.name
        return location_id.replace('-', ' ').title()

    def _landmark_at_coord(self, coord: HexCoord) -> HexLandmarkDefinition | None:
        for landmark in self.travel_map.landmarks:
            if landmark.coord == coord:
                return landmark
        return None

    def _cell_cost_units(self, coord: HexCoord) -> int:
        cell = self.cells[coord]
        return max(1, cell.travel_cost_units + cell.route_cost_adjustment_units)

    def _travel_minutes_for_coord(self, coord: HexCoord, pace: TravelPace) -> int:
        return self._cell_cost_units(coord) * PACE_PROFILES[pace].minutes_per_cost_unit

    def _axial_distance(self, a: HexCoord, b: HexCoord) -> int:
        return (abs(a.q - b.q) + abs(a.q + a.r - b.q - b.r) + abs(a.r - b.r)) // 2
