from __future__ import annotations

import json
from pathlib import Path

from shared_types.errors import EncounterValidationError
from shared_types.travel import (
    HexCellDefinition,
    HexCoordinateSystem,
    HexCoord,
    HexLandmarkDefinition,
    HexMapDefinition,
    HexTerrainType,
    TravelHookDefinition,
    TravelHookTrigger,
    TravelHookType,
)


class HexMapLoader:
    @staticmethod
    def load(path: str | Path) -> HexMapDefinition:
        map_path = Path(path).resolve()
        payload = json.loads(map_path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise EncounterValidationError('Hex map payload must be a JSON object.')
        try:
            coord_system = HexCoordinateSystem(str(payload['coord_system']))
        except KeyError as exc:
            raise EncounterValidationError('Hex map payload is missing `coord_system`.') from exc
        cells = tuple(HexMapLoader._parse_cell(item) for item in HexMapLoader._require_list(payload, 'cells'))
        landmarks = tuple(HexMapLoader._parse_landmark(item) for item in HexMapLoader._require_list(payload, 'landmarks'))
        hooks = tuple(HexMapLoader._parse_hook(item) for item in HexMapLoader._require_list(payload, 'hooks'))
        if coord_system != HexCoordinateSystem.AXIAL:
            raise EncounterValidationError('Only axial hex coordinates are supported in this slice.')
        return HexMapDefinition(
            map_id=HexMapLoader._require_str(payload, 'map_id'),
            campaign_id=HexMapLoader._require_str(payload, 'campaign_id'),
            region_id=HexMapLoader._require_str(payload, 'region_id'),
            name=HexMapLoader._require_str(payload, 'name'),
            coord_system=coord_system,
            hex_scale_miles=HexMapLoader._require_int(payload, 'hex_scale_miles'),
            cells=cells,
            landmarks=landmarks,
            hooks=hooks,
        )

    @staticmethod
    def _parse_cell(item: object) -> HexCellDefinition:
        if not isinstance(item, dict):
            raise EncounterValidationError('Hex map cell entries must be objects.')
        return HexCellDefinition(
            coord=HexCoord(q=HexMapLoader._require_int(item, 'q'), r=HexMapLoader._require_int(item, 'r')),
            terrain=HexTerrainType(HexMapLoader._require_str(item, 'terrain')),
            travel_cost_units=HexMapLoader._require_int(item, 'travel_cost_units'),
            route_kind=HexMapLoader._optional_str(item, 'route_kind'),
            route_cost_adjustment_units=HexMapLoader._optional_int(item, 'route_cost_adjustment_units', default=0),
            landmark_ids=tuple(HexMapLoader._require_str_list(item, 'landmark_ids')),
            location_id=HexMapLoader._optional_str(item, 'location_id'),
            tags=tuple(HexMapLoader._require_str_list(item, 'tags')),
            discovered_by_default=HexMapLoader._optional_bool(item, 'discovered_by_default', default=False),
            traversable=HexMapLoader._optional_bool(item, 'traversable', default=True),
        )

    @staticmethod
    def _parse_landmark(item: object) -> HexLandmarkDefinition:
        if not isinstance(item, dict):
            raise EncounterValidationError('Hex map landmark entries must be objects.')
        return HexLandmarkDefinition(
            landmark_id=HexMapLoader._require_str(item, 'landmark_id'),
            name=HexMapLoader._require_str(item, 'name'),
            coord=HexCoord(q=HexMapLoader._require_int(item, 'q'), r=HexMapLoader._require_int(item, 'r')),
            description=HexMapLoader._optional_str(item, 'description', default='') or '',
            location_id=HexMapLoader._optional_str(item, 'location_id'),
            scene_id=HexMapLoader._optional_str(item, 'scene_id'),
            tags=tuple(HexMapLoader._require_str_list(item, 'tags')),
            hidden=HexMapLoader._optional_bool(item, 'hidden', default=False),
            revealed_by_default=HexMapLoader._optional_bool(item, 'revealed_by_default', default=False),
            discovery_radius=HexMapLoader._optional_int(item, 'discovery_radius', default=0),
        )

    @staticmethod
    def _parse_hook(item: object) -> TravelHookDefinition:
        if not isinstance(item, dict):
            raise EncounterValidationError('Hex map hook entries must be objects.')
        coord = None
        if 'q' in item or 'r' in item:
            coord = HexCoord(q=HexMapLoader._require_int(item, 'q'), r=HexMapLoader._require_int(item, 'r'))
        return TravelHookDefinition(
            hook_id=HexMapLoader._require_str(item, 'hook_id'),
            hook_type=TravelHookType(HexMapLoader._require_str(item, 'hook_type')),
            trigger=TravelHookTrigger(HexMapLoader._require_str(item, 'trigger')),
            summary=HexMapLoader._require_str(item, 'summary'),
            coord=coord,
            location_id=HexMapLoader._optional_str(item, 'location_id'),
            landmark_id=HexMapLoader._optional_str(item, 'landmark_id'),
            scene_id=HexMapLoader._optional_str(item, 'scene_id'),
            battlefield_map_id=HexMapLoader._optional_str(item, 'battlefield_map_id'),
            tags=tuple(HexMapLoader._require_str_list(item, 'tags')),
            once=HexMapLoader._optional_bool(item, 'once', default=True),
            interrupts_travel=HexMapLoader._optional_bool(item, 'interrupts_travel', default=False),
            suggested_open_loops=tuple(HexMapLoader._require_str_list(item, 'suggested_open_loops')),
            suggested_party_goals=tuple(HexMapLoader._require_str_list(item, 'suggested_party_goals')),
        )

    @staticmethod
    def _require_list(payload: dict[str, object], key: str) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise EncounterValidationError(f'Hex map payload field `{key}` must be a list.')
        return value

    @staticmethod
    def _require_str_list(payload: dict[str, object], key: str) -> list[str]:
        value = payload.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise EncounterValidationError(f'Hex map payload field `{key}` must be a list of strings.')
        return list(value)

    @staticmethod
    def _require_str(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise EncounterValidationError(f'Hex map payload field `{key}` must be a non-empty string.')
        return value.strip()

    @staticmethod
    def _optional_str(payload: dict[str, object], key: str, *, default: str | None = None) -> str | None:
        value = payload.get(key, default)
        if value is None:
            return None
        if not isinstance(value, str):
            raise EncounterValidationError(f'Hex map payload field `{key}` must be a string when present.')
        stripped = value.strip()
        return stripped or default

    @staticmethod
    def _require_int(payload: dict[str, object], key: str) -> int:
        value = payload.get(key)
        if not isinstance(value, int):
            raise EncounterValidationError(f'Hex map payload field `{key}` must be an integer.')
        return value

    @staticmethod
    def _optional_int(payload: dict[str, object], key: str, *, default: int) -> int:
        value = payload.get(key, default)
        if not isinstance(value, int):
            raise EncounterValidationError(f'Hex map payload field `{key}` must be an integer when present.')
        return value

    @staticmethod
    def _optional_bool(payload: dict[str, object], key: str, *, default: bool) -> bool:
        value = payload.get(key, default)
        if not isinstance(value, bool):
            raise EncounterValidationError(f'Hex map payload field `{key}` must be a boolean when present.')
        return value
