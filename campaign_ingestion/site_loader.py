"""Strict loader for authored, rules-owned campaign sites."""

from __future__ import annotations

import json
from pathlib import Path

from shared_types.campaign_site import (
    CampaignSiteDefinition,
    SiteConversation,
    TownPlace,
    SiteEntrance,
    SiteRoom,
    SiteDoor,
    SiteMonster,
    SiteEncounter,
    SiteInteraction,
    SiteHazard,
)
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError


def _cells(values):
    return tuple(GridPosition(*value) for value in values)


def _index(values, key):
    result = {getattr(value, key): value for value in values}
    if len(result) != len(values):
        raise EncounterValidationError(f'Duplicate site content key: {key}.')
    return result


def load_campaign_site(path: str | Path) -> CampaignSiteDefinition:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload['schema_version'] != 1:
        raise EncounterValidationError('Unsupported campaign-site schema.')
    places = _index(
        [
            TownPlace(
                **{
                    **item,
                    'conversations': tuple(
                        SiteConversation(**{**c, 'grants': tuple(c['grants'])}) for c in item['conversations']
                    ),
                }
            )
            for item in payload['places']
        ],
        'place_id',
    )
    rooms = _index(
        [SiteRoom(**{**item, 'cells': _cells(item['cells'])}) for item in payload['rooms']], 'room_id'
    )
    entrances = _index(
        [SiteEntrance(**{**item, 'positions': _cells(item['positions'])}) for item in payload['entrances']],
        'entrance_id',
    )
    doors = _index(
        [SiteDoor(**{**item, 'cells': _cells(item['cells'])}) for item in payload['doors']], 'door_id'
    )
    encounters = _index(
        [
            SiteEncounter(
                **{
                    **item,
                    'monsters': tuple(
                        SiteMonster(
                            **{
                                **m,
                                'position': GridPosition(*m['position']),
                                'conditions': tuple(m.get('conditions', [])),
                                'prepared_spell_ids': tuple(m.get('prepared_spell_ids', [])),
                                'spell_slot_counts': tuple(m.get('spell_slot_counts', [])),
                            }
                        )
                        for m in item['monsters']
                    ),
                    'trigger_cells': _cells(item['trigger_cells']),
                    'resolved_grants': tuple(item['resolved_grants']),
                }
            )
            for item in payload['encounters']
        ],
        'encounter_id',
    )
    interactions = _index(
        [
            SiteInteraction(
                **{
                    **item,
                    'grants': tuple(item['grants']),
                    'requires': tuple(item.get('requires', [])),
                    'required_open_doors': tuple(item['required_open_doors']),
                    'reveals_doors': tuple(item['reveals_doors']),
                }
            )
            for item in payload['interactions']
        ],
        'interaction_id',
    )
    hazards = _index(
        [SiteHazard(**{**item, 'cells': _cells(item['cells'])}) for item in payload['hazards']], 'hazard_id'
    )
    for item in entrances.values():
        if item.place_id not in places or not item.positions:
            raise EncounterValidationError(f'Invalid entrance: {item.entrance_id}.')
    for item in (*encounters.values(), *interactions.values()):
        if item.room_id not in rooms:
            raise EncounterValidationError(f'Unknown site room: {item.room_id}.')
    for item in interactions.values():
        if not set(item.required_open_doors + item.reveals_doors) <= doors.keys():
            raise EncounterValidationError(f'Unknown interaction door: {item.interaction_id}.')
        if item.required_living_encounter is not None and item.required_living_encounter not in encounters:
            raise EncounterValidationError(f'Unknown interaction encounter: {item.interaction_id}.')
    for door in doors.values():
        if not door.cells or len(door.cells) % 2:
            raise EncounterValidationError(f'Door needs paired boundary cells: {door.door_id}.')
    actor_ids = [monster.actor_id for item in encounters.values() for monster in item.monsters]
    if len(actor_ids) != len(set(actor_ids)):
        raise EncounterValidationError('Duplicate site monster actor id.')
    for place in places.values():
        if not (0 <= place.x <= 1 and 0 <= place.y <= 1):
            raise EncounterValidationError(f'Invalid town marker coordinates: {place.place_id}.')
    return CampaignSiteDefinition(
        site_id=payload['site_id'],
        town_location_id=payload['town_location_id'],
        dungeon_location_id=payload['dungeon_location_id'],
        town_image=payload['town_image'],
        town_width_px=payload['town_width_px'],
        town_height_px=payload['town_height_px'],
        battlefield_path=payload['battlefield_path'],
        arrival_text=payload['arrival_text'],
        places=places,
        rooms=rooms,
        entrances=entrances,
        doors=doors,
        encounters=encounters,
        interactions=interactions,
        hazards=hazards,
        chapter_id=payload['chapter_id'],
        arrival_scene_id=payload['arrival_scene_id'],
        dungeon_scene_id=payload['dungeon_scene_id'],
        arrival_goals=tuple(payload['arrival_goals']),
        arrival_open_loops=tuple(payload['arrival_open_loops']),
        return_grants=tuple(tuple(pair) for pair in payload['return_grants']),
    )
