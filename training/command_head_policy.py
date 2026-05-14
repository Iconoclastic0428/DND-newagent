from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from training.supervised_baseline import SUPERVISED_BASELINE_SCHEMA_VERSION
from training.trainable_policy import (
    BREAKDOWN_FIELDS,
    SPLIT_STRATEGIES,
    SUPERVISED_OBJECTIVE,
    _action_family,
    _action_parts,
    _component_accuracy,
    _features,
    _load_json_object,
    _load_transition_rows,
    _split_counts,
    _split_rows,
    _update_action_component_counts,
)
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


COMMAND_HEAD_POLICY_SCHEMA_VERSION = 'dnd-agents-command-head-policy-run-v1'
MAX_ARG_HEADS = 4


class CommandHeadPolicyError(RuntimeError):
    pass


def run_command_head_policy_preflight(
    recipe_path: str | Path,
    *,
    baseline_report_path: str | Path,
    output_dir: str | Path,
    run_name: str = 'mosaicml-command-head-policy',
    epochs: int = 8,
    learning_rate: float = 1.0,
    holdout_fraction: float = 0.2,
    split_strategy: str = 'hash',
    max_records: int | None = None,
    max_arg_heads: int = MAX_ARG_HEADS,
) -> dict[str, Any]:
    if epochs <= 0:
        raise CommandHeadPolicyError('epochs must be greater than 0.')
    if learning_rate <= 0:
        raise CommandHeadPolicyError('learning_rate must be greater than 0.')
    if not 0.0 <= holdout_fraction < 1.0:
        raise CommandHeadPolicyError('holdout_fraction must be at least 0 and less than 1.')
    if split_strategy not in SPLIT_STRATEGIES:
        raise CommandHeadPolicyError(f'split_strategy must be one of: {", ".join(sorted(SPLIT_STRATEGIES))}.')
    if max_records is not None and max_records <= 0:
        raise CommandHeadPolicyError('max_records must be greater than 0 when provided.')
    if max_arg_heads <= 0:
        raise CommandHeadPolicyError('max_arg_heads must be greater than 0.')

    recipe_file = Path(recipe_path)
    baseline_file = Path(baseline_report_path)
    try:
        recipe = _load_json_object(recipe_file, label='training recipe')
        baseline = _load_json_object(baseline_file, label='supervised baseline report')
    except RuntimeError as exc:
        raise CommandHeadPolicyError(str(exc)) from exc
    if recipe.get('schema_version') != TRAINING_RECIPE_SCHEMA_VERSION:
        raise CommandHeadPolicyError(f'Unsupported recipe schema: {recipe.get("schema_version")!r}.')
    if baseline.get('schema_version') != SUPERVISED_BASELINE_SCHEMA_VERSION:
        raise CommandHeadPolicyError(f'Unsupported baseline schema: {baseline.get("schema_version")!r}.')
    objective = _supervised_objective(recipe)
    if objective is None:
        raise CommandHeadPolicyError(f'Recipe has no {SUPERVISED_OBJECTIVE!r} objective.')
    dataset_path_value = objective.get('dataset_path')
    if not isinstance(dataset_path_value, str) or not dataset_path_value:
        raise CommandHeadPolicyError('Supervised objective has no dataset_path.')
    dataset_path = Path(dataset_path_value)
    if not dataset_path.exists():
        raise CommandHeadPolicyError(f'Supervised dataset does not exist: {dataset_path}')
    try:
        rows = _load_transition_rows(dataset_path)
    except RuntimeError as exc:
        raise CommandHeadPolicyError(str(exc)) from exc
    if max_records is not None:
        rows = rows[:max_records]
    if not rows:
        raise CommandHeadPolicyError('Supervised dataset has no usable action rows.')
    try:
        train_rows, eval_rows = _split_rows(rows, holdout_fraction=holdout_fraction, strategy=split_strategy)
    except RuntimeError as exc:
        raise CommandHeadPolicyError(str(exc)) from exc
    if not train_rows:
        raise CommandHeadPolicyError('Command-head policy needs at least one training row.')

    model = _train_command_head_model(train_rows, epochs=epochs, learning_rate=learning_rate, max_arg_heads=max_arg_heads)
    train_metrics = _evaluate_rows(train_rows, model)
    eval_metrics = _evaluate_rows(eval_rows, model) if eval_rows else _empty_metrics()
    metrics = {
        'train': train_metrics,
        'eval': eval_metrics,
        'breakdowns': {
            'train': _metric_breakdowns(train_rows, model),
            'eval': _metric_breakdowns(eval_rows, model),
        },
    }
    output_path = Path(output_dir)
    run_id = f'{_safe_token(run_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = output_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model_path = run_dir / 'command_head_policy_model.json'
    report_path = run_dir / 'command_head_policy_report.json'
    markdown_path = run_dir / 'command_head_policy_report.md'
    model_path.write_text(json.dumps(_model_artifact(model), ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    report: dict[str, Any] = {
        'schema_version': COMMAND_HEAD_POLICY_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_id': run_id,
        'run_name': run_name,
        'run_mode': 'local_command_head_policy_preflight',
        'output_dir': str(run_dir),
        'recipe_path': str(recipe_file),
        'recipe_id': recipe.get('recipe_id'),
        'baseline_report_path': str(baseline_file),
        'dataset_path': str(dataset_path),
        'objective': SUPERVISED_OBJECTIVE,
        'trainer_backend': {
            'name': 'sparse_multi_head_perceptron',
            'updates_model_weights': True,
            'mosaicml_submission_status': 'not_submitted_local_preflight',
        },
        'model': {
            'kind': 'multi_head_command_policy',
            'feature_template': 'state_summary_sparse_features_v2',
            'epochs': epochs,
            'learning_rate': learning_rate,
            'heads': _head_summary(model),
        },
        'split': {
            'strategy': split_strategy,
            'holdout_fraction': holdout_fraction,
            'total_records': len(rows),
            'train_records': len(train_rows),
            'eval_records': len(eval_rows),
            'max_records': max_records,
            'coverage': {'train': _split_counts(train_rows), 'eval': _split_counts(eval_rows)},
        },
        'metrics': metrics,
        'baseline_comparison': _baseline_comparison(metrics, baseline),
        'checks': _run_checks(train_rows=train_rows, eval_rows=eval_rows, eval_metrics=eval_metrics),
        'model_path': str(model_path),
        'report_path': str(report_path),
        'markdown_path': str(markdown_path),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_command_head_policy_markdown(report), encoding='utf-8')
    return report


def render_command_head_policy_markdown(report: dict[str, Any]) -> str:
    metrics = report.get('metrics') if isinstance(report.get('metrics'), dict) else {}
    train = metrics.get('train') if isinstance(metrics.get('train'), dict) else {}
    eval_metrics = metrics.get('eval') if isinstance(metrics.get('eval'), dict) else {}
    model = report.get('model') if isinstance(report.get('model'), dict) else {}
    heads = model.get('heads') if isinstance(model.get('heads'), dict) else {}
    comparison = report.get('baseline_comparison') if isinstance(report.get('baseline_comparison'), dict) else {}
    overall = comparison.get('overall') if isinstance(comparison.get('overall'), dict) else {}
    lines = [
        '# Command Head Policy Preflight',
        '',
        f'Run: **{_markdown_text(report.get("run_id"))}**',
        f'Recipe: {_markdown_text(report.get("recipe_id"))}',
        f'Dataset: {_markdown_text(report.get("dataset_path"))}',
        f'Model: {_markdown_text(model.get("kind"))}',
        '',
        '## Metrics',
        '',
        '| Split | Records | Exact Accuracy | Family Accuracy |',
        '| --- | ---: | ---: | ---: |',
        f'| train | {_format_int(train.get("record_count"))} | {_format_float(train.get("accuracy"))} | {_format_float(train.get("action_family_accuracy"))} |',
        f'| eval | {_format_int(eval_metrics.get("record_count"))} | {_format_float(eval_metrics.get("accuracy"))} | {_format_float(eval_metrics.get("action_family_accuracy"))} |',
        '',
        '## Head Metrics',
        '',
        '| Head | Labels | Train Rows |',
        '| --- | ---: | ---: |',
    ]
    for name in sorted(heads):
        head = heads[name] if isinstance(heads[name], dict) else {}
        lines.append(f'| {_markdown_text(name)} | {_format_int(head.get("label_count"))} | {_format_int(head.get("train_records"))} |')
    lines.extend([
        '',
        '## Baseline Comparison',
        '',
        '| Scope | Baseline Accuracy | Policy Accuracy | Delta | Beats Baseline |',
        '| --- | ---: | ---: | ---: | --- |',
        f'| overall | {_format_float(overall.get("baseline_accuracy"))} | {_format_float(overall.get("policy_accuracy"))} | {_format_float(overall.get("accuracy_delta"))} | {_markdown_text(overall.get("beats_baseline"))} |',
        '',
    ])
    return '\n'.join(lines)


def _supervised_objective(recipe: dict[str, Any]) -> dict[str, Any] | None:
    objectives = recipe.get('objectives')
    if not isinstance(objectives, list):
        return None
    for objective in objectives:
        if isinstance(objective, dict) and objective.get('objective') == SUPERVISED_OBJECTIVE:
            return objective
    return None


def _train_command_head_model(
    rows: list[dict[str, Any]],
    *,
    epochs: int,
    learning_rate: float,
    max_arg_heads: int,
) -> dict[str, Any]:
    heads: dict[str, dict[str, Any]] = {}
    heads['command_family'] = _train_head(
        rows,
        label_fn=lambda row: _action_family(str(row.get('action') or '')),
        epochs=epochs,
        learning_rate=learning_rate,
    )
    natural_rows = [row for row in rows if not str(row.get('action') or '').strip().startswith('/')]
    if natural_rows:
        heads['natural_action'] = _train_head(
            natural_rows,
            label_fn=lambda row: str(row.get('action') or ''),
            epochs=epochs,
            learning_rate=learning_rate,
        )
    slash_rows = [row for row in rows if str(row.get('action') or '').strip().startswith('/')]
    if slash_rows:
        heads['command_arg_count'] = _train_head(
            slash_rows,
            label_fn=lambda row: str(min(max_arg_heads, max(0, len(_action_parts(str(row.get('action') or ''))) - 1))),
            epochs=epochs,
            learning_rate=learning_rate,
        )
    for index in range(1, max_arg_heads + 1):
        arg_rows = [row for row in rows if _slash_arg(str(row.get('action') or ''), index) is not None]
        if not arg_rows:
            continue
        heads[f'command_arg_{index}'] = _train_head(
            arg_rows,
            label_fn=lambda row, arg_index=index: _slash_arg(str(row.get('action') or ''), arg_index),
            epochs=epochs,
            learning_rate=learning_rate,
        )
    return {
        'kind': 'multi_head_command_policy',
        'heads': heads,
        'epochs': epochs,
        'learning_rate': learning_rate,
    }


def _train_head(
    rows: list[dict[str, Any]],
    *,
    label_fn: Callable[[dict[str, Any]], str | None],
    epochs: int,
    learning_rate: float,
) -> dict[str, Any]:
    labeled_rows = [(row, label_fn(row)) for row in rows]
    labeled_rows = [(row, label) for row, label in labeled_rows if isinstance(label, str) and label]
    labels = sorted({label for _, label in labeled_rows})
    weights: dict[str, Counter[str]] = {label: Counter() for label in labels}
    feature_vocab: Counter[str] = Counter()
    for epoch in range(epochs):
        for row, expected in sorted(labeled_rows, key=lambda item: (str(item[0].get('sample_id') or ''), epoch)):
            features = _features(row)
            feature_vocab.update(features)
            predicted = _predict_label(features, weights, labels)
            if predicted == expected:
                continue
            for feature, value in features.items():
                weights[expected][feature] += learning_rate * value
                weights[predicted][feature] -= learning_rate * value
    return {
        'labels': labels,
        'weights': weights,
        'feature_vocab': feature_vocab,
        'train_records': len(labeled_rows),
    }


def _predict_command(row: dict[str, Any], model: dict[str, Any]) -> str:
    features = _features(row)
    family = _predict_head(features, model['heads'].get('command_family'))
    if family is None:
        return ''
    if not family.startswith('/'):
        natural = _predict_head(features, model['heads'].get('natural_action'))
        return natural or family
    parts = [family]
    arg_count = _predicted_arg_count(features, model)
    for index in range(1, arg_count + 1):
        arg = _predict_head(features, model['heads'].get(f'command_arg_{index}'))
        if arg is None:
            continue
        parts.append(arg)
    return ' '.join(parts)


def _predicted_arg_count(features: Counter[str], model: dict[str, Any]) -> int:
    value = _predict_head(features, model['heads'].get('command_arg_count'))
    if value is None:
        return MAX_ARG_HEADS
    try:
        return max(0, min(MAX_ARG_HEADS, int(value)))
    except ValueError:
        return MAX_ARG_HEADS


def _predict_head(features: Counter[str], head: dict[str, Any] | None) -> str | None:
    if not isinstance(head, dict):
        return None
    labels = head.get('labels')
    weights = head.get('weights')
    if not isinstance(labels, list) or not labels or not isinstance(weights, dict):
        return None
    return _predict_label(features, weights, labels)


def _predict_label(features: Counter[str], weights: dict[str, Counter[str]], labels: list[str]) -> str:
    return sorted(labels, key=lambda label: (-_score(features, weights[label]), label))[0]


def _score(features: Counter[str], weights: Counter[str]) -> float:
    return sum(weights.get(feature, 0.0) * value for feature, value in features.items())


def _evaluate_rows(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return _empty_metrics()
    correct = 0
    family_correct = 0
    component_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'correct_count': 0, 'record_count': 0})
    for row in rows:
        expected = str(row.get('action') or '')
        predicted = _predict_command(row, model)
        if predicted == expected:
            correct += 1
        if _action_family(predicted) == _action_family(expected):
            family_correct += 1
        _update_action_component_counts(component_counts, predicted=predicted, expected=expected)
    return {
        'record_count': len(rows),
        'correct_count': correct,
        'accuracy': correct / len(rows),
        'action_family_correct_count': family_correct,
        'action_family_accuracy': family_correct / len(rows),
        'action_component_accuracy': _component_accuracy(component_counts),
    }


def _metric_breakdowns(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for field in BREAKDOWN_FIELDS:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[_group_label(row.get(field))].append(row)
        result[field] = {
            label: _evaluate_rows(bucket_rows, model)
            for label, bucket_rows in sorted(buckets.items())
        }
    return result


def _baseline_comparison(metrics: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_metrics = baseline.get('metrics') if isinstance(baseline.get('metrics'), dict) else {}
    baseline_eval = baseline_metrics.get('eval') if isinstance(baseline_metrics.get('eval'), dict) else {}
    policy_eval = metrics.get('eval') if isinstance(metrics.get('eval'), dict) else {}
    return {'overall': _compare_metric(policy_eval, baseline_eval)}


def _compare_metric(policy: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    policy_accuracy = policy.get('accuracy')
    baseline_accuracy = baseline.get('accuracy')
    delta = (
        float(policy_accuracy) - float(baseline_accuracy)
        if isinstance(policy_accuracy, (int, float)) and isinstance(baseline_accuracy, (int, float))
        else None
    )
    return {
        'record_count': policy.get('record_count'),
        'baseline_record_count': baseline.get('record_count'),
        'policy_accuracy': policy_accuracy,
        'baseline_accuracy': baseline_accuracy,
        'accuracy_delta': delta,
        'beats_baseline': delta is not None and delta > 0,
    }


def _model_artifact(model: dict[str, Any]) -> dict[str, Any]:
    return {
        'schema_version': 'dnd-agents-command-head-policy-model-v1',
        'kind': 'multi_head_command_policy',
        'epochs': model['epochs'],
        'learning_rate': model['learning_rate'],
        'heads': _head_summary(model),
    }


def _head_summary(model: dict[str, Any]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for name, head in sorted(model.get('heads', {}).items()):
        labels = head.get('labels') if isinstance(head, dict) else []
        feature_vocab = head.get('feature_vocab') if isinstance(head, dict) else {}
        summary[name] = {
            'label_count': len(labels) if isinstance(labels, list) else 0,
            'feature_count': len(feature_vocab) if isinstance(feature_vocab, Counter) else 0,
            'train_records': head.get('train_records') if isinstance(head.get('train_records'), int) else 0,
        }
    return summary


def _run_checks(
    *,
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    eval_metrics: dict[str, Any],
) -> list[dict[str, str]]:
    accuracy = eval_metrics.get('accuracy')
    checks = [
        {'status': 'pass' if train_rows else 'fail', 'message': f'Training split has {len(train_rows)} rows.'},
        {'status': 'pass' if eval_rows else 'warn', 'message': f'Evaluation split has {len(eval_rows)} rows.'},
        {
            'status': 'pass' if isinstance(accuracy, (int, float)) else 'warn',
            'message': f'Evaluation accuracy computed: {accuracy:.3f}.' if isinstance(accuracy, (int, float)) else 'Evaluation accuracy was not computed.',
        },
        {'status': 'pass', 'message': 'MosaicML submission is not performed by local preflight.'},
    ]
    return checks


def _slash_arg(action: str, index: int) -> str | None:
    parts = _action_parts(action)
    if not parts or not parts[0].startswith('/'):
        return None
    if index >= len(parts):
        return None
    return parts[index]


def _empty_metrics() -> dict[str, Any]:
    return {
        'record_count': 0,
        'correct_count': 0,
        'accuracy': None,
        'action_family_correct_count': 0,
        'action_family_accuracy': None,
        'action_component_accuracy': {},
    }


def _group_label(value: Any) -> str:
    if value is None or str(value).strip() == '':
        return 'unknown'
    return str(value)


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'mosaicml-command-head-policy'


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_float(value: Any) -> str:
    return f'{float(value):.4f}' if isinstance(value, (int, float)) else 'n/a'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
