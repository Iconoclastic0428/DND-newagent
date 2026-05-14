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
            'feature_template': 'state_summary_sparse_features_v2_candidate_aware_arguments',
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
            features = _command_features(row)
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
    features = _command_features(row)
    family = _predict_head(features, model['heads'].get('command_family'), candidate_labels=_available_command_families(row))
    if family is None:
        return ''
    if not family.startswith('/'):
        natural = _predict_head(features, model['heads'].get('natural_action'))
        return natural or family
    parts = [family]
    arg_count = _predicted_arg_count(features, model)
    for index in range(1, arg_count + 1):
        arg = _predict_head(features, model['heads'].get(f'command_arg_{index}'), candidate_labels=_argument_candidates(row, family, index, for_decoding=True))
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


def _predict_head(
    features: Counter[str],
    head: dict[str, Any] | None,
    *,
    candidate_labels: list[str] | None = None,
) -> str | None:
    if not isinstance(head, dict):
        return None
    labels = head.get('labels')
    weights = head.get('weights')
    if not isinstance(labels, list) or not labels or not isinstance(weights, dict):
        return None
    if candidate_labels:
        constrained = sorted({label for label in candidate_labels if label})
        if constrained:
            labels = constrained
    return _predict_label(features, weights, labels)


def _predict_label(features: Counter[str], weights: dict[str, Counter[str]], labels: list[str]) -> str:
    return sorted(labels, key=lambda label: (-_score(features, weights.get(label, Counter())), label))[0]


def _command_features(row: dict[str, Any]) -> Counter[str]:
    features = _features(row)
    if str(row.get('runtime_mode') or '').strip().lower() != 'combat':
        return features
    for action in _available_action_items(row):
        group_id = _normalized_option(action.get('group_id') if isinstance(action, dict) else None)
        option_id = _normalized_option(action.get('option_id') if isinstance(action, dict) else None)
        label = _normalized_option(action.get('label') if isinstance(action, dict) else None)
        if group_id:
            features[f'command_available_group={group_id}'] += 1.0
        _add_available_option_features(features, group_id=group_id, option_id=option_id, label=label)
        for family in _inferred_command_families(group_id=group_id, option_id=option_id, label=label):
            features[f'command_available_family={family}'] += 1.0
            if group_id:
                features[f'command_available_family_group={group_id}:{family}'] += 1.0
    _add_literal_command_candidate_features(features, row)
    _add_visible_combat_actor_features(features, row)
    return features


def _available_action_items(row: dict[str, Any]) -> list[Any]:
    items: list[Any] = []
    available_actions = row.get('available_actions')
    if isinstance(available_actions, list):
        items.extend(available_actions[:80])
    observation = row.get('observation') if isinstance(row.get('observation'), dict) else {}
    choices = observation.get('available_choices') if isinstance(observation.get('available_choices'), dict) else {}
    for choice_rows in choices.values():
        if isinstance(choice_rows, list):
            items.extend(choice_rows[:80])
    return items


def _inferred_command_families(*, group_id: str, option_id: str, label: str) -> list[str]:
    families: set[str] = set()
    for value in (option_id, label):
        if value in ACTION_OPTION_FAMILIES:
            families.add(ACTION_OPTION_FAMILIES[value])
    if group_id == 'attacks':
        families.add('/attack')
    return sorted(families)


def _add_available_option_features(features: Counter[str], *, group_id: str, option_id: str, label: str) -> None:
    if option_id:
        if group_id:
            features[f'command_available_option={group_id}:{option_id}'] += 1.0
        else:
            features[f'command_available_option={option_id}'] += 1.0
    if label and group_id:
        features[f'command_available_label={group_id}:{label}'] += 1.0
    if group_id == 'attacks':
        if option_id:
            features[f'command_attack_option={option_id}'] += 1.0
        if label:
            features[f'command_attack_label={label}'] += 1.0


def _add_literal_command_candidate_features(features: Counter[str], row: dict[str, Any]) -> None:
    for parts in _available_literal_command_parts(row):
        if not parts:
            continue
        features[f'command_candidate_family={parts[0]}'] += 1.0
        for index, value in enumerate(parts[1:5], start=1):
            features[f'command_candidate_arg_{index}={value}'] += 1.0
            features[f'command_candidate_family_arg_{index}={parts[0]}:{value}'] += 1.0


def _available_literal_command_parts(row: dict[str, Any]) -> list[list[str]]:
    parts_rows: list[list[str]] = []
    for action in _available_action_items(row):
        parts = _action_parts(_available_action_command(action))
        if parts and parts[0].startswith('/'):
            parts_rows.append(parts)
    return parts_rows


def _add_visible_combat_actor_features(features: Counter[str], row: dict[str, Any]) -> None:
    state = row.get('state_before') if isinstance(row.get('state_before'), dict) else {}
    active_side = str(state.get('active_actor_side') or '').strip().lower()
    for actor_id in _visible_combat_actor_ids(row):
        features[f'command_visible_actor={actor_id}'] += 1.0
        if actor_id.startswith('monster-'):
            features['command_visible_actor_side=monster'] += 1.0
            if active_side == 'player':
                features[f'command_candidate_target={actor_id}'] += 1.0
        elif actor_id.startswith('player-'):
            features['command_visible_actor_side=player'] += 1.0
            if active_side == 'monster':
                features[f'command_candidate_target={actor_id}'] += 1.0


def _visible_combat_actor_ids(row: dict[str, Any]) -> list[str]:
    observation = row.get('observation') if isinstance(row.get('observation'), dict) else {}
    summary_lines = observation.get('summary_lines') if isinstance(observation.get('summary_lines'), list) else []
    actor_ids: set[str] = set()
    for line in summary_lines:
        if not isinstance(line, str) or ':' not in line:
            continue
        actor_id = line.split(':', 1)[0].strip().lower()
        if actor_id.startswith(('player-', 'monster-')) and ' ' not in actor_id:
            actor_ids.add(actor_id)
    return sorted(actor_ids)

def _normalized_option(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    return value.strip().lower().replace(' ', '-')


def _available_command_families(row: dict[str, Any]) -> list[str]:
    if str(row.get('runtime_mode') or '').strip().lower() != 'combat':
        return []
    available_actions = row.get('available_actions')
    if not isinstance(available_actions, list):
        return []
    families: set[str] = set()
    for action in available_actions:
        parts = _action_parts(_available_action_command(action))
        if not parts or not parts[0].startswith('/'):
            continue
        families.add(parts[0])
    return sorted(families)


def _available_command_parts(row: dict[str, Any], family: str) -> list[list[str]]:
    available_actions = row.get('available_actions')
    if not isinstance(available_actions, list):
        return []
    result: list[list[str]] = []
    for action in available_actions:
        parts = _action_parts(_available_action_command(action))
        if parts and parts[0] == family:
            result.append(parts)
    return result


def _available_action_command(action: Any) -> str:
    if isinstance(action, str):
        return action
    if not isinstance(action, dict):
        return ''
    for key in ('command', 'action', 'id'):
        value = action.get(key)
        if isinstance(value, str) and value.strip().startswith('/'):
            return value
    return ''


def _argument_candidates(row: dict[str, Any], family: str, index: int, *, for_decoding: bool) -> list[str]:
    candidates: set[str] = set(_candidate_args(_available_command_parts(row, family), index))
    if family == '/attack' and index == 3:
        candidates.update(_target_argument_candidates(row))
    if index == 1:
        for value in _actor_argument_candidates(row):
            candidates.add(value)
    if not for_decoding and family == '/attack' and index == 2:
        candidates.update(_attack_option_candidates(row))
    return sorted(candidate for candidate in candidates if candidate)


def _actor_argument_candidates(row: dict[str, Any]) -> list[str]:
    values = [row.get('acting_actor_id')]
    state = row.get('state_before') if isinstance(row.get('state_before'), dict) else {}
    values.append(state.get('active_actor_id'))
    return sorted({str(value).strip().lower() for value in values if isinstance(value, str) and value.strip()})


def _attack_option_candidates(row: dict[str, Any]) -> list[str]:
    options: set[str] = set()
    for action in _available_action_items(row):
        if not isinstance(action, dict):
            continue
        if _normalized_option(action.get('group_id')) == 'attacks':
            option_id = _normalized_option(action.get('option_id'))
            if option_id:
                options.add(option_id)
    return sorted(options)


def _candidate_args(available_parts: list[list[str]], index: int) -> list[str]:
    return sorted({parts[index] for parts in available_parts if index < len(parts)})


def _target_argument_candidates(row: dict[str, Any]) -> list[str]:
    state = row.get('state_before') if isinstance(row.get('state_before'), dict) else {}
    active_side = str(state.get('active_actor_side') or '').strip().lower()
    targets: set[str] = set()
    for actor_id in _visible_combat_actor_ids(row):
        if actor_id.startswith('monster-') and active_side == 'player':
            targets.add(actor_id)
        elif actor_id.startswith('player-') and active_side == 'monster':
            targets.add(actor_id)
    return sorted(targets)


def _score(features: Counter[str], weights: Counter[str]) -> float:
    return sum(weights.get(feature, 0.0) * value for feature, value in features.items())


def _evaluate_rows(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return _empty_metrics()
    correct = 0
    family_correct = 0
    component_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'correct_count': 0, 'record_count': 0})
    candidate_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'covered_count': 0, 'record_count': 0})
    for row in rows:
        expected = str(row.get('action') or '')
        predicted = _predict_command(row, model)
        if predicted == expected:
            correct += 1
        if _action_family(predicted) == _action_family(expected):
            family_correct += 1
        _update_argument_candidate_counts(candidate_counts, row, expected=expected)
        _update_action_component_counts(component_counts, predicted=predicted, expected=expected)
    return {
        'record_count': len(rows),
        'correct_count': correct,
        'accuracy': correct / len(rows),
        'action_family_correct_count': family_correct,
        'action_family_accuracy': family_correct / len(rows),
        'action_component_accuracy': _component_accuracy(component_counts),
        'argument_candidate_coverage': _candidate_coverage(candidate_counts),
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


def _update_argument_candidate_counts(
    counts: dict[str, dict[str, int]],
    row: dict[str, Any],
    *,
    expected: str,
) -> None:
    expected_parts = _action_parts(expected)
    if not expected_parts or not expected_parts[0].startswith('/'):
        return
    family = expected_parts[0]
    for index, expected_arg in enumerate(expected_parts[1:5], start=1):
        candidates = _argument_candidates(row, family, index, for_decoding=False)
        if not candidates:
            continue
        key = f'arg_{index}'
        counts[key]['record_count'] += 1
        if expected_arg in candidates:
            counts[key]['covered_count'] += 1


def _candidate_coverage(counts: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for component, item in sorted(counts.items()):
        total = item['record_count']
        covered = item['covered_count']
        result[component] = {
            'record_count': total,
            'covered_count': covered,
            'coverage': covered / total if total else None,
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


ACTION_OPTION_FAMILIES = {
    'attack': '/attack',
    'dash': '/dash',
    'disengage': '/disengage',
    'dodge': '/dodge',
    'end-turn': '/endturn',
    'endturn': '/endturn',
    'grapple': '/grapple',
    'help': '/help',
    'hide': '/hide',
    'ready': '/ready',
    'search': '/search',
    'shove': '/shove',
    'study': '/study',
    'utilize': '/utilize',
}


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_float(value: Any) -> str:
    return f'{float(value):.4f}' if isinstance(value, (int, float)) else 'n/a'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
