from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable


def build_training_readiness_report(
    input_paths: Iterable[str | Path],
    *,
    benchmark_history_path: str | Path | None = None,
) -> dict[str, Any]:
    paths = tuple(Path(path) for path in input_paths)
    if not paths:
        raise ValueError('At least one input path must be provided.')

    collection_reports = _load_collection_reports(paths)
    manifests = _load_manifest_reports(paths)
    quality_reports = _load_quality_reports(paths)
    history_paths = _discover_benchmark_history_paths(paths, explicit_path=benchmark_history_path)
    history_entries = _load_benchmark_history_entries(history_paths)

    datasets = _dataset_summaries(
        collection_reports=collection_reports,
        manifests=manifests,
        quality_reports=quality_reports,
    )
    issues = _readiness_issues(datasets=datasets, history_entries=history_entries)
    recommendations = _readiness_recommendations(datasets=datasets, issues=issues)
    blocker_count = sum(1 for issue in issues if issue['severity'] == 'blocker')
    warning_count = sum(1 for issue in issues if issue['severity'] == 'warn')
    status = 'blocked' if blocker_count else 'needs_attention' if warning_count else 'ready'

    return {
        'schema_version': 'dnd-agents-training-readiness-v1',
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'status': status,
        'blocker_count': blocker_count,
        'warning_count': warning_count,
        'input_paths': [str(path) for path in paths],
        'collection_report_count': len(collection_reports),
        'dataset_count': len(datasets),
        'total_record_count': sum(_int(dataset.get('record_count')) for dataset in datasets),
        'datasets': datasets,
        'benchmark_history': _benchmark_history_summary(history_paths, history_entries),
        'issues': issues,
        'recommendations': recommendations,
    }


def write_training_readiness_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def render_training_readiness_markdown(report: dict[str, Any]) -> str:
    lines = [
        '# Training Readiness Report',
        '',
        f'Status: **{_markdown_text(report.get("status", "unknown"))}**',
        '',
        f'Datasets: {_format_int(report.get("dataset_count"))}',
        f'Total records: {_format_int(report.get("total_record_count"))}',
        f'Blockers: {_format_int(report.get("blocker_count"))}',
        f'Warnings: {_format_int(report.get("warning_count"))}',
        '',
        '## Datasets',
        '',
        '| Dataset | Type | Records | Manifest | Quality | File |',
        '| --- | --- | ---: | --- | --- | --- |',
    ]
    datasets = report.get('datasets') if isinstance(report.get('datasets'), list) else []
    if datasets:
        for dataset in datasets:
            lines.append(
                '| '
                + ' | '.join([
                    _markdown_text(dataset.get('dataset_name') or 'n/a'),
                    _markdown_text(dataset.get('dataset_type') or 'n/a'),
                    _format_int(dataset.get('record_count')),
                    _markdown_text(dataset.get('manifest_status') or 'missing'),
                    _markdown_text(dataset.get('quality_status') or 'missing'),
                    _markdown_text(dataset.get('dataset_path') or 'n/a'),
                ])
                + ' |'
            )
    else:
        lines.append('| n/a | n/a | 0 | missing | missing | n/a |')

    lines.extend([
        '',
        '## Coverage',
        '',
        '| Dataset | Counts | Quality Issues |',
        '| --- | --- | --- |',
    ])
    if datasets:
        for dataset in datasets:
            lines.append(
                '| '
                + ' | '.join([
                    _markdown_text(dataset.get('dataset_name') or 'n/a'),
                    _markdown_text(_coverage_summary(dataset.get('quality_counts'))),
                    _markdown_text(_quality_issue_summary(dataset.get('quality_issues'))),
                ])
                + ' |'
            )
    else:
        lines.append('| n/a | n/a | n/a |')

    history = report.get('benchmark_history') if isinstance(report.get('benchmark_history'), dict) else {}
    latest = history.get('latest') if isinstance(history.get('latest'), dict) else {}
    lines.extend([
        '',
        '## Benchmark History',
        '',
        f'History entries: {_format_int(history.get("entry_count"))}',
        f'Latest benchmark: {_markdown_text(latest.get("benchmark_id") or "n/a")}',
        f'Latest scenario: {_markdown_text(latest.get("scenario_id") or "n/a")}',
        '',
        '## Recommendations',
        '',
    ])
    recommendations = report.get('recommendations') if isinstance(report.get('recommendations'), list) else []
    if recommendations:
        for recommendation in recommendations:
            lines.append(f'- {_markdown_text(recommendation)}')
    else:
        lines.append('- No follow-up recommendations were generated.')
    lines.extend([
        '',
        '## Issues',
        '',
    ])
    issues = report.get('issues') if isinstance(report.get('issues'), list) else []
    if not issues:
        lines.append('- No readiness issues were found.')
    for issue in issues:
        lines.append(
            f'- {_markdown_text(issue.get("severity"))}: '
            f'{_markdown_text(issue.get("code"))} - '
            f'{_markdown_text(issue.get("message"))}'
        )
    lines.append('')
    return '\n'.join(lines)


def write_training_readiness_markdown(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_training_readiness_markdown(report), encoding='utf-8')
    return path


def _load_collection_reports(input_paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in _discover_named_files(input_paths, 'dataset_collection_report.json'):
        report = _load_json_object(path, label='dataset collection report')
        report['_report_path'] = str(path)
        reports.append(report)
    return reports


def _load_manifest_reports(input_paths: tuple[Path, ...]) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for path in _discover_suffix_files(input_paths, '.manifest.json'):
        manifest = _load_json_object(path, label='dataset manifest')
        manifest['_manifest_path'] = str(path)
        dataset_path = manifest.get('dataset_path')
        if isinstance(dataset_path, str) and dataset_path:
            manifests[_path_key(Path(dataset_path))] = manifest
    return manifests


def _load_quality_reports(input_paths: tuple[Path, ...]) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for path in _discover_suffix_files(input_paths, '.quality.json'):
        report = _load_json_object(path, label='dataset quality report')
        report['_quality_path'] = str(path)
        dataset_path = report.get('dataset_path')
        if isinstance(dataset_path, str) and dataset_path:
            reports[_path_key(Path(dataset_path))] = report
    return reports


def _dataset_summaries(
    *,
    collection_reports: list[dict[str, Any]],
    manifests: dict[str, dict[str, Any]],
    quality_reports: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}

    if not collection_reports:
        for manifest in manifests.values():
            dataset_path = Path(str(manifest['dataset_path']))
            entries.setdefault(_path_key(dataset_path), {'dataset_path': str(dataset_path)})

    for collection in collection_reports:
        for dataset_key, manifest_key, quality_key in (
            ('transition_path', 'transition_manifest_path', 'transition_quality_path'),
            ('preference_path', 'preference_manifest_path', 'preference_quality_path'),
        ):
            dataset_path_value = collection.get(dataset_key)
            if not isinstance(dataset_path_value, str) or not dataset_path_value:
                continue
            dataset_path = Path(dataset_path_value)
            entry = entries.setdefault(_path_key(dataset_path), {'dataset_path': str(dataset_path)})
            entry['collection_report_path'] = collection.get('_report_path')
            entry['collection_dataset_key'] = dataset_key
            if isinstance(collection.get(manifest_key), str):
                entry['collection_manifest_path'] = collection[manifest_key]
            if isinstance(collection.get(quality_key), str):
                entry['collection_quality_path'] = collection[quality_key]

    for key, entry in entries.items():
        manifest = manifests.get(key) or _load_optional_report(entry.get('collection_manifest_path'), label='dataset manifest')
        quality = quality_reports.get(key) or _load_optional_report(entry.get('collection_quality_path'), label='dataset quality report')
        dataset_path = Path(str(entry['dataset_path']))
        dataset_name = dataset_path.name
        dataset_type = _dataset_type(dataset_name=dataset_name, manifest=manifest)
        quality_counts = quality.get('counts') if quality and isinstance(quality.get('counts'), dict) else {}
        quality_issues = quality.get('issues') if quality and isinstance(quality.get('issues'), list) else []
        record_count = _record_count(dataset_path=dataset_path, manifest=manifest, quality=quality)
        entry.update({
            'dataset_name': dataset_name,
            'dataset_type': dataset_type,
            'record_count': record_count,
            'dataset_exists': dataset_path.exists(),
            'manifest_status': 'present' if manifest else 'missing',
            'manifest_path': manifest.get('_manifest_path') if manifest else entry.get('collection_manifest_path'),
            'quality_status': quality.get('status') if quality else 'missing',
            'quality_path': quality.get('_quality_path') if quality else entry.get('collection_quality_path'),
            'quality_fail_count': _int(quality.get('fail_count')) if quality else None,
            'quality_warn_count': _int(quality.get('warn_count')) if quality else None,
            'quality_counts': quality_counts,
            'quality_issues': _quality_issue_summaries(quality_issues),
        })

    return sorted(entries.values(), key=lambda item: (str(item.get('dataset_type')), str(item.get('dataset_path'))))


def _readiness_issues(*, datasets: list[dict[str, Any]], history_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not datasets:
        issues.append(_issue('blocker', 'no_datasets', 'No dataset manifests or collection report datasets were found.'))
    for dataset in datasets:
        dataset_name = str(dataset.get('dataset_name') or dataset.get('dataset_path') or 'dataset')
        if not dataset.get('dataset_exists'):
            issues.append(_issue('blocker', 'missing_dataset_file', f'{dataset_name} does not exist.', dataset=dataset_name))
        if dataset.get('manifest_status') != 'present':
            issues.append(_issue('blocker', 'missing_manifest', f'{dataset_name} has no dataset manifest.', dataset=dataset_name))
        if _int(dataset.get('record_count')) <= 0:
            issues.append(_issue('blocker', 'empty_dataset', f'{dataset_name} has no records.', dataset=dataset_name))
        quality_status = dataset.get('quality_status')
        if quality_status == 'missing':
            issues.append(_issue('warn', 'missing_quality_report', f'{dataset_name} has no quality report.', dataset=dataset_name))
        elif quality_status == 'fail':
            issues.append(_issue('blocker', 'quality_failed', f'{dataset_name} has failing quality checks.', dataset=dataset_name))
        elif quality_status == 'warn':
            issues.append(_issue('warn', 'quality_warning', f'{dataset_name} has quality warnings.', dataset=dataset_name))
    if not history_entries:
        issues.append(_issue('warn', 'missing_benchmark_history', 'No benchmark history entries were found.'))
    return issues


def _readiness_recommendations(*, datasets: list[dict[str, Any]], issues: list[dict[str, Any]]) -> list[str]:
    recommendations: list[str] = []
    issue_codes = {str(issue.get('code')) for issue in issues}
    if 'no_datasets' in issue_codes:
        recommendations.append('Run policy benchmarks and collect them with user-test\\collect_training_datasets.py before training.')
    if 'missing_benchmark_history' in issue_codes:
        recommendations.append('Run user-test\\run_policy_benchmark.py so readiness can tie datasets back to benchmark history.')
    for dataset in datasets:
        dataset_name = str(dataset.get('dataset_name') or dataset.get('dataset_path') or 'dataset')
        if dataset.get('quality_status') == 'missing':
            recommendations.append(f'Generate a quality report for {dataset_name} before using it for training.')
        if dataset.get('quality_status') == 'fail':
            recommendations.append(f'Fix failing quality checks for {dataset_name} before training.')
        for issue in dataset.get('quality_issues') or []:
            if not isinstance(issue, dict):
                continue
            recommendation = _quality_issue_recommendation(dataset_name=dataset_name, issue=issue)
            if recommendation:
                recommendations.append(recommendation)
    return _unique_strings(recommendations)


def _quality_issue_recommendation(*, dataset_name: str, issue: dict[str, Any]) -> str | None:
    code = issue.get('code')
    details = issue.get('details') if isinstance(issue.get('details'), dict) else {}
    if code == 'runtime_mode_imbalance':
        top_key = str(details.get('top_key') or 'one runtime mode')
        share = details.get('share')
        share_text = _format_percent(share) if isinstance(share, (int, float)) else 'most'
        return f'Add more non-{top_key} preference examples for {dataset_name}; {top_key} currently covers {share_text} of records.'
    if code == 'actor_imbalance':
        top_key = str(details.get('top_key') or 'one actor')
        share = details.get('share')
        share_text = _format_percent(share) if isinstance(share, (int, float)) else 'most'
        return f'Collect more actions from actors other than {top_key} for {dataset_name}; {top_key} currently covers {share_text} of records.'
    if code == 'source_imbalance':
        top_key = str(details.get('top_key') or 'one source')
        share = details.get('share')
        share_text = _format_percent(share) if isinstance(share, (int, float)) else 'most'
        return f'Collect more data from sources other than {top_key} for {dataset_name}; {top_key} currently covers {share_text} of records.'
    if code == 'duplicate_id':
        return f'Regenerate {dataset_name} with unique row IDs before training.'
    if code == 'empty_dataset':
        return f'Collect at least one record for {dataset_name} before training.'
    return None


def _quality_issue_summaries(issues: list[Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        summary = {
            'severity': issue.get('severity'),
            'code': issue.get('code'),
            'message': issue.get('message'),
        }
        if isinstance(issue.get('details'), dict):
            summary['details'] = issue['details']
        summaries.append(summary)
    return summaries


def _discover_benchmark_history_paths(input_paths: tuple[Path, ...], *, explicit_path: str | Path | None) -> list[Path]:
    if explicit_path is not None:
        path = Path(explicit_path)
        return [path] if path.exists() else []
    return _discover_named_files(input_paths, 'benchmark_history.jsonl')


def _load_benchmark_history_entries(paths: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'Invalid benchmark history JSONL at {path}:{line_number}: {exc}') from exc
            if not isinstance(entry, dict):
                raise ValueError(f'Benchmark history row at {path}:{line_number} must be a JSON object.')
            entry['_history_path'] = str(path)
            entries.append(entry)
    return entries


def _benchmark_history_summary(paths: list[Path], entries: list[dict[str, Any]]) -> dict[str, Any]:
    latest = entries[-1] if entries else None
    return {
        'paths': [str(path) for path in paths],
        'entry_count': len(entries),
        'latest': _latest_benchmark_summary(latest) if latest else None,
    }


def _latest_benchmark_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        'benchmark_id': entry.get('benchmark_id'),
        'scenario_id': entry.get('scenario_id'),
        'created_at': entry.get('created_at'),
        'seed_count': entry.get('seed_count'),
        'policy_count': len(entry.get('policies') or []) if isinstance(entry.get('policies'), list) else None,
    }


def _discover_named_files(input_paths: tuple[Path, ...], name: str) -> list[Path]:
    paths: list[Path] = []
    for input_path in input_paths:
        if input_path.is_file() and input_path.name == name:
            paths.append(input_path)
        elif input_path.is_dir():
            paths.extend(sorted(input_path.rglob(name)))
    return _unique_paths(paths)


def _discover_suffix_files(input_paths: tuple[Path, ...], suffix: str) -> list[Path]:
    paths: list[Path] = []
    for input_path in input_paths:
        if input_path.is_file() and input_path.name.endswith(suffix):
            paths.append(input_path)
        elif input_path.is_dir():
            paths.extend(sorted(path for path in input_path.rglob(f'*{suffix}') if path.is_file()))
    return _unique_paths(paths)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid {label} JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise ValueError(f'{label} at {path} must be a JSON object.')
    return payload


def _load_optional_report(path_value: Any, *, label: str) -> dict[str, Any] | None:
    if not isinstance(path_value, str) or not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    report = _load_json_object(path, label=label)
    marker = '_manifest_path' if label == 'dataset manifest' else '_quality_path'
    report[marker] = str(path)
    return report


def _dataset_type(*, dataset_name: str, manifest: dict[str, Any] | None) -> str:
    if manifest and isinstance(manifest.get('dataset_type'), str):
        return str(manifest['dataset_type'])
    if 'preference' in dataset_name:
        return 'preference_pairs'
    if 'transition' in dataset_name:
        return 'training_transitions'
    return 'unknown'


def _record_count(*, dataset_path: Path, manifest: dict[str, Any] | None, quality: dict[str, Any] | None) -> int:
    if manifest and isinstance(manifest.get('record_count'), int):
        return int(manifest['record_count'])
    if quality and isinstance(quality.get('record_count'), int):
        return int(quality['record_count'])
    if not dataset_path.exists():
        return 0
    return sum(1 for line in dataset_path.read_text(encoding='utf-8-sig').splitlines() if line.strip())


def _path_key(path: Path) -> str:
    return str(path.resolve()) if path.exists() else str(path)


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _issue(severity: str, code: str, message: str, *, dataset: str | None = None) -> dict[str, Any]:
    issue = {
        'severity': severity,
        'code': code,
        'message': message,
    }
    if dataset is not None:
        issue['dataset'] = dataset
    return issue


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_percent(value: float) -> str:
    return f'{value:.1%}'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')


def _coverage_summary(counts: Any) -> str:
    if not isinstance(counts, dict) or not counts:
        return 'n/a'
    parts: list[str] = []
    for label in ('runtime_mode_counts', 'source_counts', 'actor_counts', 'agent_counts', 'scenario_counts'):
        value = counts.get(label)
        if isinstance(value, dict) and value:
            parts.append(f'{label}: {_compact_counts(value)}')
    return '; '.join(parts) if parts else 'n/a'


def _quality_issue_summary(issues: Any) -> str:
    if not isinstance(issues, list) or not issues:
        return 'none'
    codes = [
        str(issue.get('code'))
        for issue in issues
        if isinstance(issue, dict) and issue.get('code')
    ]
    return ', '.join(codes) if codes else 'none'


def _compact_counts(counts: dict[str, Any]) -> str:
    return ', '.join(
        f'{key}={value}'
        for key, value in sorted(counts.items(), key=lambda item: str(item[0]))
    )


def _unique_strings(values: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
