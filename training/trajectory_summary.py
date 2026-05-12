from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
from typing import Any, Iterable


def load_trajectory_records(path: str | Path) -> list[dict[str, Any]]:
    trajectory_path = Path(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(trajectory_path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid trajectory JSON on line {line_number} of {trajectory_path}: {exc}') from exc
        if not isinstance(record, dict):
            raise ValueError(f'Trajectory line {line_number} of {trajectory_path} is not a JSON object.')
        records.append(record)
    return records


def summarize_trajectory(path_or_records: str | Path | Iterable[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(path_or_records, (str, Path)):
        records = load_trajectory_records(path_or_records)
        trajectory_path = str(Path(path_or_records))
    else:
        records = list(path_or_records)
        trajectory_path = None
    if not records:
        return {
            'trajectory_path': trajectory_path,
            'episode_id': None,
            'scenario_id': None,
            'record_count': 0,
            'turn_count': 0,
            'invalid_action_count': 0,
            'total_reward': 0.0,
            'success': False,
            'terminal': None,
            'action_count_by_agent': {},
            'action_count_by_source': {},
            'error_messages': [],
        }

    turns = [record for record in records if record.get('record_type') == 'turn']
    terminal = next((record for record in reversed(records) if record.get('record_type') == 'episode_completed'), None)
    errors = [str(record.get('error')) for record in turns if record.get('error')]
    final_state = _last_state_after(turns)
    terminal_metadata = terminal.get('metadata') if isinstance(terminal, dict) and isinstance(terminal.get('metadata'), dict) else {}
    total_reward = sum(_reward_total(record) for record in records)
    party_hp_ratio = _party_hp_ratio(terminal_metadata or final_state)

    return {
        'trajectory_path': trajectory_path,
        'episode_id': records[0].get('episode_id'),
        'scenario_id': records[0].get('scenario_id'),
        'record_count': len(records),
        'turn_count': len(turns),
        'invalid_action_count': len(errors),
        'total_reward': total_reward,
        'success': bool(terminal_metadata.get('success')) if terminal is not None else False,
        'terminal': {
            'runtime_mode': terminal.get('runtime_mode') if terminal is not None else None,
            'reward_total': _reward_total(terminal) if terminal is not None else 0.0,
            'winning_side': terminal_metadata.get('winning_side'),
            'round_number': terminal_metadata.get('round_number'),
            'party_hp_ratio': party_hp_ratio,
            'living_party_count': terminal_metadata.get('living_party_count'),
            'living_monster_count': terminal_metadata.get('living_monster_count'),
        } if terminal is not None else None,
        'final_runtime_mode': (terminal.get('runtime_mode') if terminal is not None else final_state.get('runtime_mode')),
        'final_scene_id': final_state.get('scene_id'),
        'final_party_hp_ratio': party_hp_ratio,
        'action_count_by_agent': dict(Counter(str(record.get('agent_id')) for record in turns if record.get('agent_id'))),
        'action_count_by_source': dict(Counter(str(record.get('source')) for record in turns if record.get('source'))),
        'error_messages': errors,
    }


def summarize_batch(episode_summaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    summaries = list(episode_summaries)
    episode_count = len(summaries)
    success_count = sum(1 for summary in summaries if summary.get('success'))
    return {
        'episodes': episode_count,
        'successes': success_count,
        'success_rate': success_count / episode_count if episode_count else 0.0,
        'avg_reward': _average(summary.get('total_reward') for summary in summaries),
        'avg_invalid_actions': _average(summary.get('invalid_action_count') for summary in summaries),
        'avg_turns': _average(summary.get('turn_count') for summary in summaries),
        'avg_party_hp_remaining': _average(
            summary.get('final_party_hp_ratio')
            for summary in summaries
            if summary.get('final_party_hp_ratio') is not None
        ),
        'common_failure_modes': _common_failure_modes(summaries),
        'episode_summaries': summaries,
    }


def _reward_total(record: dict[str, Any]) -> float:
    metadata = record.get('metadata')
    if isinstance(metadata, dict) and isinstance(metadata.get('reward_total'), (int, float)):
        return float(metadata['reward_total'])
    components = record.get('reward_components')
    if not isinstance(components, dict):
        return 0.0
    return float(sum(float(value) for value in components.values() if isinstance(value, (int, float))))


def _last_state_after(turns: list[dict[str, Any]]) -> dict[str, Any]:
    for record in reversed(turns):
        state_after = record.get('state_after')
        if isinstance(state_after, dict):
            return state_after
    return {}


def _party_hp_ratio(state: dict[str, Any]) -> float | None:
    current = state.get('party_hp_current')
    maximum = state.get('party_hp_max')
    if not isinstance(current, (int, float)) or not isinstance(maximum, (int, float)) or maximum <= 0:
        return None
    return max(0.0, float(current)) / float(maximum)


def _average(values: Iterable[Any]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return 0.0
    return sum(numeric) / len(numeric)


def _common_failure_modes(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for summary in summaries:
        for message in summary.get('error_messages') or ():
            counter[str(message)] += 1
    return [
        {'message': message, 'count': count}
        for message, count in counter.most_common(10)
    ]
