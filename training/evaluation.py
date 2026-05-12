from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
from typing import Any, Iterable


def load_transition_records(path: str | Path) -> list[dict[str, Any]]:
    transition_path = Path(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(transition_path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid transition JSON on line {line_number} of {transition_path}: {exc}') from exc
        if not isinstance(record, dict):
            raise ValueError(f'Transition line {line_number} of {transition_path} is not a JSON object.')
        records.append(record)
    return records


def summarize_policy_evaluation(
    transitions_or_path: str | Path | Iterable[dict[str, Any]],
    *,
    episode_summaries: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    if isinstance(transitions_or_path, (str, Path)):
        transitions = load_transition_records(transitions_or_path)
        transition_path = str(Path(transitions_or_path))
    else:
        transitions = list(transitions_or_path)
        transition_path = None

    summaries = list(episode_summaries)
    terminal_transitions = [transition for transition in transitions if transition.get('done')]
    successes = _success_count(summaries=summaries, terminal_transitions=terminal_transitions)
    episode_count = len(summaries) if summaries else len(terminal_transitions)
    invalid_count = sum(1 for transition in transitions if transition.get('error'))
    total_reward = sum(_numeric(transition.get('reward')) for transition in transitions)
    total_action_reward = sum(_numeric(transition.get('action_reward')) for transition in transitions)
    total_terminal_reward = sum(_numeric(transition.get('terminal_reward')) for transition in transitions)
    reward_by_channel = _channel_totals(transitions, key='reward_channels')

    return {
        'transition_path': transition_path,
        'transition_count': len(transitions),
        'episode_count': episode_count,
        'successes': successes,
        'success_rate': successes / episode_count if episode_count else 0.0,
        'invalid_transition_count': invalid_count,
        'invalid_transition_rate': invalid_count / len(transitions) if transitions else 0.0,
        'total_reward': total_reward,
        'avg_reward_per_transition': total_reward / len(transitions) if transitions else 0.0,
        'total_action_reward': total_action_reward,
        'total_terminal_reward': total_terminal_reward,
        'reward_by_channel': reward_by_channel,
        'avg_reward_by_channel': {
            channel: value / len(transitions)
            for channel, value in reward_by_channel.items()
        } if transitions else {},
        'action_count_by_agent': dict(Counter(str(transition.get('agent_id')) for transition in transitions if transition.get('agent_id'))),
        'action_count_by_source': dict(Counter(str(transition.get('source')) for transition in transitions if transition.get('source'))),
        'action_count_by_runtime_mode': dict(Counter(str(transition.get('runtime_mode')) for transition in transitions if transition.get('runtime_mode'))),
        'per_agent': _group_summaries(transitions, group_key='agent_id'),
        'per_source': _group_summaries(transitions, group_key='source'),
        'agent_leaderboard': _agent_leaderboard(transitions),
    }


def write_policy_evaluation_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def _success_count(
    *,
    summaries: list[dict[str, Any]],
    terminal_transitions: list[dict[str, Any]],
) -> int:
    if summaries:
        return sum(1 for summary in summaries if summary.get('success'))
    return sum(1 for transition in terminal_transitions if transition.get('success') is True)


def _group_summaries(transitions: list[dict[str, Any]], *, group_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for transition in transitions:
        group_value = transition.get(group_key)
        if group_value is None:
            continue
        groups.setdefault(str(group_value), []).append(transition)
    return {
        group_id: _summarize_transition_group(group_transitions)
        for group_id, group_transitions in sorted(groups.items())
    }


def _summarize_transition_group(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    action_count = len(transitions)
    invalid_count = sum(1 for transition in transitions if transition.get('error'))
    total_reward = sum(_numeric(transition.get('reward')) for transition in transitions)
    action_reward = sum(_numeric(transition.get('action_reward')) for transition in transitions)
    terminal_reward = sum(_numeric(transition.get('terminal_reward')) for transition in transitions)
    return {
        'action_count': action_count,
        'invalid_action_count': invalid_count,
        'invalid_action_rate': invalid_count / action_count if action_count else 0.0,
        'total_reward': total_reward,
        'avg_reward': total_reward / action_count if action_count else 0.0,
        'action_reward': action_reward,
        'terminal_reward': terminal_reward,
        'reward_by_channel': _channel_totals(transitions, key='reward_channels'),
        'action_count_by_source': dict(Counter(str(transition.get('source')) for transition in transitions if transition.get('source'))),
        'action_count_by_runtime_mode': dict(Counter(str(transition.get('runtime_mode')) for transition in transitions if transition.get('runtime_mode'))),
    }


def _agent_leaderboard(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_summaries(transitions, group_key='agent_id')
    rows = [
        {
            'agent_id': agent_id,
            'action_count': summary['action_count'],
            'total_reward': summary['total_reward'],
            'avg_reward': summary['avg_reward'],
            'invalid_action_rate': summary['invalid_action_rate'],
            'reward_by_channel': summary['reward_by_channel'],
        }
        for agent_id, summary in grouped.items()
    ]
    return sorted(rows, key=lambda row: (row['avg_reward'], row['total_reward'], -row['invalid_action_rate']), reverse=True)


def _channel_totals(transitions: Iterable[dict[str, Any]], *, key: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for transition in transitions:
        channels = transition.get(key)
        if not isinstance(channels, dict):
            continue
        for channel, value in channels.items():
            if not isinstance(value, (int, float)):
                continue
            totals[str(channel)] = totals.get(str(channel), 0.0) + float(value)
    return totals


def _numeric(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0
