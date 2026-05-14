from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from training.training_smoke import TRAINING_SMOKE_SCHEMA_VERSION


TRAINING_RECIPE_SCHEMA_VERSION = 'dnd-agents-training-recipe-v1'
DEFAULT_OBJECTIVE_MIX = {
    'supervised_action_prediction': 0.6,
    'preference_ranking': 0.4,
}


class TrainingRecipeError(RuntimeError):
    pass


def build_training_recipe(
    smoke_report_path: str | Path,
    *,
    output_dir: str | Path,
    recipe_name: str = 'training-recipe',
    objective_mix: dict[str, float] | None = None,
    allow_failed_smoke: bool = False,
) -> dict[str, Any]:
    smoke_path = Path(smoke_report_path)
    smoke = _load_smoke_report(smoke_path)
    if smoke.get('schema_version') != TRAINING_SMOKE_SCHEMA_VERSION:
        raise TrainingRecipeError(f'Unsupported smoke report schema: {smoke.get("schema_version")!r}.')
    checks = _checks(smoke)
    failed_checks = [check for check in checks if check.get('status') == 'fail']
    readiness = smoke.get('readiness') if isinstance(smoke.get('readiness'), dict) else {}
    if (failed_checks or readiness.get('status') != 'ready') and not allow_failed_smoke:
        raise TrainingRecipeError('Training recipe requires a passing ready smoke report.')

    output_path = Path(output_dir)
    recipe_id = f'{_safe_token(recipe_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    recipe_dir = output_path / recipe_id
    recipe_dir.mkdir(parents=True, exist_ok=True)
    objectives = _objective_plan(_normalize_objective_mix(objective_mix), datasets=_datasets(smoke))
    recipe: dict[str, Any] = {
        'schema_version': TRAINING_RECIPE_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'recipe_id': recipe_id,
        'recipe_name': recipe_name,
        'recipe_mode': 'dry_run_plan',
        'output_dir': str(recipe_dir),
        'smoke_report_path': str(smoke_path),
        'smoke_run_id': smoke.get('run_id'),
        'readiness': {
            'status': readiness.get('status'),
            'total_record_count': readiness.get('total_record_count'),
            'blocker_count': readiness.get('blocker_count'),
            'warning_count': readiness.get('warning_count'),
        },
        'quality_gate': {
            'required_smoke_schema': TRAINING_SMOKE_SCHEMA_VERSION,
            'allow_failed_smoke': allow_failed_smoke,
            'failed_check_count': len(failed_checks),
            'checks': checks,
        },
        'datasets': _recipe_datasets(smoke),
        'objectives': objectives,
        'trainer_stub': {
            'status': 'planned',
            'backend': 'not_configured',
            'notes': [
                'This recipe is a deterministic handoff artifact and does not start model training.',
                'Use the dataset paths and objective weights here when adding the first trainer backend.',
            ],
        },
        'next_commands': _next_commands(smoke_path=smoke_path, recipe_dir=recipe_dir),
    }
    recipe_path = recipe_dir / 'training_recipe.json'
    markdown_path = recipe_dir / 'training_recipe.md'
    recipe['recipe_path'] = str(recipe_path)
    recipe['markdown_path'] = str(markdown_path)
    recipe_path.write_text(json.dumps(recipe, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_training_recipe_markdown(recipe), encoding='utf-8')
    return recipe


def render_training_recipe_markdown(recipe: dict[str, Any]) -> str:
    readiness = recipe.get('readiness') if isinstance(recipe.get('readiness'), dict) else {}
    quality_gate = recipe.get('quality_gate') if isinstance(recipe.get('quality_gate'), dict) else {}
    lines = [
        '# Training Recipe',
        '',
        f'Recipe: **{_markdown_text(recipe.get("recipe_id"))}**',
        f'Mode: {_markdown_text(recipe.get("recipe_mode"))}',
        f'Smoke: {_markdown_text(recipe.get("smoke_run_id"))}',
        f'Readiness: **{_markdown_text(readiness.get("status"))}**',
        f'Failed smoke checks: {_format_int(quality_gate.get("failed_check_count"))}',
        '',
        '## Objectives',
        '',
        '| Objective | Weight | Dataset | Records |',
        '| --- | ---: | --- | ---: |',
    ]
    objectives = recipe.get('objectives') if isinstance(recipe.get('objectives'), list) else []
    if objectives:
        for objective in objectives:
            lines.append(
                '| '
                + ' | '.join([
                    _markdown_text(objective.get('objective')),
                    _format_float(objective.get('weight')),
                    _markdown_text(objective.get('dataset_path')),
                    _format_int(objective.get('record_count')),
                ])
                + ' |'
            )
    else:
        lines.append('| n/a | 0.00 | n/a | 0 |')
    lines.extend([
        '',
        '## Next Commands',
        '',
    ])
    commands = recipe.get('next_commands') if isinstance(recipe.get('next_commands'), list) else []
    if commands:
        for command in commands:
            lines.append(f'- `{_markdown_text(command)}`')
    else:
        lines.append('- n/a')
    lines.append('')
    return '\n'.join(lines)


def _load_smoke_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise TrainingRecipeError(f'Smoke report does not exist: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise TrainingRecipeError(f'Invalid smoke report JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise TrainingRecipeError(f'Smoke report at {path} must be a JSON object.')
    return payload


def _checks(smoke: dict[str, Any]) -> list[dict[str, Any]]:
    checks = smoke.get('checks')
    return [check for check in checks if isinstance(check, dict)] if isinstance(checks, list) else []


def _datasets(smoke: dict[str, Any]) -> list[dict[str, Any]]:
    datasets = smoke.get('datasets')
    return [dataset for dataset in datasets if isinstance(dataset, dict)] if isinstance(datasets, list) else []


def _recipe_datasets(smoke: dict[str, Any]) -> list[dict[str, Any]]:
    recipe_datasets: list[dict[str, Any]] = []
    for dataset in _datasets(smoke):
        recipe_datasets.append({
            'dataset_name': dataset.get('dataset_name'),
            'dataset_type': dataset.get('dataset_type'),
            'dataset_path': dataset.get('dataset_path'),
            'record_count': dataset.get('record_count'),
            'manifest_path': dataset.get('manifest_path'),
            'quality_path': dataset.get('quality_path'),
            'quality_status': dataset.get('quality_status'),
        })
    return recipe_datasets


def _objective_plan(objective_mix: dict[str, float], *, datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objectives: list[dict[str, Any]] = []
    transition_dataset = _first_dataset(datasets, contains='transition')
    preference_dataset = _first_dataset(datasets, contains='preference')
    if transition_dataset is not None and objective_mix.get('supervised_action_prediction', 0.0) > 0:
        objectives.append(_objective_row(
            objective='supervised_action_prediction',
            weight=objective_mix['supervised_action_prediction'],
            dataset=transition_dataset,
            target='action',
            input_fields=['observation', 'available_actions', 'runtime_mode', 'agent_id'],
        ))
    if preference_dataset is not None and objective_mix.get('preference_ranking', 0.0) > 0:
        objectives.append(_objective_row(
            objective='preference_ranking',
            weight=objective_mix['preference_ranking'],
            dataset=preference_dataset,
            target='chosen_over_rejected',
            input_fields=['prompt', 'chosen', 'rejected', 'reward_gap'],
        ))
    return objectives


def _objective_row(
    *,
    objective: str,
    weight: float,
    dataset: dict[str, Any],
    target: str,
    input_fields: list[str],
) -> dict[str, Any]:
    return {
        'objective': objective,
        'weight': weight,
        'dataset_path': dataset.get('dataset_path'),
        'dataset_type': dataset.get('dataset_type'),
        'record_count': dataset.get('record_count'),
        'quality_status': dataset.get('quality_status'),
        'target': target,
        'input_fields': input_fields,
    }


def _first_dataset(datasets: list[dict[str, Any]], *, contains: str) -> dict[str, Any] | None:
    for dataset in datasets:
        dataset_type = str(dataset.get('dataset_type') or dataset.get('dataset_name') or '')
        if contains in dataset_type:
            return dataset
    return None


def _normalize_objective_mix(objective_mix: dict[str, float] | None) -> dict[str, float]:
    raw = dict(DEFAULT_OBJECTIVE_MIX if objective_mix is None else objective_mix)
    cleaned: dict[str, float] = {}
    for key in DEFAULT_OBJECTIVE_MIX:
        value = raw.get(key, 0.0)
        if not isinstance(value, (int, float)):
            raise TrainingRecipeError(f'Objective weight for {key} must be numeric.')
        if float(value) < 0:
            raise TrainingRecipeError(f'Objective weight for {key} must be zero or greater.')
        cleaned[key] = float(value)
    total = sum(cleaned.values())
    if total <= 0:
        raise TrainingRecipeError('At least one objective weight must be greater than zero.')
    return {key: value / total for key, value in cleaned.items()}


def _next_commands(*, smoke_path: Path, recipe_dir: Path) -> list[str]:
    return [
        f'python user-test\\plan_training_recipe.py --smoke-report {smoke_path} --output-dir {recipe_dir.parent}',
        f'python user-test\\run_training_smoke.py --input runs\\datasets\\latest --input runs\\benchmarks --output-dir runs\\training-smoke',
    ]


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'training-recipe'


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_float(value: Any) -> str:
    return f'{float(value):.2f}' if isinstance(value, (int, float)) else '0.00'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
