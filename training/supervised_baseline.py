from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


SUPERVISED_BASELINE_SCHEMA_VERSION = 'dnd-agents-supervised-baseline-v1'
SUPERVISED_OBJECTIVE = 'supervised_action_prediction'
CONTEXT_FIELDS = ('runtime_mode', 'agent_id')
SPLIT_STRATEGIES = {'hash', 'tail'}


class SupervisedBaselineError(RuntimeError):
    pass


def run_supervised_action_baseline(
    recipe_path: str | Path,
    *,
    output_dir: str | Path,
    run_name: str = 'supervised-baseline',
    holdout_fraction: float = 0.2,
    smoothing_alpha: float = 1.0,
    max_records: int | None = None,
    split_strategy: str = 'hash',
) -> dict[str, Any]:
    if not 0.0 <= holdout_fraction < 1.0:
        raise SupervisedBaselineError('holdout_fraction must be at least 0 and less than 1.')
    if smoothing_alpha <= 0:
        raise SupervisedBaselineError('smoothing_alpha must be greater than 0.')
    if max_records is not None and max_records <= 0:
        raise SupervisedBaselineError('max_records must be greater than 0 when provided.')
    if split_strategy not in SPLIT_STRATEGIES:
        raise SupervisedBaselineError(f'split_strategy must be one of: {", ".join(sorted(SPLIT_STRATEGIES))}.')

    path = Path(recipe_path)
    recipe = _load_recipe(path)
    if recipe.get('schema_version') != TRAINING_RECIPE_SCHEMA_VERSION:
        raise SupervisedBaselineError(f'Unsupported recipe schema: {recipe.get("schema_version")!r}.')
    objective = _supervised_objective(recipe)
    if objective is None:
        raise SupervisedBaselineError(f'Recipe has no {SUPERVISED_OBJECTIVE!r} objective.')
    dataset_path_value = objective.get('dataset_path')
    if not isinstance(dataset_path_value, str) or not dataset_path_value:
        raise SupervisedBaselineError('Supervised objective has no dataset_path.')
    dataset_path = Path(dataset_path_value)
    if not dataset_path.exists():
        raise SupervisedBaselineError(f'Supervised dataset does not exist: {dataset_path}')
    rows = _load_transition_rows(dataset_path)
    if max_records is not None:
        rows = rows[:max_records]
    if not rows:
        raise SupervisedBaselineError('Supervised dataset has no usable action rows.')
    train_rows, eval_rows = _split_rows(rows, holdout_fraction=holdout_fraction, strategy=split_strategy)
    if not train_rows:
        raise SupervisedBaselineError('Supervised baseline needs at least one training row.')

    model = _fit_frequency_model(train_rows, smoothing_alpha=smoothing_alpha)
    train_metrics = _evaluate_rows(train_rows, model)
    eval_metrics = _evaluate_rows(eval_rows, model) if eval_rows else _empty_metrics()
    output_path = Path(output_dir)
    run_id = f'{_safe_token(run_name)}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = output_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model_path = run_dir / 'supervised_action_frequency_model.json'
    report_path = run_dir / 'supervised_baseline_report.json'
    markdown_path = run_dir / 'supervised_baseline_report.md'
    model_artifact = _model_artifact(model)
    model_path.write_text(json.dumps(model_artifact, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    report: dict[str, Any] = {
        'schema_version': SUPERVISED_BASELINE_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_id': run_id,
        'run_name': run_name,
        'run_mode': 'supervised_action_frequency_baseline',
        'output_dir': str(run_dir),
        'recipe_path': str(path),
        'recipe_id': recipe.get('recipe_id'),
        'objective': SUPERVISED_OBJECTIVE,
        'dataset_path': str(dataset_path),
        'model_path': str(model_path),
        'model': {
            'kind': 'contextual_action_frequency',
            'context_fields': list(CONTEXT_FIELDS),
            'smoothing_alpha': smoothing_alpha,
            'context_count': len(model['context_counts']),
            'action_vocab_size': len(model['action_vocab']),
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
        'metrics': {
            'train': train_metrics,
            'eval': eval_metrics,
        },
        'checks': _baseline_checks(train_rows=train_rows, eval_rows=eval_rows, eval_metrics=eval_metrics),
    }
    report['report_path'] = str(report_path)
    report['markdown_path'] = str(markdown_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_supervised_baseline_markdown(report), encoding='utf-8')
    return report


def render_supervised_baseline_markdown(report: dict[str, Any]) -> str:
    split = report.get('split') if isinstance(report.get('split'), dict) else {}
    metrics = report.get('metrics') if isinstance(report.get('metrics'), dict) else {}
    train = metrics.get('train') if isinstance(metrics.get('train'), dict) else {}
    eval_metrics = metrics.get('eval') if isinstance(metrics.get('eval'), dict) else {}
    lines = [
        '# Supervised Action Baseline',
        '',
        f'Run: **{_markdown_text(report.get("run_id"))}**',
        f'Mode: {_markdown_text(report.get("run_mode"))}',
        f'Recipe: {_markdown_text(report.get("recipe_id"))}',
        f'Dataset: {_markdown_text(report.get("dataset_path"))}',
        '',
        '## Split',
        '',
        f'Strategy: {_markdown_text(split.get("strategy") or "unknown")}',
        f'Total records: {_format_int(split.get("total_records"))}',
        f'Train records: {_format_int(split.get("train_records"))}',
        f'Eval records: {_format_int(split.get("eval_records"))}',
        '',
        '## Metrics',
        '',
        '| Split | Records | Accuracy | Negative Log Loss |',
        '| --- | ---: | ---: | ---: |',
        f'| train | {_format_int(train.get("record_count"))} | {_format_float(train.get("accuracy"))} | {_format_float(train.get("negative_log_likelihood"))} |',
        f'| eval | {_format_int(eval_metrics.get("record_count"))} | {_format_float(eval_metrics.get("accuracy"))} | {_format_float(eval_metrics.get("negative_log_likelihood"))} |',
        '',
    ]
    coverage = split.get('coverage') if isinstance(split.get('coverage'), dict) else {}
    if coverage:
        lines.extend([
            '## Coverage',
            '',
            f'Train: {_coverage_summary(coverage.get("train"))}',
            f'Eval: {_coverage_summary(coverage.get("eval"))}',
            '',
        ])
    return '\n'.join(lines)


def _load_recipe(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SupervisedBaselineError(f'Training recipe does not exist: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise SupervisedBaselineError(f'Invalid training recipe JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise SupervisedBaselineError(f'Training recipe at {path} must be a JSON object.')
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
            raise SupervisedBaselineError(f'Invalid transition JSONL at {path}:{line_number}: {exc}') from exc
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
        train_rows = [row for row in rows if id(row) not in eval_ids]
        eval_rows = [row for row in rows if id(row) in eval_ids]
        return train_rows, eval_rows
    if strategy != 'tail':
        raise SupervisedBaselineError(f'Unsupported split strategy: {strategy!r}.')
    split_at = len(rows) - eval_count
    return rows[:split_at], rows[split_at:]


def _stable_split_score(row: dict[str, Any]) -> str:
    key = str(row.get('sample_id') or json.dumps(row, ensure_ascii=False, sort_keys=True))
    return sha256(key.encode('utf-8')).hexdigest()


def _fit_frequency_model(rows: list[dict[str, Any]], *, smoothing_alpha: float) -> dict[str, Any]:
    context_counts: dict[str, Counter[str]] = defaultdict(Counter)
    global_counts: Counter[str] = Counter()
    for row in rows:
        action = str(row.get('action') or '')
        context_key = _context_key(row)
        context_counts[context_key][action] += 1
        global_counts[action] += 1
    action_vocab = sorted(global_counts)
    return {
        'context_counts': context_counts,
        'global_counts': global_counts,
        'action_vocab': action_vocab,
        'smoothing_alpha': smoothing_alpha,
    }


def _evaluate_rows(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return _empty_metrics()
    correct = 0
    total_loss = 0.0
    for row in rows:
        expected_action = str(row.get('action') or '')
        prediction = _predict_action(row, model)
        if prediction == expected_action:
            correct += 1
        probability = _action_probability(row, expected_action, model)
        total_loss += -math.log(max(probability, 1e-12))
    return {
        'record_count': len(rows),
        'correct_count': correct,
        'accuracy': correct / len(rows),
        'negative_log_likelihood': total_loss / len(rows),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        'record_count': 0,
        'correct_count': 0,
        'accuracy': None,
        'negative_log_likelihood': None,
    }


def _predict_action(row: dict[str, Any], model: dict[str, Any]) -> str | None:
    counts = _counts_for_row(row, model)
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _action_probability(row: dict[str, Any], action: str, model: dict[str, Any]) -> float:
    counts = _counts_for_row(row, model)
    alpha = float(model['smoothing_alpha'])
    vocab = set(model['action_vocab'])
    vocab.add(action)
    denominator = sum(counts.values()) + alpha * len(vocab)
    if denominator <= 0:
        return 1.0 / max(len(vocab), 1)
    return (counts.get(action, 0) + alpha) / denominator


def _counts_for_row(row: dict[str, Any], model: dict[str, Any]) -> Counter[str]:
    context_counts = model['context_counts'].get(_context_key(row))
    if context_counts:
        return context_counts
    return model['global_counts']


def _context_key(row: dict[str, Any]) -> str:
    return '|'.join(str(row.get(field) or '') for field in CONTEXT_FIELDS)


def _model_artifact(model: dict[str, Any]) -> dict[str, Any]:
    contexts: dict[str, dict[str, Any]] = {}
    for context_key, counts in sorted(model['context_counts'].items()):
        top_action, top_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        contexts[context_key] = {
            'record_count': sum(counts.values()),
            'top_action': top_action,
            'top_action_count': top_count,
            'unique_action_count': len(counts),
        }
    return {
        'schema_version': 'dnd-agents-action-frequency-model-v1',
        'kind': 'contextual_action_frequency',
        'context_fields': list(CONTEXT_FIELDS),
        'smoothing_alpha': model['smoothing_alpha'],
        'action_vocab_size': len(model['action_vocab']),
        'global_top_actions': [
            {'action': action, 'count': count}
            for action, count in model['global_counts'].most_common(20)
        ],
        'contexts': contexts,
    }


def _baseline_checks(
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
    return checks


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


def _coverage_summary(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return 'n/a'
    parts: list[str] = []
    for label in ('scenario_counts', 'runtime_mode_counts', 'source_counts', 'agent_counts'):
        counts = value.get(label)
        if isinstance(counts, dict) and counts:
            parts.append(f'{label}: {_compact_counts(counts)}')
    return '; '.join(parts) if parts else 'n/a'


def _compact_counts(counts: dict[str, Any]) -> str:
    return ', '.join(f'{key}={counts[key]}' for key in sorted(counts))


def _safe_token(value: str) -> str:
    token = ''.join(character if character.isalnum() or character in ('-', '_') else '-' for character in value.strip())
    return token.strip('-') or 'supervised-baseline'


def _format_int(value: Any) -> str:
    return str(value) if isinstance(value, int) else '0'


def _format_float(value: Any) -> str:
    return f'{float(value):.4f}' if isinstance(value, (int, float)) else 'n/a'


def _markdown_text(value: Any) -> str:
    text = '' if value is None else str(value)
    return text.replace('|', '\\|').replace('\n', ' ')
