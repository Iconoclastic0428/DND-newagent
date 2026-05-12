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
    diagnostics = _comparison_diagnostics(leaderboard)
    return {
        'comparison_count': len(rows),
        'scenario_ids': sorted({str(row.get('scenario_id')) for row in rows if row.get('scenario_id')}),
        'reward_channels': reward_channels,
        'rows': rows,
        'leaderboard': leaderboard,
        'best_by_metric': _best_by_metric(rows),
        'diagnostics': diagnostics,
    }


def write_policy_comparison_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def render_policy_comparison_markdown(report: dict[str, Any]) -> str:
    diagnostics = report.get('diagnostics') if isinstance(report.get('diagnostics'), dict) else {}
    leaderboard = report.get('leaderboard') if isinstance(report.get('leaderboard'), list) else []
    lines = [
        '# Policy Benchmark Summary',
        '',
        f'Winner: {_markdown_text(diagnostics.get("winner_label") or "n/a")}',
        '',
        _markdown_text(diagnostics.get('winner_summary') or 'No benchmark diagnostics are available.'),
        '',
        '## Leaderboard',
        '',
        '| Rank | Policy | Success | Avg Reward | Invalid Actions | Avg Turns | Party HP | Score |',
        '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for row in leaderboard:
        lines.append(
            '| '
            + ' | '.join([
                _format_number(row.get('rank'), digits=0),
                _markdown_text(row.get('label')),
                _format_percent(row.get('success_rate')),
                _format_number(row.get('avg_reward')),
                _format_number(row.get('avg_invalid_actions')),
                _format_number(row.get('avg_turns')),
                _format_percent(row.get('avg_party_hp_remaining')),
                _format_number(row.get('comparison_score')),
            ])
            + ' |'
        )
    lines.extend([
        '',
        '## Why',
        '',
    ])
    policy_notes = diagnostics.get('policy_notes') if isinstance(diagnostics.get('policy_notes'), list) else []
    if not policy_notes:
        lines.append('- No policy diagnostics were generated.')
    for note in policy_notes:
        lines.extend(_render_policy_note(note))
    lines.extend([
        '',
        '## Reward Channels',
        '',
        '| Policy | ' + ' | '.join(_markdown_text(channel) for channel in _reward_channels_for_markdown(report)) + ' |',
        '| --- | ' + ' | '.join('---:' for _channel in _reward_channels_for_markdown(report)) + ' |',
    ])
    channels = _reward_channels_for_markdown(report)
    for row in leaderboard:
        reward_by_channel = row.get('reward_by_channel') if isinstance(row.get('reward_by_channel'), dict) else {}
        lines.append(
            f'| {_markdown_text(row.get("label"))} | '
            + ' | '.join(_format_number(reward_by_channel.get(channel, 0.0)) for channel in channels)
            + ' |'
        )
    lines.append('')
    return '\n'.join(lines)


def write_policy_comparison_markdown(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_policy_comparison_markdown(report), encoding='utf-8')
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


def _comparison_diagnostics(leaderboard: list[dict[str, Any]]) -> dict[str, Any]:
    if not leaderboard:
        return {
            'winner_label': None,
            'runner_up_label': None,
            'winner_summary': 'No policies were compared.',
            'policy_notes': [],
        }
    winner = leaderboard[0]
    runner_up = leaderboard[1] if len(leaderboard) > 1 else None
    policy_notes = [
        _policy_diagnostic_note(row, reference=(runner_up if row is winner and runner_up is not None else winner))
        for row in leaderboard
    ]
    return {
        'winner_label': winner['label'],
        'runner_up_label': runner_up['label'] if runner_up is not None else None,
        'winner_summary': _winner_summary(winner, runner_up),
        'policy_notes': policy_notes,
    }


def _policy_diagnostic_note(row: dict[str, Any], *, reference: dict[str, Any]) -> dict[str, Any]:
    metric_deltas = {
        'comparison_score': row['comparison_score'] - reference['comparison_score'],
        'success_rate': row['success_rate'] - reference['success_rate'],
        'avg_reward': row['avg_reward'] - reference['avg_reward'],
        'avg_invalid_actions': row['avg_invalid_actions'] - reference['avg_invalid_actions'],
        'invalid_transition_rate': row['invalid_transition_rate'] - reference['invalid_transition_rate'],
        'avg_turns': row['avg_turns'] - reference['avg_turns'],
        'avg_party_hp_remaining': row['avg_party_hp_remaining'] - reference['avg_party_hp_remaining'],
    }
    channel_deltas = _reward_channel_deltas(row, reference)
    advantages = _diagnostic_advantages(metric_deltas, channel_deltas)
    tradeoffs = _diagnostic_tradeoffs(metric_deltas, channel_deltas)
    return {
        'label': row['label'],
        'rank': row['rank'],
        'compared_to': reference['label'],
        'headline': _diagnostic_headline(row, reference, advantages, tradeoffs),
        'metric_deltas': metric_deltas,
        'reward_channel_deltas': channel_deltas,
        'advantages': advantages,
        'tradeoffs': tradeoffs,
    }


def _winner_summary(winner: dict[str, Any], runner_up: dict[str, Any] | None) -> str:
    if runner_up is None:
        return f'{winner["label"]} is the only policy in this comparison.'
    note = _policy_diagnostic_note(winner, reference=runner_up)
    reasons = note['advantages'][:2]
    if not reasons:
        return f'{winner["label"]} edges out {runner_up["label"]} on the aggregate comparison score.'
    return f'{winner["label"]} leads {runner_up["label"]}: ' + '; '.join(reasons) + '.'


def _diagnostic_headline(
    row: dict[str, Any],
    reference: dict[str, Any],
    advantages: list[str],
    tradeoffs: list[str],
) -> str:
    if row is reference:
        return f'{row["label"]} is the top-ranked policy.'
    if row['comparison_score'] >= reference['comparison_score']:
        if advantages:
            return f'{row["label"]} leads {reference["label"]}: {advantages[0]}.'
        return f'{row["label"]} leads {reference["label"]} by aggregate score.'
    if tradeoffs:
        return f'{row["label"]} trails {reference["label"]}: {tradeoffs[0]}.'
    return f'{row["label"]} trails {reference["label"]} by aggregate score.'


def _diagnostic_advantages(metric_deltas: dict[str, float], channel_deltas: dict[str, float]) -> list[str]:
    notes: list[str] = []
    if metric_deltas['success_rate'] > 0.001:
        notes.append(f'higher success rate ({_signed(metric_deltas["success_rate"])})')
    if metric_deltas['avg_reward'] > 0.001:
        notes.append(f'higher average reward ({_signed(metric_deltas["avg_reward"])})')
    if metric_deltas['avg_invalid_actions'] < -0.001:
        notes.append(f'fewer invalid actions ({_signed(metric_deltas["avg_invalid_actions"])})')
    if metric_deltas['invalid_transition_rate'] < -0.001:
        notes.append(f'lower invalid transition rate ({_signed(metric_deltas["invalid_transition_rate"])})')
    if metric_deltas['avg_turns'] < -0.001:
        notes.append(f'faster episodes ({_signed(metric_deltas["avg_turns"])} turns)')
    if metric_deltas['avg_party_hp_remaining'] > 0.001:
        notes.append(f'better party survival ({_signed(metric_deltas["avg_party_hp_remaining"])})')
    notes.extend(_top_channel_notes(channel_deltas, positive=True))
    return notes


def _diagnostic_tradeoffs(metric_deltas: dict[str, float], channel_deltas: dict[str, float]) -> list[str]:
    notes: list[str] = []
    if metric_deltas['success_rate'] < -0.001:
        notes.append(f'lower success rate ({_signed(metric_deltas["success_rate"])})')
    if metric_deltas['avg_reward'] < -0.001:
        notes.append(f'lower average reward ({_signed(metric_deltas["avg_reward"])})')
    if metric_deltas['avg_invalid_actions'] > 0.001:
        notes.append(f'more invalid actions ({_signed(metric_deltas["avg_invalid_actions"])})')
    if metric_deltas['invalid_transition_rate'] > 0.001:
        notes.append(f'higher invalid transition rate ({_signed(metric_deltas["invalid_transition_rate"])})')
    if metric_deltas['avg_turns'] > 0.001:
        notes.append(f'slower episodes ({_signed(metric_deltas["avg_turns"])} turns)')
    if metric_deltas['avg_party_hp_remaining'] < -0.001:
        notes.append(f'worse party survival ({_signed(metric_deltas["avg_party_hp_remaining"])})')
    notes.extend(_top_channel_notes(channel_deltas, positive=False))
    return notes


def _top_channel_notes(channel_deltas: dict[str, float], *, positive: bool) -> list[str]:
    filtered = [
        (channel, delta)
        for channel, delta in channel_deltas.items()
        if (delta > 0.05 if positive else delta < -0.05)
    ]
    filtered.sort(key=lambda item: abs(item[1]), reverse=True)
    direction = 'higher' if positive else 'lower'
    return [
        f'{direction} {channel} reward ({_signed(delta)})'
        for channel, delta in filtered[:3]
    ]


def _reward_channel_deltas(row: dict[str, Any], reference: dict[str, Any]) -> dict[str, float]:
    channels = sorted(set(row.get('reward_by_channel', {})) | set(reference.get('reward_by_channel', {})))
    return {
        channel: row.get('reward_by_channel', {}).get(channel, 0.0) - reference.get('reward_by_channel', {}).get(channel, 0.0)
        for channel in channels
    }


def _signed(value: float) -> str:
    return f'{value:+.3f}'


def _render_policy_note(note: dict[str, Any]) -> list[str]:
    lines = [
        f'### Rank {_format_number(note.get("rank"), digits=0)}: {_markdown_text(note.get("label"))}',
        '',
        _markdown_text(note.get('headline') or ''),
    ]
    advantages = note.get('advantages') if isinstance(note.get('advantages'), list) else []
    tradeoffs = note.get('tradeoffs') if isinstance(note.get('tradeoffs'), list) else []
    if advantages:
        lines.extend(['', 'Advantages:'])
        lines.extend(f'- {_markdown_text(item)}' for item in advantages[:5])
    if tradeoffs:
        lines.extend(['', 'Tradeoffs:'])
        lines.extend(f'- {_markdown_text(item)}' for item in tradeoffs[:5])
    lines.append('')
    return lines


def _reward_channels_for_markdown(report: dict[str, Any]) -> list[str]:
    channels = report.get('reward_channels')
    if isinstance(channels, list) and channels:
        return [str(channel) for channel in channels]
    leaderboard = report.get('leaderboard') if isinstance(report.get('leaderboard'), list) else []
    return sorted({
        str(channel)
        for row in leaderboard
        if isinstance(row, dict) and isinstance(row.get('reward_by_channel'), dict)
        for channel in row['reward_by_channel']
    })


def _format_number(value: Any, *, digits: int = 3) -> str:
    if not isinstance(value, (int, float)):
        return '0'
    if digits <= 0:
        return str(int(value))
    return f'{float(value):.{digits}f}'


def _format_percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return '0.0%'
    return f'{float(value) * 100.0:.1f}%'


def _markdown_text(value: Any) -> str:
    text = str(value) if value is not None else ''
    return text.replace('|', '\\|').replace('\n', ' ')


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
