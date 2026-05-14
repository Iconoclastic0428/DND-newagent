from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from training.readiness_report import build_training_readiness_report


TRAINING_SMOKE_SCHEMA_VERSION = 'dnd-agents-training-smoke-v1'


class TrainingSmokeError(RuntimeError):
    pass


def build_training_smoke_report(
    input_paths: Iterable[str | Path],
    *,
    output_dir: str | Path,
    run_name: str = 'training-smoke',
    transition_sample_limit: int = 5,
    preference_sample_limit: int = 5,
    benchmark_history_path: str | Path | None = None,
    allow_not_ready: bool = False,
) -> dict[str, Any]:
    paths = tuple(Path(path) for path in input_paths)
    if not paths:
        raise TrainingSmokeError('At least one input path must be provided.')
    if transition_sample_limit < 0 or preference_sample_limit < 0:
        raise TrainingSmokeError('Sample limits must be zero or greater.')

    readiness = build_training_readiness_report(paths, benchmark_history_path=benchmark_history_path)
    if readiness.get('status') != 'ready' and not allow_not_ready:
        raise TrainingSmokeError(
            f'Training smoke requires ready datasets; readiness status is {readiness.get("status")!r}.'
        )

    output_path = Path(output_dir)
    run_id = f'{_safe_token(run_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = output_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    datasets = [_smoke_dataset_summary(dataset) for dataset in _datasets(readiness)]
    transition_dataset = _first_dataset(datasets, contains='transition')
    preference_dataset = _first_dataset(datasets, contains='preference')
    transition_samples = _sample_jsonl(transition_dataset.get('dataset_path'), transition_sample_limit) if transition_dataset else []
    preference_samples = _sample_jsonl(preference_dataset.get('dataset_path'), preference_sample_limit) if preference_dataset else []

    report: dict[str, Any] = {
        'schema_version': TRAINING_SMOKE_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_id': run_id,
        'run_name': run_name,
        'run_mode': 'dry_run',
        'output_dir': str(run_dir),
        'input_paths': [str(path) for path in paths],
        'readiness': _readiness_summary(readiness),
        'training_config': {
            'objective': 'dry_run_dataset_handoff',
            'transition_sample_limit': transition_sample_limit,
            'preference_sample_limit': preference_sample_limit,
            'allow_not_ready': allow_not_ready,
        },
        'datasets': datasets,
        'samples': {
            'transition_count': len(transition_samples),
            'preference_count': len(preference_samples),
            'transitions': [_transition_sample(row) for row in transition_samples],
            'preferences': [_preference_sample(row) for row in preference_samples],
        },
        'checks': _smoke_checks(readiness=readiness, datasets=datasets),
    }
    report_path = run_dir / 'training_smoke_report.json'
    markdown_path = run_dir / 'training_smoke_report.md'
    report['report_path'] = str(report_path)
    report['markdown_path'] = str(markdown_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_training_smoke_markdown(report), encoding='utf-8')
    return report


def render_training_smoke_markdown(report: dict[str, Any]) -> str:
    readiness = report.get('readiness') if isinstance(report.get('readiness'), dict) else {}
    lines = [
        '# Training Smoke Report',
        '',
        f'Run: **{_markdown_text(report.get("run_id"))}**',
        f'Mode: {_markdown_text(report.get("run_mode"))}',
        f'Readiness: **{_markdown_text(readiness.get("status"))}**',
        f'Total records: {_format_int(readiness.get("total_record_count"))}',
        '',
        '## Datasets',
        '',
        '| Dataset | Type | Records | Quality | Manifest |',
        '| --- | --- | ---: | --- | --- |',
    ]
    datasets = report.get('datasets') if isinstance(report.get('datasets'), list) else []
    if datasets:
        for dataset in datasets:
            lines.append(
                '| '
                + ' | '.join([
                    _markdown_text(dataset.get('dataset_name')),
                    _markdown_text(dataset.get('dataset_type')),
                    _format_int(dataset.get('record_count')),
                    _markdown_text(dataset.get('quality_status')),
                    _markdown_text(dataset.get('manifest_path')),
                ])
                + ' |'
            )
    else:
        lines.append('| n/a | n/a | 0 | n/a | n/a |')
    samples = report.get('samples') if isinstance(report.get('samples'), dict) else {}
    lines.extend([
        '',
        '## Samples',
        '',
        f'Transition samples: {_format_int(samples.get("transition_count"))}',
        f'Preference samples: {_format_int(samples.get("preference_count"))}',
        '',
        '## Checks',
        '',
    ])
    checks = report.get('checks') if isinstance(report.get('checks'), list) else []
    if checks:
        for check in checks:
            lines.append(f'- {_markdown_text(check.get("status"))}: {_markdown_text(check.get("message"))}')
    else:
        lines.append('- No smoke checks were recorded.')
    lines.append('')
    return '\n'.join(lines)


def _datasets(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    datasets = readiness.get('datasets')
    return [dataset for dataset in datasets if isinstance(dataset, dict)] if isinstance(datasets, list) else []


def _smoke_dataset_summary(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        'dataset_name': dataset.get('dataset_name'),
        'dataset_type': dataset.get('dataset_type'),
        'dataset_path': dataset.get('dataset_path'),
        'record_count': dataset.get('record_count'),
        'manifest_path': dataset.get('manifest_path'),
        'manifest_status': dataset.get('manifest_status'),
        'quality_path': dataset.get('quality_path'),
        'quality_status': dataset.get('quality_status'),
        'quality_counts': dataset.get('quality_counts') if isinstance(dataset.get('quality_counts'), dict) else {},
    }


def _readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        'status': readiness.get('status'),
        'blocker_count': readiness.get('blocker_count'),
        'warning_count': readiness.get('warning_count'),
        'dataset_count': readiness.get('dataset_count'),
        'total_record_count': readiness.get('total_record_count'),
        'benchmark_history': readiness.get('benchmark_history'),
        'issues': readiness.get('issues') if isinstance(readiness.get('issues'), list) else [],
        'recommendations': readiness.get('recommendations') if isinstance(readiness.get('recommendations'), list) else [],
    }


def _first_dataset(datasets: list[dict[str, Any]], *, contains: str) -> dict[str, Any] | None:
    for dataset in datasets:
        dataset_type = str(dataset.get('dataset_type') or dataset.get('dataset_name') or '')
        if contains in dataset_type:
            return dataset
    return None


def _sample_jsonl(path_value: Any, limit: int) -> list[dict[str, Any]]:
    if limit == 0 or not isinstance(path_value, str) or not path_value:
        return []
    path = Path(path_value)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if len(rows) >= limit:
            break
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _transition_sample(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'sample_id': row.get('sample_id'),
        'scenario_id': row.get('scenario_id'),
        'runtime_mode': row.get('runtime_mode'),
        'source': row.get('source'),
        'agent_id': row.get('agent_id'),
        'reward': row.get('reward'),
        'action': _truncate(row.get('action')),
        'reward_channels': row.get('reward_channels') if isinstance(row.get('reward_channels'), dict) else {},
    }


def _preference_sample(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'pair_id': row.get('pair_id'),
        'scenario_id': row.get('scenario_id'),
        'runtime_mode': row.get('runtime_mode'),
        'chosen_reward': row.get('chosen_reward'),
        'rejected_reward': row.get('rejected_reward'),
        'reward_gap': row.get('reward_gap'),
        'chosen': _truncate(row.get('chosen')),
        'rejected': _truncate(row.get('rejected')),
    }


def _smoke_checks(*, readiness: dict[str, Any], datasets: list[dict[str, Any]]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    readiness_status = str(readiness.get('status') or 'unknown')
    checks.append({'status': 'pass' if readiness_status == 'ready' else 'warn', 'message': f'Readiness status is {readiness_status}.'})
    for contains, label in (('transition', 'transition dataset'), ('preference', 'preference dataset')):
        dataset = _first_dataset(datasets, contains=contains)
        if dataset is None:
            checks.append({'status': 'fail', 'message': f'Missing {label}.'})
            continue
        records = dataset.get('record_count')
        status = 'pass' if isinstance(records, int) and records > 0 else 'fail'
        checks.append({'status': status, 'message': f'{label} has {_format_int(records)} records.'})
    return checks


def _truncate(value: Any, *, limit: int = 180) -> str:
    text = '' if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 3] + '...'


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'training-smoke'


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
