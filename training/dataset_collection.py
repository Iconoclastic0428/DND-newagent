from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from training.dataset_manifest import write_dataset_manifest
from training.dataset_quality import validate_preference_dataset, validate_transition_dataset, write_dataset_quality_report


def collect_training_datasets(
    input_paths: Iterable[str | Path],
    *,
    output_dir: str | Path,
    include_transitions: bool = True,
    include_preferences: bool = True,
) -> dict[str, Any]:
    paths = tuple(Path(path) for path in input_paths)
    if not paths:
        raise ValueError('At least one input path must be provided.')
    if not include_transitions and not include_preferences:
        raise ValueError('At least one dataset type must be included.')
    batch_reports = _discover_batch_reports(paths)
    if not batch_reports:
        raise ValueError('No batch_report.json files were found in the input paths.')

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    collection_id = f'dataset-collection-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    source_summary = _source_summary(batch_reports)
    report: dict[str, Any] = {
        'collection_id': collection_id,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'input_paths': [str(path) for path in paths],
        'output_dir': str(output_path),
        'source_batch_count': len(batch_reports),
        'source_batches': source_summary,
    }
    if include_transitions:
        transition_sources = _dataset_sources(batch_reports, 'transition_path')
        transition_path = output_path / 'combined_training_transitions.jsonl'
        transition_count = _concatenate_jsonl(transition_sources, transition_path, id_key='sample_id')
        transition_manifest_path = write_dataset_manifest(
            dataset_type='combined_training_transitions',
            dataset_path=transition_path,
            record_count=transition_count,
            source_paths=[source['path'] for source in transition_sources],
            filters={'source_dataset_type': 'training_transitions'},
            context=_collection_context(collection_id=collection_id, source_summary=source_summary),
        )
        transition_quality_path = output_path / 'combined_training_transitions.quality.json'
        transition_quality = validate_transition_dataset(transition_path)
        write_dataset_quality_report(transition_quality, transition_quality_path)
        report.update({
            'transition_path': str(transition_path),
            'transition_manifest_path': str(transition_manifest_path),
            'transition_quality_path': str(transition_quality_path),
            'transition_quality_status': transition_quality['status'],
            'transition_count': transition_count,
            'transition_source_count': len(transition_sources),
        })
    if include_preferences:
        preference_sources = _dataset_sources(batch_reports, 'preference_path')
        preference_path = output_path / 'combined_preference_pairs.jsonl'
        preference_count = _concatenate_jsonl(preference_sources, preference_path, id_key='pair_id')
        preference_manifest_path = write_dataset_manifest(
            dataset_type='combined_preference_pairs',
            dataset_path=preference_path,
            record_count=preference_count,
            source_paths=[source['path'] for source in preference_sources],
            filters={'source_dataset_type': 'preference_pairs'},
            context=_collection_context(collection_id=collection_id, source_summary=source_summary),
        )
        preference_quality_path = output_path / 'combined_preference_pairs.quality.json'
        preference_quality = validate_preference_dataset(preference_path)
        write_dataset_quality_report(preference_quality, preference_quality_path)
        report.update({
            'preference_path': str(preference_path),
            'preference_manifest_path': str(preference_manifest_path),
            'preference_quality_path': str(preference_quality_path),
            'preference_quality_status': preference_quality['status'],
            'preference_pair_count': preference_count,
            'preference_source_count': len(preference_sources),
        })
    report_path = output_path / 'dataset_collection_report.json'
    report['report_path'] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


def _discover_batch_reports(input_paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for input_path in input_paths:
        for report_path in _candidate_batch_report_paths(input_path):
            resolved = report_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            report = _load_json_object(report_path)
            report['_report_path'] = str(report_path)
            report['_benchmark_context'] = _benchmark_context_for_batch(report_path)
            reports.append(report)
    return reports


def _candidate_batch_report_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.name == 'batch_report.json':
            return [input_path]
        if input_path.name == 'benchmark_report.json':
            return _batch_paths_from_benchmark_report(input_path)
        return []
    if input_path.is_dir():
        paths: list[Path] = []
        benchmark_report_paths = sorted(input_path.rglob('benchmark_report.json'))
        benchmark_batch_paths: set[Path] = set()
        for benchmark_report_path in benchmark_report_paths:
            batch_paths = _batch_paths_from_benchmark_report(benchmark_report_path)
            paths.extend(batch_paths)
            benchmark_batch_paths.update(path.resolve() for path in batch_paths)
        for batch_report_path in sorted(input_path.rglob('batch_report.json')):
            if batch_report_path.resolve() not in benchmark_batch_paths:
                paths.append(batch_report_path)
        return paths
    return []


def _batch_paths_from_benchmark_report(benchmark_report_path: Path) -> list[Path]:
    benchmark = _load_json_object(benchmark_report_path)
    return [
        Path(str(seed_report['report_path']))
        for seed_report in benchmark.get('seed_batch_reports', [])
        if isinstance(seed_report, dict) and seed_report.get('report_path')
    ]


def _benchmark_context_for_batch(batch_report_path: Path) -> dict[str, Any]:
    for parent in batch_report_path.resolve().parents:
        benchmark_path = parent / 'benchmark_report.json'
        if not benchmark_path.exists():
            continue
        benchmark = _load_json_object(benchmark_path)
        return {
            'benchmark_id': benchmark.get('benchmark_id'),
            'benchmark_path': str(benchmark_path),
            'manifest_path': benchmark.get('manifest_path'),
            'git_commit': benchmark.get('git_commit'),
            'created_at': benchmark.get('created_at'),
        }
    return {}


def _source_summary(batch_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for report in batch_reports:
        benchmark_context = report.get('_benchmark_context') if isinstance(report.get('_benchmark_context'), dict) else {}
        summary.append({
            'batch_id': report.get('batch_id'),
            'batch_report_path': report.get('_report_path'),
            'benchmark_id': benchmark_context.get('benchmark_id'),
            'benchmark_path': benchmark_context.get('benchmark_path'),
            'scenario_id': report.get('scenario_id'),
            'policy': report.get('policy'),
            'baseline_seed': report.get('baseline_seed'),
            'character_load_path': report.get('character_load_path'),
            'llm_player_controllers': report.get('llm_player_controllers') or [],
            'transition_path': report.get('transition_path'),
            'preference_path': report.get('preference_path'),
            'transition_count': report.get('transition_count'),
            'preference_pair_count': report.get('preference_pair_count'),
            'success_rate': report.get('success_rate'),
            'avg_reward': report.get('avg_reward'),
        })
    return summary


def _collection_context(*, collection_id: str, source_summary: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'collection_id': collection_id,
        'source_batch_count': len(source_summary),
        'source_batch_reports': [item.get('batch_report_path') for item in source_summary if item.get('batch_report_path')],
        'source_benchmark_ids': _unique_present(item.get('benchmark_id') for item in source_summary),
        'scenario_ids': _unique_present(item.get('scenario_id') for item in source_summary),
        'policies': _unique_present(item.get('policy') for item in source_summary),
        'baseline_seeds': _unique_present(item.get('baseline_seed') for item in source_summary),
        'character_load_paths': _unique_present(item.get('character_load_path') for item in source_summary),
    }


def _dataset_sources(batch_reports: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for report in batch_reports:
        value = report.get(key)
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        sources.append({
            'path': path,
            'namespace': _source_namespace(report, path),
        })
    return sources


def _concatenate_jsonl(source_entries: list[dict[str, Any]], output_path: Path, *, id_key: str) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open('w', encoding='utf-8') as output:
        for source in source_entries:
            source_path = source['path']
            namespace = str(source['namespace'])
            for line in source_path.read_text(encoding='utf-8-sig').splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f'Expected JSON object rows in {source_path}.')
                _namespace_dataset_row(row, id_key=id_key, namespace=namespace)
                output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
                count += 1
    return count


def _namespace_dataset_row(row: dict[str, Any], *, id_key: str, namespace: str) -> None:
    value = row.get(id_key)
    if isinstance(value, str) and value:
        row[id_key] = f'{namespace}::{value}'
    if id_key == 'pair_id':
        for sample_key in ('chosen_sample_id', 'rejected_sample_id'):
            sample_value = row.get(sample_key)
            if isinstance(sample_value, str) and sample_value:
                row[sample_key] = f'{namespace}::{sample_value}'
    row['source_batch_id'] = namespace


def _source_namespace(report: dict[str, Any], path: Path) -> str:
    benchmark_context = report.get('_benchmark_context') if isinstance(report.get('_benchmark_context'), dict) else {}
    parts = [
        benchmark_context.get('benchmark_id'),
        report.get('batch_id'),
    ]
    tokens = [_safe_token(str(part)) for part in parts if part]
    if tokens:
        return '__'.join(tokens)
    return _safe_token(path.parent.name)


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'source'


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON object at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise ValueError(f'Expected a JSON object at {path}.')
    return payload


def _unique_present(values: Iterable[Any]) -> list[Any]:
    unique: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        marker = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(value)
    return unique
