from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from character_creation import build_default_kernel
from dm_agent.memory import DmMemoryWriter
from dm_agent.runtime import DMStorytellingRuntime
from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface, SlashCommandInterface
from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from rules_engine.exploration import ExplorationProcedureEngine
from rules_engine.social import SocialConsequenceEngine
from rules_engine.hexmap_loader import HexMapLoader
from rules_engine.travel import HexTravelEngine
from session_server.encounter_session import EncounterSession
from session_server.storytelling_session import StorytellingSession
from shared_types.encounter_control import ControllerBinding, ControllerRole
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from shared_types.models import CharacterRecord
from shared_types.storytelling import RuntimeMode, StoryRuntimeState
from shared_types.travel import HexCoord


def build_default_character_record(*, base_url: str | None = None):
    kernel = build_default_kernel(base_url=base_url)
    ui = SlashCommandInterface(kernel)
    state = kernel.new_state()
    commands = (
        '/create begin',
        '/create choose species aasimar',
        '/create choose class wizard',
        '/create choose class-skills Arcana History',
        '/create choose background acolyte',
        '/create choose choice class:wizard:cantrips fire-bolt mage-hand light',
        '/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person',
        '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS',
        '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance',
        '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds',
        '/create ability generate point-buy 15 14 13 12 10 8',
        '/create ability assign 8 14 13 15 12 10',
        '/create background-asi choose acolyte-int2-wis1',
        '/create equipment background gold',
        '/create equipment class package wizard-package-1',
        '/create confirm',
    )
    for command in commands:
        state, _ = ui.execute(state, command)
    if state.character_record is None:
        raise RuntimeError('Character creation did not produce a CharacterRecord.')
    return state.character_record


def _clone_record(record, *, record_id: str):
    cloned = deepcopy(record)
    cloned.record_id = record_id
    return cloned


def _monster_id(runtime, *, name: str, source: str) -> str:
    for record_id, record in runtime.encounter_catalog.monsters.items():
        if record.name == name and record.source == source:
            return record_id
    raise RuntimeError(f'Monster not found: {name} [{source}]')


def _control_runtime(runtime):
    controllers = {
        'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
        'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
    }
    actor_controllers = {
        'player-1': 'player-1-controller',
        'monster-skeleton-1': 'dm',
        'monster-mage-1': 'dm',
    }
    return runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)


def _story_demo_control_runtime(runtime):
    controllers = {
        'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
        'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
        'player-2-controller': ControllerBinding(controller_id='player-2-controller', role=ControllerRole.PLAYER, label='Player 2'),
        'player-3-controller': ControllerBinding(controller_id='player-3-controller', role=ControllerRole.PLAYER, label='Player 3'),
        'player-4-controller': ControllerBinding(controller_id='player-4-controller', role=ControllerRole.PLAYER, label='Player 4'),
    }
    actor_controllers = {
        'player-1': 'player-1-controller',
        'player-2': 'player-2-controller',
        'player-3': 'player-3-controller',
        'player-4': 'player-4-controller',
        'monster-goblin-1': 'dm',
        'monster-goblin-2': 'dm',
        'monster-goblin-3': 'dm',
        'monster-goblin-4': 'dm',
    }
    return runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)


def build_default_encounter_session(*, base_url: str | None = None) -> EncounterSession:
    runtime = build_default_encounter_runtime(base_url=base_url)
    record = build_default_character_record(base_url=base_url)
    skeleton_id = _monster_id(runtime, name='Skeleton', source='XMM')
    mage_id = _monster_id(runtime, name='Mage', source='XMM')
    state = runtime.new_state(
        characters=(CharacterPlacement(actor_id='player-1', record=record, position=GridPosition(0, 0)),),
        monsters=(
            MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=GridPosition(6, 0)),
            MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=GridPosition(8, 2)),
        ),
    )
    return EncounterSession(
        state=state,
        control_runtime=_control_runtime(runtime),
        command_interface=EncounterSlashCommandInterface(runtime.kernel),
        runtime_services=runtime,
    )


def build_goblin_ambush_encounter_session(*, base_url: str | None = None, map_path: str | None = None) -> EncounterSession:
    runtime = build_default_encounter_runtime(base_url=base_url)
    record = build_default_character_record(base_url=base_url)
    skeleton_id = _monster_id(runtime, name='Skeleton', source='XMM')
    mage_id = _monster_id(runtime, name='Mage', source='XMM')
    battlefield = load_battlefield_state_from_json(map_path or DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
    player_start = battlefield.spawn_zones['players'][0]
    north_start = battlefield.spawn_zones['goblinNorth'][0]
    south_start = battlefield.spawn_zones['goblinSouth'][0]
    state = runtime.new_state(
        characters=(CharacterPlacement(actor_id='player-1', record=record, position=player_start),),
        monsters=(
            MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=north_start),
            MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=south_start),
        ),
        battlefield=battlefield,
    )
    return EncounterSession(
        state=state,
        control_runtime=_control_runtime(runtime),
        command_interface=EncounterSlashCommandInterface(runtime.kernel),
        runtime_services=runtime,
    )


def build_lmop_story_demo_encounter_session_from_records(
    *,
    player_records: tuple[CharacterRecord, CharacterRecord, CharacterRecord, CharacterRecord],
    base_url: str | None = None,
    map_path: str | None = None,
) -> EncounterSession:
    if len(player_records) != 4:
        raise RuntimeError('LMOP story demo requires exactly four confirmed player records.')
    runtime = build_default_encounter_runtime(base_url=base_url)
    battlefield = load_battlefield_state_from_json(map_path or DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
    goblin_id = _monster_id(runtime, name='Goblin Warrior', source='XMM')

    player_starts = battlefield.spawn_zones['players']
    north_starts = battlefield.spawn_zones['goblinNorth']
    south_starts = battlefield.spawn_zones['goblinSouth']

    characters = tuple(
        CharacterPlacement(
            actor_id=f'player-{index}',
            record=_clone_record(player_records[index - 1], record_id=f'level-1-character-p{index}'),
            position=player_starts[index - 1],
        )
        for index in range(1, 5)
    )
    monsters = (
        MonsterPlacement(actor_id='monster-goblin-1', monster_id=goblin_id, position=north_starts[0]),
        MonsterPlacement(actor_id='monster-goblin-2', monster_id=goblin_id, position=north_starts[1]),
        MonsterPlacement(actor_id='monster-goblin-3', monster_id=goblin_id, position=south_starts[0]),
        MonsterPlacement(actor_id='monster-goblin-4', monster_id=goblin_id, position=south_starts[1]),
    )
    state = runtime.new_state(characters=characters, monsters=monsters, battlefield=battlefield)
    for index in range(1, 5):
        state.actors[f'player-{index}'].name = f'Player {index}'
    for index in range(1, 5):
        state.actors[f'monster-goblin-{index}'].name = f'Goblin Ambusher {index}'

    return EncounterSession(
        state=state,
        control_runtime=_story_demo_control_runtime(runtime),
        command_interface=EncounterSlashCommandInterface(runtime.kernel),
        runtime_services=runtime,
    )


def build_lmop_story_demo_encounter_session(*, base_url: str | None = None, map_path: str | None = None) -> EncounterSession:
    base_record = build_default_character_record(base_url=base_url)
    player_records = tuple(
        _clone_record(base_record, record_id=f'level-1-character-p{index}')
        for index in range(1, 5)
    )
    return build_lmop_story_demo_encounter_session_from_records(
        player_records=player_records,
        base_url=base_url,
        map_path=map_path,
    )


def build_goblin_ambush_storytelling_session(
    *,
    base_url: str | None = None,
    campaign_root: str | Path | None = None,
    env_path: str | Path = '.env',
    client_transport=None,
) -> StorytellingSession:
    encounter_session = build_goblin_ambush_encounter_session(base_url=base_url)
    campaign_path = Path(campaign_root or Path(__file__).resolve().parents[1] / 'campaigns' / 'lmop')
    story_state = StoryRuntimeState(
        campaign_id='lmop',
        current_scene_id='scene-triboar-goblin-ambush',
        runtime_mode=RuntimeMode.STORYTELLING,
        current_chapter_id='chapter-01',
        canonical_location_id='triboar-trail',
        open_loops=('Who ordered the ambush?', 'Where were Gundren and Sildar taken?'),
        current_party_goals=('Survive the ambush.', 'Recover clues from the trail.'),
        recent_summary='The party has just reached the goblin ambush on Triboar Trail.',
        metadata={
            'retrieval_tags': 'ambush,trail,goblins',
            'nearby_tags': 'trail,forest',
            'visible_npc_ids': 'gundren-rockseeker,sildar-hallwinter',
        },
    )
    exploration_engine = ExplorationProcedureEngine(kernel=encounter_session.control_runtime.kernel, campaign_id='lmop')
    exploration_state, _ = exploration_engine.initial_state(
        encounter_state=encounter_session.state,
        actor_ids=tuple(actor_id for actor_id, actor in encounter_session.state.actors.items() if actor.side.value == 'player'),
        current_scene_id=story_state.current_scene_id,
        current_location_id=story_state.canonical_location_id,
        current_travel_map_id=None,
        travel_active=False,
    )
    story_state.exploration_state = exploration_state
    social_engine = SocialConsequenceEngine(campaign_id='lmop')
    story_state.social_state = social_engine.initial_state(exploration_state=exploration_state, current_location_id=story_state.canonical_location_id)
    dm_runtime = DMStorytellingRuntime.from_env(env_path=env_path, client_transport=client_transport)
    memory_writer = DmMemoryWriter(campaign_path.parent, campaign_id='lmop')
    return StorytellingSession(
        encounter_session=encounter_session,
        story_state=story_state,
        campaign_root=campaign_path,
        memory_writer=memory_writer,
        dm_runtime=dm_runtime,
        exploration_engine=exploration_engine,
        social_engine=social_engine,
    )


def build_lmop_story_demo_session_from_records(
    *,
    player_records: tuple[CharacterRecord, CharacterRecord, CharacterRecord, CharacterRecord],
    base_url: str | None = None,
    campaign_root: str | Path | None = None,
    env_path: str | Path = '.env',
    client_transport=None,
) -> StorytellingSession:
    encounter_session = build_lmop_story_demo_encounter_session_from_records(
        player_records=player_records,
        base_url=base_url,
    )
    campaign_path = Path(campaign_root or Path(__file__).resolve().parents[1] / 'campaigns' / 'lmop')
    travel_map = HexMapLoader.load(campaign_path / 'maps' / 'high-road-region-hex.json')
    travel_engine = HexTravelEngine(travel_map)
    travel_state, _ = travel_engine.initial_state(
        start_coord=HexCoord(0, 0),
        current_scene_id='scene-waterdeep-gundren-briefing',
        current_location_id='waterdeep',
    )
    story_state = StoryRuntimeState(
        campaign_id='lmop',
        current_scene_id='scene-waterdeep-gundren-briefing',
        runtime_mode=RuntimeMode.STORYTELLING,
        current_chapter_id='chapter-01',
        canonical_location_id='waterdeep',
        active_battlefield_map_id='goblin-ambush-triboar-trail',
        open_loops=(
            'Why is Gundren so eager to reach Phandalin ahead of the wagon?',
            'What exactly have Gundren and his brothers found?',
        ),
        current_party_goals=(
            'Hear Gundren out and decide whether to take the Phandalin job.',
            'Get the wagon safely onto the High Road.',
        ),
        recent_summary='The party is meeting Gundren Rockseeker in Waterdeep before the road job begins.',
        metadata={
            'retrieval_tags': 'waterdeep,gundren,phandalin,escort,high-road,triboar-trail',
            'nearby_tags': 'waterdeep,high-road,caravan',
            'visible_npc_ids': 'gundren-rockseeker,sildar-hallwinter',
            'party_beliefs': 'Gundren is excited about something important in Phandalin.',
        },
        travel_state=travel_state,
        session_log_id='session-0001',
    )
    exploration_engine = ExplorationProcedureEngine(kernel=encounter_session.control_runtime.kernel, campaign_id='lmop')
    exploration_state, _ = exploration_engine.initial_state(
        encounter_state=encounter_session.state,
        actor_ids=tuple(actor_id for actor_id, actor in encounter_session.state.actors.items() if actor.side.value == 'player'),
        current_scene_id=story_state.current_scene_id,
        current_location_id=story_state.canonical_location_id,
        current_travel_map_id=travel_state.map_id,
        travel_active=False,
    )
    story_state.exploration_state = exploration_state
    social_engine = SocialConsequenceEngine(campaign_id='lmop')
    story_state.social_state = social_engine.initial_state(exploration_state=exploration_state, current_location_id=story_state.canonical_location_id)
    dm_runtime = DMStorytellingRuntime.from_env(env_path=env_path, client_transport=client_transport)
    memory_writer = DmMemoryWriter(campaign_path.parent, campaign_id='lmop')
    return StorytellingSession(
        encounter_session=encounter_session,
        story_state=story_state,
        campaign_root=campaign_path,
        memory_writer=memory_writer,
        dm_runtime=dm_runtime,
        travel_engine=travel_engine,
        exploration_engine=exploration_engine,
        social_engine=social_engine,
    )


def build_lmop_story_demo_session(
    *,
    base_url: str | None = None,
    campaign_root: str | Path | None = None,
    env_path: str | Path = '.env',
    client_transport=None,
) -> StorytellingSession:
    base_record = build_default_character_record(base_url=base_url)
    player_records = tuple(
        _clone_record(base_record, record_id=f'level-1-character-p{index}')
        for index in range(1, 5)
    )
    return build_lmop_story_demo_session_from_records(
        player_records=player_records,
        base_url=base_url,
        campaign_root=campaign_root,
        env_path=env_path,
        client_transport=client_transport,
    )

