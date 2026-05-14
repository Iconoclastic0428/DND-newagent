from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from training.supervised_baseline import SUPERVISED_BASELINE_SCHEMA_VERSION
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


TRAINABLE_POLICY_SCHEMA_VERSION = 'dnd-agents-trainable-policy-run-v1'
SUPERVISED_OBJECTIVE = 'supervised_action_prediction'
BREAKDOWN_FIELDS = ('scenario_id', 'runtime_mode')
SPLIT_STRATEGIES = {'hash', 'tail'}
TOKEN_RE = re.compile(r'[a-z0-9_./:-]+')
STOP_WORDS = {
    'the',
    'and',
    'for',
    'with',
    'that',
    'this',
    'from',
    'are',
    'you',
    'your',
    'into',
    'mode',
    'runtime',
    'current',
    'available',
}


class TrainablePolicyError(RuntimeError):
    pass


def run_trainable_policy_preflight(
    recipe_path: str | Path,
    *,
    baseline_report_path: str | Path,
    output_dir: str | Path,
    run_name: str = 'mosaicml-trainable-policy',
    epochs: int = 8,
    learning_rate: float = 1.0,
    holdout_fraction: float = 0.2,
    split_strategy: str = 'hash',
    max_records: int | None = None,
) -> dict[str, Any]:
    if epochs <= 0:
        raise TrainablePolicyError('epochs must be greater than 0.')
    if learning_rate <= 0:
        raise TrainablePolicyError('learning_rate must be greater than 0.')
    if not 0.0 <= holdout_fraction < 1.0:
        raise TrainablePolicyError('holdout_fraction must be at least 0 and less than 1.')
    if split_strategy not in SPLIT_STRATEGIES:
        raise TrainablePolicyError(f'split_strategy must be one of: {", ".join(sorted(SPLIT_STRATEGIES))}.')
    if max_records is not None and max_records <= 0:
        raise TrainablePolicyError('max_records must be greater than 0 when provided.')

    recipe_file = Path(recipe_path)
    baseline_file = Path(baseline_report_path)
    recipe = _load_json_object(recipe_file, label='training recipe')
    baseline = _load_json_object(baseline_file, label='supervised baseline report')
    if recipe.get('schema_version') != TRAINING_RECIPE_SCHEMA_VERSION:
        raise TrainablePolicyError(f'Unsupported recipe schema: {recipe.get("schema_version")!r}.')
    if baseline.get('schema_version') != SUPERVISED_BASELINE_SCHEMA_VERSION:
        raise TrainablePolicyError(f'Unsupported baseline schema: {baseline.get("schema_version")!r}.')
    objective = _supervised_objective(recipe)
    if objective is None:
        raise TrainablePolicyError(f'Recipe has no {SUPERVISED_OBJECTIVE!r} objective.')
    dataset_path_value = objective.get('dataset_path')
    if not isinstance(dataset_path_value, str) or not dataset_path_value:
        raise TrainablePolicyError('Supervised objective has no dataset_path.')
    dataset_path = Path(dataset_path_value)
    if not dataset_path.exists():
        raise TrainablePolicyError(f'Supervised dataset does not exist: {dataset_path}')
    rows = _load_transition_rows(dataset_path)
    if max_records is not None:
        rows = rows[:max_records]
    if not rows:
        raise TrainablePolicyError('Supervised dataset has no usable action rows.')
    train_rows, eval_rows = _split_rows(rows, holdout_fraction=holdout_fraction, strategy=split_strategy)
    if not train_rows:
        raise TrainablePolicyError('Trainable policy needs at least one training row.')

    model = _train_linear_policy(train_rows, epochs=epochs, learning_rate=learning_rate)
    train_metrics = _evaluate_rows(train_rows, model)
    eval_metrics = _evaluate_rows(eval_rows, model) if eval_rows else _empty_metrics()
    output_path = Path(output_dir)
    run_id = f'{_safe_token(run_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = output_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model_path = run_dir / 'trainable_policy_model.json'
    report_path = run_dir / 'trainable_policy_report.json'
    markdown_path = run_dir / 'trainable_policy_report.md'
    model_path.write_text(json.dumps(_model_artifact(model), ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    metrics = {
        'train': train_metrics,
        'eval': eval_metrics,
        'breakdowns': {
            'train': _metric_breakdowns(train_rows, model),
            'eval': _metric_breakdowns(eval_rows, model),
        },
    }
    report: dict[str, Any] = {
        'schema_version': TRAINABLE_POLICY_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_id': run_id,
        'run_name': run_name,
        'run_mode': 'local_trainable_policy_preflight',
        'output_dir': str(run_dir),
        'recipe_path': str(recipe_file),
        'recipe_id': recipe.get('recipe_id'),
        'baseline_report_path': str(baseline_file),
        'dataset_path': str(dataset_path),
        'objective': SUPERVISED_OBJECTIVE,
        'trainer_backend': {
            'name': 'sparse_linear_perceptron',
            'updates_model_weights': True,
            'mosaicml_submission_status': 'not_submitted_local_preflight',
        },
        'model': {
            'kind': 'sparse_linear_action_policy',
            'feature_template': 'state_summary_sparse_features_v2',
            'epochs': epochs,
            'learning_rate': learning_rate,
            'action_vocab_size': len(model['actions']),
            'feature_count': len(model['feature_vocab']),
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
    markdown_path.write_text(render_trainable_policy_markdown(report), encoding='utf-8')
    return report


def render_trainable_policy_markdown(report: dict[str, Any]) -> str:
    split = report.get('split') if isinstance(report.get('split'), dict) else {}
    model = report.get('model') if isinstance(report.get('model'), dict) else {}
    metrics = report.get('metrics') if isinstance(report.get('metrics'), dict) else {}
    train = metrics.get('train') if isinstance(metrics.get('train'), dict) else {}
    eval_metrics = metrics.get('eval') if isinstance(metrics.get('eval'), dict) else {}
    comparison = report.get('baseline_comparison') if isinstance(report.get('baseline_comparison'), dict) else {}
    overall = comparison.get('overall') if isinstance(comparison.get('overall'), dict) else {}
    lines = [
        '# Trainable Policy Preflight',
        '',
        f'Run: **{_markdown_text(report.get("run_id"))}**',
        f'Mode: {_markdown_text(report.get("run_mode"))}',
        f'Recipe: {_markdown_text(report.get("recipe_id"))}',
        f'Dataset: {_markdown_text(report.get("dataset_path"))}',
        f'Model: {_markdown_text(model.get("kind"))}',
        f'Epochs: {_format_int(model.get("epochs"))}',
        f'Features: {_format_int(model.get("feature_count"))}',
        '',
        '## Split',
        '',
        f'Strategy: {_markdown_text(split.get("strategy"))}',
        f'Train records: {_format_int(split.get("train_records"))}',
        f'Eval records: {_format_int(split.get("eval_records"))}',
        '',
        '## Metrics',
        '',
        '| Split | Records | Accuracy | Family Accuracy | Negative Log Loss |',
        '| --- | ---: | ---: | ---: | ---: |',
        f'| train | {_format_int(train.get("record_count"))} | {_format_float(train.get("accuracy"))} | {_format_float(train.get("action_family_accuracy"))} | {_format_float(train.get("negative_log_likelihood"))} |',
        f'| eval | {_format_int(eval_metrics.get("record_count"))} | {_format_float(eval_metrics.get("accuracy"))} | {_format_float(eval_metrics.get("action_family_accuracy"))} | {_format_float(eval_metrics.get("negative_log_likelihood"))} |',
        '',
    ]
    component_metrics = eval_metrics.get('action_component_accuracy') if isinstance(eval_metrics.get('action_component_accuracy'), dict) else {}
    if component_metrics:
        lines.extend([
            '## Component Accuracy',
            '',
            '| Component | Records | Correct | Accuracy |',
            '| --- | ---: | ---: | ---: |',
        ])
        for component in sorted(component_metrics):
            item = component_metrics[component] if isinstance(component_metrics[component], dict) else {}
            lines.append(f'| {_markdown_text(component)} | {_format_int(item.get("record_count"))} | {_format_int(item.get("correct_count"))} | {_format_float(item.get("accuracy"))} |')
        lines.append('')
    lines.extend([
        '## Baseline Comparison',
        '',
        '| Scope | Baseline Accuracy | Policy Accuracy | Delta | Beats Baseline |',
        '| --- | ---: | ---: | ---: | --- |',
        f'| overall | {_format_float(overall.get("baseline_accuracy"))} | {_format_float(overall.get("policy_accuracy"))} | {_format_float(overall.get("accuracy_delta"))} | {_markdown_text(overall.get("beats_baseline"))} |',
    ])
    breakdowns = comparison.get('breakdowns') if isinstance(comparison.get('breakdowns'), dict) else {}
    for field in BREAKDOWN_FIELDS:
        groups = breakdowns.get(field)
        if not isinstance(groups, dict):
            continue
        for value in sorted(groups):
            item = groups[value] if isinstance(groups[value], dict) else {}
            lines.append(
                f'| {field}:{_markdown_text(value)} | {_format_float(item.get("baseline_accuracy"))} | {_format_float(item.get("policy_accuracy"))} | {_format_float(item.get("accuracy_delta"))} | {_markdown_text(item.get("beats_baseline"))} |'
            )
    lines.append('')
    return '\n'.join(lines)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise TrainablePolicyError(f'{label.title()} does not exist: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise TrainablePolicyError(f'Invalid {label} JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise TrainablePolicyError(f'{label.title()} at {path} must be a JSON object.')
    return payload


def _supervised_objective(recipe: dict[str, Any]) -> dict[str, Any] | None:
    objectives = recipe.get('objectives')
    if not isinstance(objectives, list):
        return None
    for objective in objectives:
        if isinstance(objective, dict) and objective.get('objective') == SUPERVISED_OBJECTIVE:
            return objective
    return None


def _load_transition_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TrainablePolicyError(f'Invalid transition JSONL at {path}:{line_number}: {exc}') from exc
        if not isinstance(row, dict):
            continue
        action = row.get('action')
        if isinstance(action, str) and action.strip():
            rows.append(row)
    return sorted(rows, key=lambda row: str(row.get('sample_id') or ''))


def _split_rows(rows: list[dict[str, Any]], *, holdout_fraction: float, strategy: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(rows) < 2 or holdout_fraction == 0:
        return rows, []
    eval_count = max(1, int(round(len(rows) * holdout_fraction)))
    eval_count = min(eval_count, len(rows) - 1)
    if strategy == 'hash':
        ranked = sorted(rows, key=lambda row: (_stable_split_score(row), str(row.get('sample_id') or '')))
        eval_ids = {id(row) for row in ranked[:eval_count]}
        return [row for row in rows if id(row) not in eval_ids], [row for row in rows if id(row) in eval_ids]
    if strategy != 'tail':
        raise TrainablePolicyError(f'Unsupported split strategy: {strategy!r}.')
    split_at = len(rows) - eval_count
    return rows[:split_at], rows[split_at:]


def _stable_split_score(row: dict[str, Any]) -> str:
    key = str(row.get('sample_id') or json.dumps(row, ensure_ascii=False, sort_keys=True))
    return sha256(key.encode('utf-8')).hexdigest()


def _train_linear_policy(rows: list[dict[str, Any]], *, epochs: int, learning_rate: float) -> dict[str, Any]:
    actions = sorted({str(row.get('action') or '') for row in rows})
    weights: dict[str, Counter[str]] = {action: Counter() for action in actions}
    feature_vocab: Counter[str] = Counter()
    for epoch in range(epochs):
        for row in sorted(rows, key=lambda item: (str(item.get('sample_id') or ''), epoch)):
            expected = str(row.get('action') or '')
            features = _features(row)
            feature_vocab.update(features)
            predicted = _predict_action(features, weights, actions)
            if predicted == expected:
                continue
            for feature, value in features.items():
                weights[expected][feature] += learning_rate * value
                weights[predicted][feature] -= learning_rate * value
    return {
        'actions': actions,
        'weights': weights,
        'feature_vocab': feature_vocab,
        'epochs': epochs,
        'learning_rate': learning_rate,
    }


def _features(row: dict[str, Any]) -> Counter[str]:
    features: Counter[str] = Counter()
    features['bias'] = 1.0
    for field in ('runtime_mode', 'agent_id', 'scenario_id', 'source', 'role'):
        _add_value_feature(features, field, row.get(field))
    _add_value_feature(features, 'acting_actor_id', row.get('acting_actor_id'))
    parsed_action = row.get('parsed_action') if isinstance(row.get('parsed_action'), dict) else {}
    _add_value_feature(features, 'parsed_kind', parsed_action.get('kind'))
    state = row.get('state_before') if isinstance(row.get('state_before'), dict) else {}
    for field in ('scene_id', 'location_id', 'active_actor_id', 'active_actor_side', 'encounter_phase'):
        _add_value_feature(features, f'state_{field}', state.get(field))
    _add_value_feature(features, 'round_bucket', _number_bucket(state.get('round_number'), size=2))
    _add_value_feature(features, 'event_bucket', _number_bucket(state.get('event_count'), size=10))
    _add_value_feature(features, 'transcript_bucket', _number_bucket(state.get('transcript_count'), size=5))
    _add_value_feature(features, 'living_monsters', state.get('living_monster_count'))
    _add_value_feature(features, 'living_party', state.get('living_party_count'))
    _add_value_feature(features, 'party_hp_bucket', _ratio_bucket(state.get('party_hp_current'), state.get('party_hp_max')))
    _add_value_feature(features, 'monster_hp_bucket', _ratio_bucket(state.get('monster_hp_current'), state.get('monster_hp_max')))
    available_actions = row.get('available_actions')
    if isinstance(available_actions, list):
        _add_value_feature(features, 'available_action_count', _number_bucket(len(available_actions), size=2))
        for action in available_actions[:40]:
            for token in _action_tokens(action):
                features[f'available:{token}'] += 1.0
    observation = row.get('observation') if isinstance(row.get('observation'), dict) else {}
    groups = observation.get('available_action_groups') if isinstance(observation.get('available_action_groups'), list) else []
    for group in groups:
        _add_value_feature(features, 'available_group', group)
    choices = observation.get('available_choices') if isinstance(observation.get('available_choices'), dict) else {}
    for group, choice_rows in sorted(choices.items()):
        if isinstance(choice_rows, list):
            for choice in choice_rows[:40]:
                for token in _action_tokens(choice):
                    features[f'choice:{group}:{token}'] += 1.0
    summary_lines = observation.get('summary_lines') if isinstance(observation.get('summary_lines'), list) else []
    token_count = 0
    for line in summary_lines:
        if not isinstance(line, str):
            continue
        for token in _text_tokens(line):
            features[f'obs:{token}'] += 1.0
            token_count += 1
            if token_count >= 80:
                return features
    return features


def _add_value_feature(features: Counter[str], name: str, value: Any) -> None:
    if value is None or str(value).strip() == '':
        return
    features[f'{name}={value}'] += 1.0


def _action_tokens(action: Any) -> list[str]:
    if isinstance(action, str):
        return _text_tokens(action)
    if not isinstance(action, dict):
        return []
    text_parts: list[str] = []
    for key in ('id', 'command', 'label', 'name', 'description'):
        value = action.get(key)
        if isinstance(value, str):
            text_parts.append(value)
    return _text_tokens(' '.join(text_parts))


def _text_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text.lower()):
        if len(token) < 3 or token in STOP_WORDS:
            continue
        tokens.append(token[:48])
    return tokens


def _number_bucket(value: Any, *, size: int) -> str:
    if not isinstance(value, (int, float)):
        return 'unknown'
    bucket = int(value // size) * size
    return f'{bucket}-{bucket + size - 1}'


def _ratio_bucket(current: Any, maximum: Any) -> str:
    if not isinstance(current, (int, float)) or not isinstance(maximum, (int, float)) or maximum <= 0:
        return 'unknown'
    ratio = max(0.0, min(1.0, float(current) / float(maximum)))
    bucket = int(ratio * 4)
    if bucket >= 4:
        return 'full'
    return f'q{bucket + 1}'


def _predict_action(features: Counter[str], weights: dict[str, Counter[str]], actions: list[str]) -> str:
    return sorted(actions, key=lambda action: (-_score(features, weights[action]), action))[0]


def _score(features: Counter[str], weights: Counter[str]) -> float:
    return sum(weights.get(feature, 0.0) * value for feature, value in features.items())


def _evaluate_rows(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return _empty_metrics()
    correct = 0
    family_correct = 0
    component_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'correct_count': 0, 'record_count': 0})
    total_loss = 0.0
    for row in rows:
        expected = str(row.get('action') or '')
        features = _features(row)
        predicted = _predict_action(features, model['weights'], model['actions'])
        if predicted == expected:
            correct += 1
        if _action_family(predicted) == _action_family(expected):
            family_correct += 1
        _update_action_component_counts(component_counts, predicted=predicted, expected=expected)
        total_loss += -math.log(max(_action_probability(features, expected, model), 1e-12))
    return {
        'record_count': len(rows),
        'correct_count': correct,
        'accuracy': correct / len(rows),
        'action_family_correct_count': family_correct,
        'action_family_accuracy': family_correct / len(rows),
        'action_component_accuracy': _component_accuracy(component_counts),
        'negative_log_likelihood': total_loss / len(rows),
    }


def _action_probability(features: Counter[str], expected: str, model: dict[str, Any]) -> float:
    actions = model['actions']
    if expected not in actions:
        return 1e-12
    scores = {action: _score(features, model['weights'][action]) for action in actions}
    max_score = max(scores.values()) if scores else 0.0
    exp_scores = {action: math.exp(max(-60.0, min(60.0, score - max_score))) for action, score in scores.items()}
    denominator = sum(exp_scores.values())
    if denominator <= 0:
        return 1.0 / max(len(actions), 1)
    return exp_scores[expected] / denominator


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
    comparison = {
        'overall': _compare_metric(policy_eval, baseline_eval),
        'breakdowns': {},
    }
    policy_breakdowns = metrics.get('breakdowns') if isinstance(metrics.get('breakdowns'), dict) else {}
    policy_eval_breakdowns = policy_breakdowns.get('eval') if isinstance(policy_breakdowns.get('eval'), dict) else {}
    baseline_breakdowns = baseline_metrics.get('breakdowns') if isinstance(baseline_metrics.get('breakdowns'), dict) else {}
    baseline_eval_breakdowns = baseline_breakdowns.get('eval') if isinstance(baseline_breakdowns.get('eval'), dict) else {}
    for field in BREAKDOWN_FIELDS:
        policy_groups = policy_eval_breakdowns.get(field) if isinstance(policy_eval_breakdowns.get(field), dict) else {}
        baseline_groups = baseline_eval_breakdowns.get(field) if isinstance(baseline_eval_breakdowns.get(field), dict) else {}
        values = sorted(set(policy_groups) | set(baseline_groups))
        comparison['breakdowns'][field] = {
            value: _compare_metric(
                policy_groups.get(value) if isinstance(policy_groups.get(value), dict) else {},
                baseline_groups.get(value) if isinstance(baseline_groups.get(value), dict) else {},
            )
            for value in values
        }
    return comparison


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
    action_summaries: dict[str, Any] = {}
    for action in model['actions']:
        weights = model['weights'][action]
        action_summaries[action] = {
            'nonzero_feature_count': sum(1 for value in weights.values() if value),
            'top_positive_features': [
                {'feature': feature, 'weight': weight}
                for feature, weight in sorted(weights.items(), key=lambda item: (-item[1], item[0]))[:12]
                if weight > 0
            ],
        }
    return {
        'schema_version': 'dnd-agents-sparse-linear-policy-v1',
        'kind': 'sparse_linear_action_policy',
        'feature_template': 'state_summary_sparse_features_v2',
        'epochs': model['epochs'],
        'learning_rate': model['learning_rate'],
        'action_vocab_size': len(model['actions']),
        'feature_count': len(model['feature_vocab']),
        'actions': action_summaries,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        'record_count': 0,
        'correct_count': 0,
        'accuracy': None,
        'action_family_correct_count': 0,
        'action_family_accuracy': None,
        'action_component_accuracy': {},
        'negative_log_likelihood': None,
    }


def _split_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        'scenario_counts': _counter_dict(row.get('scenario_id') for row in rows),
        'runtime_mode_counts': _counter_dict(row.get('runtime_mode') for row in rows),
        'source_counts': _counter_dict(row.get('source') for row in rows),
        'agent_counts': _counter_dict(row.get('agent_id') for row in rows),
    }


def _counter_dict(values: Iterable[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for value in values:
        if value is None:
            continue
        counts[str(value)] += 1
    return dict(sorted(counts.items()))


def _run_checks(
    *,
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    eval_metrics: dict[str, Any],
) -> list[dict[str, str]]:
    checks = [
        {'status': 'pass' if train_rows else 'fail', 'message': f'Training split has {len(train_rows)} rows.'},
        {'status': 'pass' if eval_rows else 'warn', 'message': f'Evaluation split has {len(eval_rows)} rows.'},
    ]
    accuracy = eval_metrics.get('accuracy')
    if isinstance(accuracy, (int, float)):
        checks.append({'status': 'pass', 'message': f'Evaluation accuracy computed: {accuracy:.3f}.'})
    else:
        checks.append({'status': 'warn', 'message': 'Evaluation accuracy was not computed.'})
    checks.append({'status': 'pass', 'message': 'MosaicML submission is not performed by local preflight.'})
    return checks


def _group_label(value: Any) -> str:
    if value is None or str(value).strip() == '':
        return 'unknown'
    return str(value)


def _update_action_component_counts(
    counts: dict[str, dict[str, int]],
    *,
    predicted: str,
    expected: str,
) -> None:
    predicted_parts = _action_parts(predicted)
    expected_parts = _action_parts(expected)
    if not expected_parts:
        return
    _count_component(counts, 'family', _action_family(predicted) == _action_family(expected))
    if not expected_parts[0].startswith('/'):
        expected_tokens = _text_tokens(expected)[:3]
        predicted_tokens = _text_tokens(predicted)[:3]
        for index, expected_token in enumerate(expected_tokens, start=1):
            predicted_token = predicted_tokens[index - 1] if index <= len(predicted_tokens) else ''
            _count_component(counts, f'natural_token_{index}', predicted_token == expected_token)
        return
    for index, expected_arg in enumerate(expected_parts[1:5], start=1):
        predicted_arg = predicted_parts[index] if index < len(predicted_parts) else ''
        _count_component(counts, f'arg_{index}', predicted_arg == expected_arg)


def _count_component(counts: dict[str, dict[str, int]], component: str, correct: bool) -> None:
    counts[component]['record_count'] += 1
    if correct:
        counts[component]['correct_count'] += 1


def _component_accuracy(counts: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for component, item in sorted(counts.items()):
        total = item['record_count']
        result[component] = {
            'record_count': total,
            'correct_count': item['correct_count'],
            'accuracy': item['correct_count'] / total if total else None,
        }
    return result


def _action_parts(action: str) -> list[str]:
    return action.strip().lower().split()


def _action_family(action: str) -> str:
    text = action.strip().lower()
    if not text:
        return 'unknown'
    first = text.split()[0]
    if first.startswith('/'):
        return first
    tokens = _text_tokens(text)
    return f'natural:{tokens[0]}' if tokens else 'natural_language'


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'mosaicml-trainable-policy'


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_float(value: Any) -> str:
    return f'{float(value):.4f}' if isinstance(value, (int, float)) else 'n/a'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
