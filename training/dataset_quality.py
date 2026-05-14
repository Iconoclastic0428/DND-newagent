from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def validate_transition_dataset(path: str | Path) -> dict[str, Any]:
    dataset_path = Path(path)
    rows, issues = _load_jsonl_rows(dataset_path)
    issues.extend(_empty_dataset_issues(rows, dataset_type='training_transitions'))
    issues.extend(_duplicate_id_issues(rows, id_key='sample_id', dataset_type='training_transitions'))
    for index, row in enumerate(rows, start=1):
        issues.extend(_required_string_issues(row, line=index, keys=('sample_id', 'agent_id', 'source', 'runtime_mode', 'action')))
        issues.extend(_required_number_issues(row, line=index, keys=('reward', 'action_reward', 'terminal_reward')))
        issues.extend(_required_dict_issues(row, line=index, keys=('observation', 'reward_channels')))
        if not isinstance(row.get('available_actions'), list):
            issues.append(_issue('warn', 'missing_available_actions', f'Line {index} has no available_actions list.', line=index))
    counts = {
        'source_counts': _counter_dict(row.get('source') for row in rows),
        'agent_counts': _counter_dict(row.get('agent_id') for row in rows),
        'runtime_mode_counts': _counter_dict(row.get('runtime_mode') for row in rows),
        'error_count': sum(1 for row in rows if row.get('error')),
    }
    issues.extend(_imbalance_issues(counts['source_counts'], label='source'))
    issues.extend(_imbalance_issues(counts['agent_counts'], label='agent'))
    return _quality_report(
        dataset_type='training_transitions',
        dataset_path=dataset_path,
        record_count=len(rows),
        issues=issues,
        counts=counts,
    )


def validate_preference_dataset(path: str | Path) -> dict[str, Any]:
    dataset_path = Path(path)
    rows, issues = _load_jsonl_rows(dataset_path)
    issues.extend(_empty_dataset_issues(rows, dataset_type='preference_pairs'))
    issues.extend(_duplicate_id_issues(rows, id_key='pair_id', dataset_type='preference_pairs'))
    for index, row in enumerate(rows, start=1):
        issues.extend(_required_string_issues(row, line=index, keys=('pair_id', 'prompt', 'chosen', 'rejected')))
        issues.extend(_required_number_issues(row, line=index, keys=('chosen_reward', 'rejected_reward', 'reward_gap')))
        if isinstance(row.get('reward_gap'), (int, float)) and float(row['reward_gap']) <= 0:
            issues.append(_issue('fail', 'non_positive_reward_gap', f'Line {index} has non-positive reward_gap.', line=index))
        chosen_metadata = row.get('chosen_metadata')
        rejected_metadata = row.get('rejected_metadata')
        if not isinstance(chosen_metadata, dict) or not isinstance(rejected_metadata, dict):
            issues.append(_issue('warn', 'missing_pair_metadata', f'Line {index} is missing chosen/rejected metadata.', line=index))
    counts = {
        'scenario_counts': _counter_dict(row.get('scenario_id') for row in rows),
        'runtime_mode_counts': _counter_dict(row.get('runtime_mode') for row in rows),
        'actor_counts': _counter_dict(row.get('acting_actor_id') for row in rows),
    }
    issues.extend(_imbalance_issues(counts['runtime_mode_counts'], label='runtime_mode'))
    issues.extend(_imbalance_issues(counts['actor_counts'], label='actor'))
    return _quality_report(
        dataset_type='preference_pairs',
        dataset_path=dataset_path,
        record_count=len(rows),
        issues=issues,
        counts=counts,
    )


def write_dataset_quality_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def _load_jsonl_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    if not path.exists():
        return rows, [_issue('fail', 'missing_dataset', f'Dataset file does not exist: {path}')]
    for line_number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(_issue('fail', 'invalid_jsonl', f'Line {line_number} is invalid JSON: {exc}', line=line_number))
            continue
        if not isinstance(row, dict):
            issues.append(_issue('fail', 'non_object_row', f'Line {line_number} is not a JSON object.', line=line_number))
            continue
        rows.append(row)
    return rows, issues


def _empty_dataset_issues(rows: list[dict[str, Any]], *, dataset_type: str) -> list[dict[str, Any]]:
    if rows:
        return []
    return [_issue('fail', 'empty_dataset', f'{dataset_type} dataset has no records.')]


def _duplicate_id_issues(rows: list[dict[str, Any]], *, id_key: str, dataset_type: str) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(id_key)) for row in rows if row.get(id_key))
    duplicates = sorted(identifier for identifier, count in counts.items() if count > 1)
    if not duplicates:
        return []
    return [
        _issue(
            'fail',
            'duplicate_id',
            f'{dataset_type} dataset has duplicate {id_key} values.',
            details={'id_key': id_key, 'duplicates': duplicates[:20], 'duplicate_count': len(duplicates)},
        )
    ]


def _required_string_issues(row: dict[str, Any], *, line: int, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in keys:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(_issue('fail', 'missing_required_string', f'Line {line} is missing non-empty string field {key!r}.', line=line, details={'field': key}))
    return issues


def _required_number_issues(row: dict[str, Any], *, line: int, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in keys:
        if not isinstance(row.get(key), (int, float)):
            issues.append(_issue('fail', 'missing_required_number', f'Line {line} is missing numeric field {key!r}.', line=line, details={'field': key}))
    return issues


def _required_dict_issues(row: dict[str, Any], *, line: int, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in keys:
        if not isinstance(row.get(key), dict):
            issues.append(_issue('fail', 'missing_required_object', f'Line {line} is missing object field {key!r}.', line=line, details={'field': key}))
    return issues


def _imbalance_issues(counts: dict[str, int], *, label: str) -> list[dict[str, Any]]:
    total = sum(counts.values())
    if total < 20 or len(counts) <= 1:
        return []
    top_key, top_count = max(counts.items(), key=lambda item: item[1])
    share = top_count / total
    if share < 0.95:
        return []
    return [
        _issue(
            'warn',
            f'{label}_imbalance',
            f'{label} distribution is highly imbalanced: {top_key} covers {share:.1%} of records.',
            details={'label': label, 'top_key': top_key, 'top_count': top_count, 'total': total, 'share': share},
        )
    ]


def _quality_report(
    *,
    dataset_type: str,
    dataset_path: Path,
    record_count: int,
    issues: list[dict[str, Any]],
    counts: dict[str, Any],
) -> dict[str, Any]:
    fail_count = sum(1 for issue in issues if issue['severity'] == 'fail')
    warn_count = sum(1 for issue in issues if issue['severity'] == 'warn')
    status = 'fail' if fail_count else 'warn' if warn_count else 'pass'
    return {
        'dataset_type': dataset_type,
        'dataset_path': str(dataset_path),
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'record_count': record_count,
        'status': status,
        'fail_count': fail_count,
        'warn_count': warn_count,
        'issues': issues,
        'counts': counts,
    }


def _counter_dict(values: Any) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for value in values:
        if value is None:
            continue
        counts[str(value)] += 1
    return dict(sorted(counts.items()))


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    line: int | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue = {
        'severity': severity,
        'code': code,
        'message': message,
    }
    if line is not None:
        issue['line'] = line
    if details:
        issue['details'] = details
    return issue
