from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


TRAINING_RUN_SCHEMA_VERSION = 'dnd-agents-training-run-v1'


class TrainingNoOpError(RuntimeError):
    pass


def run_noop_training_epoch(
    recipe_path: str | Path,
    *,
    output_dir: str | Path,
    run_name: str = 'noop-training',
    max_records_per_objective: int | None = None,
    allow_record_mismatch: bool = False,
) -> dict[str, Any]:
    if max_records_per_objective is not None and max_records_per_objective < 0:
        raise TrainingNoOpError('max_records_per_objective must be zero or greater.')
    path = Path(recipe_path)
    recipe = _load_recipe(path)
    if recipe.get('schema_version') != TRAINING_RECIPE_SCHEMA_VERSION:
        raise TrainingNoOpError(f'Unsupported recipe schema: {recipe.get("schema_version")!r}.')
    objectives = _objectives(recipe)
    if not objectives:
        raise TrainingNoOpError('Recipe has no training objectives.')

    output_path = Path(output_dir)
    run_id = f'{_safe_token(run_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = output_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    objective_reports = [
        _objective_accounting(objective, max_records=max_records_per_objective)
        for objective in objectives
    ]
    failed_reports = [report for report in objective_reports if report['status'] == 'fail']
    if failed_reports and not allow_record_mismatch:
        messages = '; '.join(str(report['message']) for report in failed_reports)
        raise TrainingNoOpError(f'No-op trainer accounting failed: {messages}')

    total_planned = sum(_int(report.get('planned_records')) for report in objective_reports)
    total_observed = sum(_int(report.get('observed_records')) for report in objective_reports)
    total_consumed = sum(_int(report.get('consumed_records')) for report in objective_reports)
    report: dict[str, Any] = {
        'schema_version': TRAINING_RUN_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_id': run_id,
        'run_name': run_name,
        'run_mode': 'noop_epoch',
        'output_dir': str(run_dir),
        'recipe_path': str(path),
        'recipe_id': recipe.get('recipe_id'),
        'epoch_count': 1,
        'trainer_backend': {
            'name': 'noop_accounting',
            'updates_model_weights': False,
            'max_records_per_objective': max_records_per_objective,
            'allow_record_mismatch': allow_record_mismatch,
        },
        'totals': {
            'objective_count': len(objective_reports),
            'planned_records': total_planned,
            'observed_records': total_observed,
            'consumed_records': total_consumed,
            'failed_objective_count': len(failed_reports),
        },
        'objectives': objective_reports,
        'checks': _run_checks(objective_reports),
    }
    report_path = run_dir / 'training_run_report.json'
    markdown_path = run_dir / 'training_run_report.md'
    report['report_path'] = str(report_path)
    report['markdown_path'] = str(markdown_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_noop_training_markdown(report), encoding='utf-8')
    return report


def render_noop_training_markdown(report: dict[str, Any]) -> str:
    totals = report.get('totals') if isinstance(report.get('totals'), dict) else {}
    lines = [
        '# No-Op Training Run',
        '',
        f'Run: **{_markdown_text(report.get("run_id"))}**',
        f'Mode: {_markdown_text(report.get("run_mode"))}',
        f'Recipe: {_markdown_text(report.get("recipe_id"))}',
        f'Objectives: {_format_int(totals.get("objective_count"))}',
        f'Observed records: {_format_int(totals.get("observed_records"))}',
        f'Consumed records: {_format_int(totals.get("consumed_records"))}',
        f'Failed objectives: {_format_int(totals.get("failed_objective_count"))}',
        '',
        '## Objectives',
        '',
        '| Objective | Status | Planned | Observed | Consumed | Dataset |',
        '| --- | --- | ---: | ---: | ---: | --- |',
    ]
    objectives = report.get('objectives') if isinstance(report.get('objectives'), list) else []
    if objectives:
        for objective in objectives:
            lines.append(
                '| '
                + ' | '.join([
                    _markdown_text(objective.get('objective')),
                    _markdown_text(objective.get('status')),
                    _format_int(objective.get('planned_records')),
                    _format_int(objective.get('observed_records')),
                    _format_int(objective.get('consumed_records')),
                    _markdown_text(objective.get('dataset_path')),
                ])
                + ' |'
            )
    else:
        lines.append('| n/a | fail | 0 | 0 | 0 | n/a |')
    lines.append('')
    return '\n'.join(lines)


def _load_recipe(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise TrainingNoOpError(f'Training recipe does not exist: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise TrainingNoOpError(f'Invalid training recipe JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise TrainingNoOpError(f'Training recipe at {path} must be a JSON object.')
    return payload


def _objectives(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    objectives = recipe.get('objectives')
    return [objective for objective in objectives if isinstance(objective, dict)] if isinstance(objectives, list) else []


def _objective_accounting(objective: dict[str, Any], *, max_records: int | None) -> dict[str, Any]:
    dataset_path_value = objective.get('dataset_path')
    if not isinstance(dataset_path_value, str) or not dataset_path_value:
        return _objective_failure(objective, message='Objective has no dataset_path.')
    dataset_path = Path(dataset_path_value)
    if not dataset_path.exists():
        return _objective_failure(objective, message=f'Dataset does not exist: {dataset_path}')
    observed_records = _count_jsonl_rows(dataset_path)
    planned_records = _int(objective.get('record_count'))
    consumed_records = observed_records if max_records is None else min(observed_records, max_records)
    status = 'pass' if planned_records == observed_records else 'fail'
    message = (
        f'Observed {observed_records} records as planned.'
        if status == 'pass'
        else f'Planned {planned_records} records but observed {observed_records}.'
    )
    return {
        'objective': objective.get('objective'),
        'status': status,
        'message': message,
        'weight': objective.get('weight'),
        'dataset_path': str(dataset_path),
        'dataset_type': objective.get('dataset_type'),
        'quality_status': objective.get('quality_status'),
        'planned_records': planned_records,
        'observed_records': observed_records,
        'consumed_records': consumed_records,
        'target': objective.get('target'),
        'input_fields': objective.get('input_fields') if isinstance(objective.get('input_fields'), list) else [],
    }


def _objective_failure(objective: dict[str, Any], *, message: str) -> dict[str, Any]:
    return {
        'objective': objective.get('objective'),
        'status': 'fail',
        'message': message,
        'weight': objective.get('weight'),
        'dataset_path': objective.get('dataset_path'),
        'dataset_type': objective.get('dataset_type'),
        'quality_status': objective.get('quality_status'),
        'planned_records': _int(objective.get('record_count')),
        'observed_records': 0,
        'consumed_records': 0,
        'target': objective.get('target'),
        'input_fields': objective.get('input_fields') if isinstance(objective.get('input_fields'), list) else [],
    }


def _count_jsonl_rows(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            count += 1
    return count


def _run_checks(objective_reports: list[dict[str, Any]]) -> list[dict[str, str]]:
    checks = [{
        'status': 'pass' if objective_reports else 'fail',
        'message': f'Objective count is {len(objective_reports)}.',
    }]
    for report in objective_reports:
        checks.append({
            'status': str(report.get('status') or 'fail'),
            'message': str(report.get('message') or ''),
        })
    return checks


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'noop-training'


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
