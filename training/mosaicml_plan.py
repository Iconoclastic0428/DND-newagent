from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from training.supervised_baseline import SUPERVISED_BASELINE_SCHEMA_VERSION
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


MOSAICML_TRAINING_PLAN_SCHEMA_VERSION = 'dnd-agents-mosaicml-training-plan-v1'
DEFAULT_TARGET_DELTA = 0.05
DEFAULT_WEAK_SLICE_TARGET_DELTA = 0.10
PLANNED_TRAINER_ENTRYPOINT = 'user-test/train_policy_mosaicml.py'


class MosaicMLPlanError(RuntimeError):
    pass


def build_mosaicml_training_plan(
    recipe_path: str | Path,
    *,
    baseline_report_path: str | Path,
    output_dir: str | Path,
    plan_name: str = 'mosaicml-training-plan',
    accelerator: str = 'gpu',
    gpu_type: str = 'configured-by-mosaicml-workspace',
    container_image: str = 'configured-by-mosaicml-workspace',
    target_delta: float = DEFAULT_TARGET_DELTA,
    weak_slice_target_delta: float = DEFAULT_WEAK_SLICE_TARGET_DELTA,
) -> dict[str, Any]:
    if target_delta < 0:
        raise MosaicMLPlanError('target_delta must be zero or greater.')
    if weak_slice_target_delta < 0:
        raise MosaicMLPlanError('weak_slice_target_delta must be zero or greater.')
    recipe_file = Path(recipe_path)
    baseline_file = Path(baseline_report_path)
    recipe = _load_json_object(recipe_file, label='training recipe')
    baseline = _load_json_object(baseline_file, label='supervised baseline report')
    if recipe.get('schema_version') != TRAINING_RECIPE_SCHEMA_VERSION:
        raise MosaicMLPlanError(f'Unsupported recipe schema: {recipe.get("schema_version")!r}.')
    if baseline.get('schema_version') != SUPERVISED_BASELINE_SCHEMA_VERSION:
        raise MosaicMLPlanError(f'Unsupported baseline schema: {baseline.get("schema_version")!r}.')
    objectives = _objectives(recipe)
    if not objectives:
        raise MosaicMLPlanError('Training recipe has no objectives.')
    overall_eval = _overall_eval(baseline)
    if not isinstance(overall_eval.get('accuracy'), (int, float)):
        raise MosaicMLPlanError('Baseline report has no numeric eval accuracy.')

    output_path = Path(output_dir)
    plan_id = f'{_safe_token(plan_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    plan_dir = output_path / plan_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    improvement_targets = _improvement_targets(
        baseline,
        target_delta=target_delta,
        weak_slice_target_delta=weak_slice_target_delta,
    )
    plan: dict[str, Any] = {
        'schema_version': MOSAICML_TRAINING_PLAN_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'plan_id': plan_id,
        'plan_name': plan_name,
        'plan_mode': 'remote_gpu_handoff',
        'output_dir': str(plan_dir),
        'recipe_path': str(recipe_file),
        'recipe_id': recipe.get('recipe_id'),
        'baseline_report_path': str(baseline_file),
        'baseline': {
            'run_id': baseline.get('run_id'),
            'split': baseline.get('split') if isinstance(baseline.get('split'), dict) else {},
            'overall_eval': overall_eval,
        },
        'platform': {
            'name': 'mosaicml',
            'accelerator': accelerator,
            'gpu_type': gpu_type,
            'container_image': container_image,
            'submission_status': 'planned_not_submitted',
        },
        'objectives': _objective_rows(objectives),
        'datasets': _dataset_rows(objectives),
        'improvement_targets': improvement_targets,
        'launch': _launch_config(
            recipe_file=recipe_file,
            baseline_file=baseline_file,
            output_dir=Path('runs/training-runs'),
        ),
        'checks': _plan_checks(objectives=objectives, overall_eval=overall_eval, improvement_targets=improvement_targets),
    }
    plan_path = plan_dir / 'mosaicml_training_plan.json'
    markdown_path = plan_dir / 'mosaicml_training_plan.md'
    plan['plan_path'] = str(plan_path)
    plan['markdown_path'] = str(markdown_path)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_mosaicml_plan_markdown(plan), encoding='utf-8')
    return plan


def render_mosaicml_plan_markdown(plan: dict[str, Any]) -> str:
    platform = plan.get('platform') if isinstance(plan.get('platform'), dict) else {}
    baseline = plan.get('baseline') if isinstance(plan.get('baseline'), dict) else {}
    overall_eval = baseline.get('overall_eval') if isinstance(baseline.get('overall_eval'), dict) else {}
    launch = plan.get('launch') if isinstance(plan.get('launch'), dict) else {}
    lines = [
        '# MosaicML Training Plan',
        '',
        f'Plan: **{_markdown_text(plan.get("plan_id"))}**',
        f'Recipe: {_markdown_text(plan.get("recipe_id"))}',
        f'Platform: {_markdown_text(platform.get("name"))}',
        f'Accelerator: {_markdown_text(platform.get("accelerator"))}',
        f'GPU type: {_markdown_text(platform.get("gpu_type"))}',
        f'Container image: {_markdown_text(platform.get("container_image"))}',
        f'Submission: {_markdown_text(platform.get("submission_status"))}',
        f'Baseline eval accuracy: {_format_float(overall_eval.get("accuracy"))}',
        '',
        '## Objectives',
        '',
        '| Objective | Weight | Dataset | Records |',
        '| --- | ---: | --- | ---: |',
    ]
    objectives = plan.get('objectives') if isinstance(plan.get('objectives'), list) else []
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
        '## Improvement Targets',
        '',
        '| Field | Value | Records | Baseline Accuracy | Target Accuracy |',
        '| --- | --- | ---: | ---: | ---: |',
    ])
    targets = plan.get('improvement_targets') if isinstance(plan.get('improvement_targets'), list) else []
    if targets:
        for target in targets:
            lines.append(
                '| '
                + ' | '.join([
                    _markdown_text(target.get('field')),
                    _markdown_text(target.get('value')),
                    _format_int(target.get('record_count')),
                    _format_float(target.get('accuracy')),
                    _format_float(target.get('target_accuracy')),
                ])
                + ' |'
            )
    else:
        lines.append('| n/a | n/a | 0 | n/a | n/a |')
    lines.extend([
        '',
        '## Planned Command',
        '',
        f'`{_markdown_text(launch.get("planned_command"))}`',
        '',
    ])
    return '\n'.join(lines)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise MosaicMLPlanError(f'{label.title()} does not exist: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise MosaicMLPlanError(f'Invalid {label} JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise MosaicMLPlanError(f'{label.title()} at {path} must be a JSON object.')
    return payload


def _objectives(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    objectives = recipe.get('objectives')
    return [objective for objective in objectives if isinstance(objective, dict)] if isinstance(objectives, list) else []


def _objective_rows(objectives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'objective': objective.get('objective'),
            'weight': objective.get('weight'),
            'dataset_path': objective.get('dataset_path'),
            'dataset_type': objective.get('dataset_type'),
            'record_count': objective.get('record_count'),
            'quality_status': objective.get('quality_status'),
            'target': objective.get('target'),
            'input_fields': objective.get('input_fields') if isinstance(objective.get('input_fields'), list) else [],
        }
        for objective in objectives
    ]


def _dataset_rows(objectives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for objective in objectives:
        dataset_path = str(objective.get('dataset_path') or '')
        if not dataset_path or dataset_path in seen_paths:
            continue
        seen_paths.add(dataset_path)
        rows.append({
            'dataset_path': dataset_path,
            'dataset_type': objective.get('dataset_type'),
            'record_count': objective.get('record_count'),
            'quality_status': objective.get('quality_status'),
        })
    return rows


def _overall_eval(baseline: dict[str, Any]) -> dict[str, Any]:
    metrics = baseline.get('metrics') if isinstance(baseline.get('metrics'), dict) else {}
    eval_metrics = metrics.get('eval') if isinstance(metrics.get('eval'), dict) else {}
    return {
        'record_count': eval_metrics.get('record_count'),
        'correct_count': eval_metrics.get('correct_count'),
        'accuracy': eval_metrics.get('accuracy'),
        'negative_log_likelihood': eval_metrics.get('negative_log_likelihood'),
    }


def _improvement_targets(
    baseline: dict[str, Any],
    *,
    target_delta: float,
    weak_slice_target_delta: float,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    overall = _overall_eval(baseline)
    overall_accuracy = overall.get('accuracy')
    if isinstance(overall_accuracy, (int, float)):
        targets.append({
            'field': 'overall',
            'value': 'eval',
            'record_count': overall.get('record_count'),
            'accuracy': float(overall_accuracy),
            'negative_log_likelihood': overall.get('negative_log_likelihood'),
            'target_accuracy': _bounded_accuracy(float(overall_accuracy) + target_delta),
            'priority': 'aggregate',
        })
    metrics = baseline.get('metrics') if isinstance(baseline.get('metrics'), dict) else {}
    breakdowns = metrics.get('breakdowns') if isinstance(metrics.get('breakdowns'), dict) else {}
    eval_breakdowns = breakdowns.get('eval') if isinstance(breakdowns.get('eval'), dict) else {}
    for field, groups in sorted(eval_breakdowns.items()):
        if not isinstance(groups, dict):
            continue
        for value, group_metrics in sorted(groups.items()):
            if not isinstance(group_metrics, dict):
                continue
            accuracy = group_metrics.get('accuracy')
            if not isinstance(accuracy, (int, float)):
                continue
            targets.append({
                'field': str(field),
                'value': str(value),
                'record_count': group_metrics.get('record_count'),
                'accuracy': float(accuracy),
                'negative_log_likelihood': group_metrics.get('negative_log_likelihood'),
                'target_accuracy': _bounded_accuracy(float(accuracy) + weak_slice_target_delta),
                'priority': 'weak_slice',
            })
    return sorted(
        targets,
        key=lambda target: (
            target['accuracy'],
            -_int(target.get('record_count')),
            target['field'],
            target['value'],
        ),
    )


def _launch_config(*, recipe_file: Path, baseline_file: Path, output_dir: Path) -> dict[str, Any]:
    return {
        'status': 'planned_not_submitted',
        'trainer_entrypoint': PLANNED_TRAINER_ENTRYPOINT,
        'planned_command': (
            f'python {PLANNED_TRAINER_ENTRYPOINT} '
            f'--recipe {recipe_file} '
            f'--baseline-report {baseline_file} '
            f'--output-dir {output_dir}'
        ),
        'required_inputs': {
            'recipe_path': str(recipe_file),
            'baseline_report_path': str(baseline_file),
        },
        'expected_outputs': [
            'trainable_policy_model',
            'training_run_report.json',
            'training_run_report.md',
        ],
    }


def _plan_checks(
    *,
    objectives: list[dict[str, Any]],
    overall_eval: dict[str, Any],
    improvement_targets: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {'status': 'pass' if objectives else 'fail', 'message': f'Objective count is {len(objectives)}.'},
        {'status': 'pass' if isinstance(overall_eval.get('accuracy'), (int, float)) else 'fail', 'message': 'Baseline eval accuracy is available.'},
        {'status': 'pass' if improvement_targets else 'warn', 'message': f'Improvement target count is {len(improvement_targets)}.'},
        {'status': 'pass', 'message': 'MosaicML submission is planned but not submitted by this local command.'},
    ]


def _bounded_accuracy(value: float) -> float:
    return min(1.0, max(0.0, value))


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'mosaicml-training-plan'


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_float(value: Any) -> str:
    return f'{float(value):.4f}' if isinstance(value, (int, float)) else 'n/a'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
