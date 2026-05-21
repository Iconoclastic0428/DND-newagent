from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Iterable

from training.trajectory_summary import load_trajectory_records


PLAYER_ROLES = ('player',)
REWARD_CHANNELS = {
    'valid_action': 'validity',
    'invalid_action': 'validity',
    'story_progress': 'progress',
    'state_progress': 'progress',
    'mode_progress': 'progress',
    'scene_goal_completed': 'progress',
    'hidden_subgoal_completed': 'progress',
    'discovery_made': 'progress',
    'social_topic_revealed': 'progress',
    'party_goal_resolved': 'progress',
    'open_loop_resolved': 'progress',
    'combat_step_cost': 'efficiency',
    'enemy_damage': 'offense',
    'enemy_defeated': 'offense',
    'ally_healing': 'support',
    'ally_temp_hp_gained': 'support',
    'ally_buff_applied': 'support',
    'ally_help_provided': 'support',
    'enemy_action_debuff_applied': 'control',
    'enemy_control_applied': 'control',
    'enemy_accuracy_debuff_applied': 'control',
    'enemy_defense_debuff_applied': 'control',
    'enemy_mobility_debuff_applied': 'control',
    'enemy_general_debuff_applied': 'control',
    'party_damage_taken': 'penalty',
    'enemy_healing': 'penalty',
    'enemy_temp_hp_gained': 'penalty',
    'enemy_buff_applied': 'penalty',
    'enemy_help_provided': 'penalty',
    'ally_defeated': 'penalty',
    'ally_action_debuffed': 'penalty',
    'ally_control_debuffed': 'penalty',
    'ally_accuracy_debuffed': 'penalty',
    'ally_defense_debuffed': 'penalty',
    'ally_mobility_debuffed': 'penalty',
    'ally_general_debuffed': 'penalty',
    'repetitive_words': 'penalty',
    'repetitive_action': 'penalty',
    'stalled_scene_turn': 'penalty',
}
TERMINAL_REWARD_CHANNEL = 'terminal'


def build_training_transitions(
    path_or_records: str | Path | Iterable[dict[str, Any]],
    *,
    include_roles: tuple[str, ...] = PLAYER_ROLES,
    include_sources: tuple[str, ...] | None = None,
    include_errors: bool = True,
) -> list[dict[str, Any]]:
    if isinstance(path_or_records, (str, Path)):
        records = load_trajectory_records(path_or_records)
        trajectory_path = str(Path(path_or_records))
    else:
        records = list(path_or_records)
        trajectory_path = None

    turns = [record for record in records if record.get('record_type') == 'turn']
    exported_turns = [
        turn for turn in turns
        if _include_turn(turn, include_roles=include_roles, include_sources=include_sources, include_errors=include_errors)
    ]
    terminal_by_episode = _terminal_by_episode(records)
    last_exported_turn_by_episode = _last_exported_turn_by_episode(exported_turns)

    transitions: list[dict[str, Any]] = []
    for turn in exported_turns:
        episode_id = str(turn.get('episode_id') or '')
        terminal = terminal_by_episode.get(episode_id)
        done = last_exported_turn_by_episode.get(episode_id) is turn
        action_reward = _reward_total(turn)
        terminal_reward = _reward_total(terminal) if done and terminal is not None else 0.0
        observation = _dict_or_empty(turn.get('observation'))
        next_observation = _dict_or_empty(turn.get('post_observation'))
        reward_components = _dict_or_empty(turn.get('reward_components'))
        terminal_reward_components = _dict_or_empty(terminal.get('reward_components')) if done and terminal is not None else {}
        action_reward_channels = reward_channels(reward_components)
        terminal_reward_channels = _terminal_reward_channels(terminal_reward_components)
        combined_reward_channels = _merge_reward_channels(action_reward_channels, terminal_reward_channels)
        acting_actor_id = _acting_actor_id(turn)
        target_actor_ids = _target_actor_ids(turn)
        transitions.append(
            {
                'sample_id': f'{episode_id}:{turn.get("turn_index")}',
                'trajectory_path': trajectory_path,
                'episode_id': episode_id,
                'scenario_id': turn.get('scenario_id'),
                'turn_index': turn.get('turn_index'),
                'agent_id': turn.get('agent_id'),
                'role': turn.get('role'),
                'source': turn.get('source'),
                'runtime_mode': turn.get('runtime_mode'),
                'acting_actor_id': acting_actor_id,
                'target_actor_ids': target_actor_ids,
                'observation': observation,
                'available_actions': _available_actions(observation),
                'action': turn.get('raw_text') or '',
                'parsed_action': _dict_or_none(turn.get('parsed_action')),
                'next_observation': next_observation,
                'state_before': _dict_or_none(turn.get('state_before')),
                'state_after': _dict_or_none(turn.get('state_after')),
                'reward': action_reward + terminal_reward,
                'action_reward': action_reward,
                'terminal_reward': terminal_reward,
                'reward_components': reward_components,
                'terminal_reward_components': terminal_reward_components,
                'reward_channels': combined_reward_channels,
                'action_reward_channels': action_reward_channels,
                'terminal_reward_channels': terminal_reward_channels,
                'reward_attribution': {
                    'actor_id': acting_actor_id,
                    'target_actor_ids': target_actor_ids,
                    'credit_scope': _credit_scope(action_reward=action_reward, terminal_reward=terminal_reward),
                    'action_reward': action_reward,
                    'team_terminal_reward': terminal_reward,
                    'channels': combined_reward_channels,
                },
                'done': done,
                'success': _terminal_success(terminal) if done else None,
                'error': turn.get('error'),
            }
        )
    return transitions


def write_training_transitions_jsonl(transitions: Iterable[dict[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for transition in transitions:
            handle.write(json.dumps(transition, ensure_ascii=False, sort_keys=True) + '\n')
    return path


def reward_channels(components: dict[str, Any]) -> dict[str, float]:
    channels: dict[str, float] = {}
    for component_name, value in components.items():
        if not isinstance(value, (int, float)):
            continue
        channel = REWARD_CHANNELS.get(component_name, 'other')
        channels[channel] = channels.get(channel, 0.0) + float(value)
    return channels


def _include_turn(
    turn: dict[str, Any],
    *,
    include_roles: tuple[str, ...],
    include_sources: tuple[str, ...] | None,
    include_errors: bool,
) -> bool:
    if include_roles and str(turn.get('role')) not in include_roles:
        return False
    if include_sources is not None and str(turn.get('source')) not in include_sources:
        return False
    if not include_errors and turn.get('error'):
        return False
    return bool(turn.get('agent_id')) and turn.get('raw_text') is not None


def _terminal_by_episode(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    terminal_by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get('record_type') != 'episode_completed':
            continue
        episode_id = record.get('episode_id')
        if episode_id is not None:
            terminal_by_id[str(episode_id)] = record
    return terminal_by_id


def _last_exported_turn_by_episode(turns: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    last_by_id: dict[str, dict[str, Any]] = {}
    for turn in turns:
        episode_id = turn.get('episode_id')
        if episode_id is not None:
            last_by_id[str(episode_id)] = turn
    return last_by_id


def _available_actions(observation: dict[str, Any]) -> list[dict[str, Any]]:
    choices = observation.get('available_choices')
    if isinstance(choices, dict):
        actions: list[dict[str, Any]] = []
        for group_id, group_choices in choices.items():
            if not isinstance(group_choices, (list, tuple)):
                continue
            for choice in group_choices:
                if not isinstance(choice, dict):
                    continue
                option_id = choice.get('option_id')
                if option_id is None:
                    continue
                actions.append(
                    {
                        'group_id': str(group_id),
                        'option_id': str(option_id),
                        'label': str(choice.get('label') or ''),
                        'detail': str(choice.get('detail') or ''),
                    }
                )
        return actions
    groups = observation.get('available_action_groups')
    if isinstance(groups, (list, tuple)):
        return [{'group_id': str(group_id), 'option_id': '', 'label': '', 'detail': ''} for group_id in groups]
    return []


def _terminal_reward_channels(components: dict[str, Any]) -> dict[str, float]:
    total = 0.0
    for value in components.values():
        if isinstance(value, (int, float)):
            total += float(value)
    return {TERMINAL_REWARD_CHANNEL: total} if total else {}


def _merge_reward_channels(*channel_dicts: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for channels in channel_dicts:
        for channel, value in channels.items():
            merged[channel] = merged.get(channel, 0.0) + float(value)
    return merged


def _acting_actor_id(turn: dict[str, Any]) -> str | None:
    raw_text = str(turn.get('raw_text') or '').strip()
    tokens = raw_text.split()
    if len(tokens) >= 2 and _looks_like_actor_id(tokens[1]):
        return tokens[1]
    state_before = turn.get('state_before')
    if isinstance(state_before, dict):
        active_actor_id = state_before.get('active_actor_id')
        if isinstance(active_actor_id, str) and _looks_like_actor_id(active_actor_id):
            return active_actor_id
    return None


def _target_actor_ids(turn: dict[str, Any]) -> list[str]:
    raw_text = str(turn.get('raw_text') or '').strip()
    tokens = raw_text.split()
    targets: list[str] = []
    for token in tokens[2:]:
        cleaned = token.strip(',.')
        if _looks_like_actor_id(cleaned):
            targets.append(cleaned)
    return targets


def _looks_like_actor_id(value: str) -> bool:
    return value.startswith(('player-', 'monster-'))


def _credit_scope(*, action_reward: float, terminal_reward: float) -> str:
    if terminal_reward and action_reward:
        return 'action_and_team_terminal'
    if terminal_reward:
        return 'team_terminal'
    return 'action'


def _reward_total(record: dict[str, Any] | None) -> float:
    if not isinstance(record, dict):
        return 0.0
    metadata = record.get('metadata')
    if isinstance(metadata, dict) and isinstance(metadata.get('reward_total'), (int, float)):
        return float(metadata['reward_total'])
    components = record.get('reward_components')
    if not isinstance(components, dict):
        return 0.0
    return float(sum(float(value) for value in components.values() if isinstance(value, (int, float))))


def _terminal_success(record: dict[str, Any] | None) -> bool | None:
    if not isinstance(record, dict):
        return None
    metadata = record.get('metadata')
    if not isinstance(metadata, dict):
        return None
    success = metadata.get('success')
    return bool(success) if success is not None else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None
