from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Iterable


BatchEntry = tuple[str, dict[str, Any]]


def load_batch_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    try:
        report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid batch report JSON at {report_path}: {exc}') from exc
    if not isinstance(report, dict):
        raise ValueError(f'Batch report at {report_path} must be a JSON object.')
    loaded = dict(report)
    loaded['_report_path'] = str(report_path)
    return loaded


def compare_policy_batches(entries: Iterable[BatchEntry]) -> dict[str, Any]:
    rows = [_comparison_row(label=label, report=report) for label, report in entries]
    leaderboard = _ranked_rows(rows)
    reward_channels = sorted({channel for row in rows for channel in row.get('reward_by_channel', {})})
    return {
        'comparison_count': len(rows),
        'scenario_ids': sorted({str(row.get('scenario_id')) for row in rows if row.get('scenario_id')}),
        'reward_channels': reward_channels,
        'rows': rows,
        'leaderboard': leaderboard,
        'best_by_metric': _best_by_metric(rows),
    }


def write_policy_comparison_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def _comparison_row(*, label: str, report: dict[str, Any]) -> dict[str, Any]:
    evaluation = _policy_evaluation(report)
    row = {
        'label': label,
        'batch_id': report.get('batch_id'),
        'report_path': report.get('_report_path') or report.get('report_path'),
        'scenario_id': report.get('scenario_id'),
        'policy': report.get('policy'),
        'llm_player_controllers': list(report.get('llm_player_controllers') or []),
        'episodes': _number(report.get('episodes')),
        'successes': _number(report.get('successes')),
        'success_rate': _number(report.get('success_rate')),
        'avg_reward': _number(report.get('avg_reward')),
        'avg_invalid_actions': _number(report.get('avg_invalid_actions')),
        'avg_turns': _number(report.get('avg_turns')),
        'avg_party_hp_remaining': _number(report.get('avg_party_hp_remaining')),
        'transition_count': _number(report.get('transition_count') or evaluation.get('transition_count')),
        'preference_pair_count': _number(report.get('preference_pair_count')),
        'invalid_transition_rate': _number(evaluation.get('invalid_transition_rate')),
        'total_reward': _number(evaluation.get('total_reward')),
        'avg_reward_per_transition': _number(evaluation.get('avg_reward_per_transition')),
        'total_action_reward': _number(evaluation.get('total_action_reward')),
        'total_terminal_reward': _number(evaluation.get('total_terminal_reward')),
        'reward_by_channel': _number_map(evaluation.get('reward_by_channel')),
        'avg_reward_by_channel': _number_map(evaluation.get('avg_reward_by_channel')),
        'action_count_by_source': _number_map(evaluation.get('action_count_by_source')),
        'action_count_by_runtime_mode': _number_map(evaluation.get('action_count_by_runtime_mode')),
    }
    row['comparison_score'] = _comparison_score(row)
    return row


def _policy_evaluation(report: dict[str, Any]) -> dict[str, Any]:
    evaluation = report.get('policy_evaluation')
    if isinstance(evaluation, dict):
        return evaluation
    evaluation_path = report.get('evaluation_path')
    if not isinstance(evaluation_path, str) or not evaluation_path:
        return {}
    path = Path(evaluation_path)
    if not path.is_absolute() and isinstance(report.get('_report_path'), str):
        report_dir = Path(str(report['_report_path'])).parent
        candidate = report_dir / path
        if candidate.exists():
            path = candidate
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _ranked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (
            row['success_rate'],
            row['avg_reward'],
            -row['avg_invalid_actions'],
            -row['invalid_transition_rate'],
            row['avg_party_hp_remaining'],
        ),
        reverse=True,
    )
    return [
        {'rank': index, **row}
        for index, row in enumerate(ranked, start=1)
    ]


def _best_by_metric(rows: list[dict[str, Any]]) -> dict[str, str | None]:
    if not rows:
        return {
            'success_rate': None,
            'avg_reward': None,
            'lowest_invalid_actions': None,
            'avg_party_hp_remaining': None,
        }
    return {
        'success_rate': max(rows, key=lambda row: row['success_rate'])['label'],
        'avg_reward': max(rows, key=lambda row: row['avg_reward'])['label'],
        'lowest_invalid_actions': min(rows, key=lambda row: row['avg_invalid_actions'])['label'],
        'avg_party_hp_remaining': max(rows, key=lambda row: row['avg_party_hp_remaining'])['label'],
    }


def _comparison_score(row: dict[str, Any]) -> float:
    return (
        row['success_rate'] * 100.0
        + row['avg_reward']
        + row['avg_party_hp_remaining']
        - row['avg_invalid_actions'] * 5.0
        - row['invalid_transition_rate'] * 10.0
    )


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _number_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if isinstance(item, (int, float))
    }
