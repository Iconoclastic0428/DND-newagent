from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

USER_TEST_ROOT = Path(__file__).resolve().parent
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from run_training_batch import LLMPlayerAgentFactory, parse_llm_player_specs, run_batch
from training.comparison import compare_policy_batches, write_policy_comparison_markdown, write_policy_comparison_report


DEFAULT_POLICIES = ('scripted', 'random-legal')


def run_policy_benchmark(
    *,
    episodes: int,
    output_dir: str | Path,
    policies: tuple[str, ...] = DEFAULT_POLICIES,
    policy_configs: tuple[dict[str, Any], ...] | None = None,
    scenario_id: str = 'lmop_first_combat',
    env_path: str | Path = '.env',
    base_url: str | None = None,
    max_combat_turns: int = 120,
    baseline_seed: int = 0,
    seeds: tuple[int, ...] | None = None,
    llm_player_specs: tuple[tuple[str, str | Path], ...] | None = None,
    llm_player_agent_factory: LLMPlayerAgentFactory | None = None,
    llm_player_max_actions_per_pump: int = 1,
    character_load_path: str | Path | None = None,
) -> dict[str, Any]:
    if policy_configs is None and not policies:
        raise ValueError('At least one policy must be provided.')
    resolved_policy_configs = (
        tuple(policy_configs)
        if policy_configs is not None
        else _policy_configs_from_entries(policies, llm_player_specs=llm_player_specs)
    )
    if not resolved_policy_configs:
        raise ValueError('At least one policy must be provided.')
    seed_values = tuple(seeds) if seeds is not None else (baseline_seed,)
    if not seed_values:
        raise ValueError('At least one benchmark seed must be provided.')
    benchmark_dir = Path(output_dir) / f'{scenario_id}-benchmark-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    entries: list[tuple[str, dict[str, Any]]] = []
    batch_reports: list[dict[str, Any]] = []
    seed_batch_reports: list[dict[str, Any]] = []
    for policy_config in resolved_policy_configs:
        label = str(policy_config['label'])
        policy = str(policy_config['policy'])
        policy_llm_player_specs = policy_config.get('llm_player_specs', llm_player_specs)
        policy_character_load_path = policy_config.get('character_load_path', character_load_path)
        seed_reports: list[dict[str, Any]] = []
        for seed in seed_values:
            policy_dir = benchmark_dir / 'batches' / _safe_label(label) / f'seed-{seed}'
            report = run_batch(
                episodes=episodes,
                output_dir=policy_dir,
                scenario_id=scenario_id,
                env_path=env_path,
                base_url=base_url,
                max_combat_turns=max_combat_turns,
                policy=policy,
                llm_player_specs=policy_llm_player_specs,
                llm_player_agent_factory=llm_player_agent_factory,
                llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
                baseline_seed=seed,
                character_load_path=policy_character_load_path,
            )
            seed_reports.append(report)
            seed_batch_reports.append({
                'label': label,
                'policy': policy,
                'seed': seed,
                'batch_id': report.get('batch_id'),
                'report_path': report.get('report_path'),
                'success_rate': report.get('success_rate'),
                'avg_reward': report.get('avg_reward'),
                'avg_invalid_actions': report.get('avg_invalid_actions'),
                'character_load_path': report.get('character_load_path'),
            })
        report = _aggregate_policy_seed_reports(
            label=label,
            policy=policy,
            scenario_id=scenario_id,
            seed_values=seed_values,
            seed_reports=seed_reports,
        )
        entries.append((label, report))
        batch_reports.append({
            'label': label,
            'policy': policy,
            'batch_id': report.get('batch_id'),
            'seed_count': len(seed_values),
            'seeds': list(seed_values),
            'report_paths': report.get('seed_report_paths'),
            'success_rate': report.get('success_rate'),
            'avg_reward': report.get('avg_reward'),
            'avg_reward_stddev': report.get('avg_reward_stddev'),
            'avg_invalid_actions': report.get('avg_invalid_actions'),
            'character_load_path': report.get('character_load_path'),
        })
    comparison = compare_policy_batches(entries)
    comparison['benchmark_metadata'] = {
        'episodes_per_seed': episodes,
        'seed_count': len(seed_values),
        'seeds': list(seed_values),
    }
    comparison_path = benchmark_dir / 'policy_comparison.json'
    write_policy_comparison_report(comparison, comparison_path)
    markdown_summary_path = benchmark_dir / 'benchmark_summary.md'
    write_policy_comparison_markdown(comparison, markdown_summary_path)
    benchmark_report = {
        'benchmark_id': benchmark_dir.name,
        'scenario_id': scenario_id,
        'episodes_per_seed': episodes,
        'episodes_per_policy': episodes * len(seed_values),
        'baseline_seed': baseline_seed,
        'seed_count': len(seed_values),
        'seeds': list(seed_values),
        'max_combat_turns': max_combat_turns,
        'output_dir': str(benchmark_dir),
        'comparison_path': str(comparison_path),
        'markdown_summary_path': str(markdown_summary_path),
        'batch_reports': batch_reports,
        'seed_batch_reports': seed_batch_reports,
        'comparison': comparison,
    }
    benchmark_path = benchmark_dir / 'benchmark_report.json'
    benchmark_report['benchmark_path'] = str(benchmark_path)
    benchmark_path.write_text(json.dumps(benchmark_report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return benchmark_report


def run_policy_benchmark_from_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = _load_benchmark_manifest(path)
    manifest_dir = path.resolve().parent
    report = run_policy_benchmark(
        episodes=_manifest_int(manifest, 'episodes', default=1),
        output_dir=_manifest_path(manifest.get('output_dir', 'runs/benchmarks'), manifest_dir),
        policies=(),
        policy_configs=_manifest_policy_configs(manifest.get('policies', list(DEFAULT_POLICIES)), manifest_dir),
        scenario_id=str(manifest.get('scenario_id', 'lmop_first_combat')),
        env_path=_manifest_path(manifest.get('env_path', '.env'), manifest_dir),
        base_url=manifest.get('base_url'),
        max_combat_turns=_manifest_int(manifest, 'max_combat_turns', default=120),
        baseline_seed=_manifest_int(manifest, 'baseline_seed', default=0),
        seeds=_manifest_seeds(manifest),
        llm_player_specs=_manifest_llm_player_specs(manifest.get('llm_players'), manifest_dir),
        llm_player_max_actions_per_pump=_manifest_int(manifest, 'llm_player_max_actions_per_pump', default=1),
        character_load_path=_manifest_character_load_path(manifest, manifest_dir),
    )
    report['manifest_path'] = str(path)
    benchmark_path = Path(report['benchmark_path'])
    benchmark_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run multiple policy batches and write a comparison report.')
    parser.add_argument('--manifest', type=Path, help='Optional JSON benchmark manifest. When set, manifest values define the run.')
    parser.add_argument('--episodes', type=int, default=1, help='Number of episodes to run per policy.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/benchmarks'), help='Directory for benchmark output.')
    parser.add_argument(
        '--policy',
        action='append',
        default=[],
        metavar='[LABEL=]POLICY',
        help='Policy to benchmark. Repeat for multiple policies. Defaults to scripted and random-legal.',
    )
    parser.add_argument('--scenario-id', default='lmop_first_combat', help='Scenario to run. Currently supports lmop_first_combat.')
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='Environment file used by the demo runtime.')
    parser.add_argument('--base-url', default=None, help='Optional explicit 5etools mirror base URL.')
    parser.add_argument('--max-combat-turns', type=int, default=120, help='Maximum combat turns before an episode is marked failed.')
    parser.add_argument('--baseline-seed', type=int, default=0, help='Seed for deterministic baseline policies such as random-legal.')
    parser.add_argument('--seed', action='append', type=int, default=[], help='Benchmark seed to run. Repeat for multi-seed benchmarks. Overrides --baseline-seed when provided.')
    parser.add_argument('--load-characters', type=Path, help='Load confirmed character records from this JSON party file before running each episode.')
    parser.add_argument(
        '--llm-player',
        action='append',
        default=[],
        metavar='CONTROLLER_ID=ENV_PATH',
        help='Assign one player controller to an LLM env file. Used when benchmarking llm-party.',
    )
    parser.add_argument('--llm-player-max-actions-per-pump', type=int, default=1, help='Maximum LLM player actions to process per combat pump.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.manifest is not None:
        report = run_policy_benchmark_from_manifest(args.manifest)
    else:
        report = run_policy_benchmark(
            episodes=args.episodes,
            output_dir=args.output_dir,
            policies=tuple(args.policy) if args.policy else DEFAULT_POLICIES,
            scenario_id=args.scenario_id,
            env_path=args.env_path,
            base_url=args.base_url,
            max_combat_turns=args.max_combat_turns,
            baseline_seed=args.baseline_seed,
            seeds=tuple(args.seed) if args.seed else None,
            llm_player_specs=parse_llm_player_specs(args.llm_player) if args.llm_player else None,
            llm_player_max_actions_per_pump=args.llm_player_max_actions_per_pump,
            character_load_path=args.load_characters,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _parse_policy_entry(raw_entry: str) -> tuple[str, str]:
    if '=' not in raw_entry:
        policy = raw_entry.strip()
        return policy, policy
    label, policy = raw_entry.split('=', 1)
    label = label.strip()
    policy = policy.strip()
    if not label:
        raise ValueError(f'Policy label cannot be empty: {raw_entry!r}.')
    if not policy:
        raise ValueError(f'Policy cannot be empty: {raw_entry!r}.')
    return label, policy


def _safe_label(label: str) -> str:
    safe = ''.join(character if character.isalnum() or character in {'-', '_'} else '-' for character in label.strip().lower())
    return safe.strip('-') or 'policy'


def _policy_configs_from_entries(
    entries: tuple[str, ...],
    *,
    llm_player_specs: tuple[tuple[str, str | Path], ...] | None,
) -> tuple[dict[str, Any], ...]:
    configs: list[dict[str, Any]] = []
    for raw_policy in entries:
        label, policy = _parse_policy_entry(raw_policy)
        configs.append({
            'label': label,
            'policy': policy,
            'llm_player_specs': llm_player_specs,
        })
    return tuple(configs)


def _load_benchmark_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid benchmark manifest JSON at {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise ValueError(f'Benchmark manifest at {path} must be a JSON object.')
    return payload


def _manifest_policy_configs(value: Any, manifest_dir: Path) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError('Benchmark manifest must define a non-empty policies list.')
    configs: list[dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, str):
            label, policy = _parse_policy_entry(entry)
            configs.append({'label': label, 'policy': policy})
            continue
        if not isinstance(entry, dict):
            raise ValueError('Manifest policy entries must be strings or objects.')
        policy = str(entry.get('policy') or '').strip()
        if not policy:
            raise ValueError('Manifest policy object is missing policy.')
        label = str(entry.get('label') or policy).strip()
        if not label:
            raise ValueError('Manifest policy object has an empty label.')
        config = {
            'label': label,
            'policy': policy,
        }
        policy_llm_specs = _manifest_llm_player_specs(entry.get('llm_players'), manifest_dir)
        if policy_llm_specs is not None:
            config['llm_player_specs'] = policy_llm_specs
        policy_character_load_path = _manifest_character_load_path(entry, manifest_dir)
        if policy_character_load_path is not None:
            config['character_load_path'] = policy_character_load_path
        configs.append(config)
    return tuple(configs)


def _manifest_llm_player_specs(value: Any, manifest_dir: Path) -> tuple[tuple[str, Path], ...] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return tuple(
            (str(controller_id), _manifest_path(env_path, manifest_dir))
            for controller_id, env_path in value.items()
        )
    if isinstance(value, list):
        parsed = parse_llm_player_specs([str(item) for item in value])
        return tuple((controller_id, _manifest_path(env_path, manifest_dir)) for controller_id, env_path in parsed)
    raise ValueError('llm_players must be an object or list of CONTROLLER_ID=ENV_PATH strings.')


def _manifest_path(value: Any, manifest_dir: Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else manifest_dir / path


def _manifest_character_load_path(manifest: dict[str, Any], manifest_dir: Path) -> Path | None:
    if manifest.get('character_load_path') is not None:
        return _manifest_path(manifest['character_load_path'], manifest_dir)
    loadout_name = manifest.get('character_loadout')
    if loadout_name is None:
        return None
    loadouts = manifest.get('character_loadouts')
    if not isinstance(loadouts, dict):
        raise ValueError('character_loadout requires a character_loadouts object.')
    if loadout_name not in loadouts:
        raise ValueError(f'Unknown character_loadout {loadout_name!r}.')
    return _manifest_path(loadouts[loadout_name], manifest_dir)


def _manifest_int(manifest: dict[str, Any], key: str, *, default: int) -> int:
    value = manifest.get(key, default)
    if not isinstance(value, int):
        raise ValueError(f'Benchmark manifest field {key!r} must be an integer.')
    return value


def _manifest_seeds(manifest: dict[str, Any]) -> tuple[int, ...] | None:
    raw_seeds = manifest.get('seeds')
    if raw_seeds is None:
        return None
    if not isinstance(raw_seeds, list) or not raw_seeds:
        raise ValueError('Benchmark manifest field "seeds" must be a non-empty integer list.')
    if not all(isinstance(seed, int) for seed in raw_seeds):
        raise ValueError('Benchmark manifest field "seeds" must contain only integers.')
    return tuple(raw_seeds)


def _aggregate_policy_seed_reports(
    *,
    label: str,
    policy: str,
    scenario_id: str,
    seed_values: tuple[int, ...],
    seed_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    episodes = sum(_number(report.get('episodes')) for report in seed_reports)
    successes = sum(_number(report.get('successes')) for report in seed_reports)
    transition_count = sum(_number(report.get('transition_count')) for report in seed_reports)
    preference_pair_count = sum(_number(report.get('preference_pair_count')) for report in seed_reports)
    evaluation_reports = [
        report.get('policy_evaluation')
        for report in seed_reports
        if isinstance(report.get('policy_evaluation'), dict)
    ]
    avg_rewards = [_number(report.get('avg_reward')) for report in seed_reports]
    aggregate = {
        'batch_id': f'{label}-aggregate-{len(seed_reports)}-seeds',
        'scenario_id': scenario_id,
        'policy': policy,
        'label': label,
        'seed_count': len(seed_reports),
        'seeds': list(seed_values),
        'seed_report_paths': [str(report.get('report_path')) for report in seed_reports if report.get('report_path')],
        'character_load_path': _first_present(report.get('character_load_path') for report in seed_reports),
        'llm_player_controllers': _merged_list(report.get('llm_player_controllers') for report in seed_reports),
        'episodes': episodes,
        'successes': successes,
        'success_rate': successes / episodes if episodes else 0.0,
        'avg_reward': _weighted_report_average(seed_reports, 'avg_reward'),
        'avg_reward_stddev': _stddev(avg_rewards),
        'avg_invalid_actions': _weighted_report_average(seed_reports, 'avg_invalid_actions'),
        'avg_turns': _weighted_report_average(seed_reports, 'avg_turns'),
        'avg_party_hp_remaining': _weighted_report_average(seed_reports, 'avg_party_hp_remaining'),
        'transition_count': transition_count,
        'preference_pair_count': preference_pair_count,
        'policy_evaluation': _aggregate_policy_evaluations(evaluation_reports, episodes=episodes),
    }
    return aggregate


def _aggregate_policy_evaluations(evaluations: list[dict[str, Any]], *, episodes: float) -> dict[str, Any]:
    transition_count = sum(_number(evaluation.get('transition_count')) for evaluation in evaluations)
    invalid_transition_count = sum(_number(evaluation.get('invalid_transition_count')) for evaluation in evaluations)
    successes = sum(_number(evaluation.get('successes')) for evaluation in evaluations)
    total_reward = sum(_number(evaluation.get('total_reward')) for evaluation in evaluations)
    reward_by_channel = _sum_number_maps(evaluation.get('reward_by_channel') for evaluation in evaluations)
    return {
        'episode_count': episodes,
        'successes': successes,
        'success_rate': successes / episodes if episodes else 0.0,
        'transition_count': transition_count,
        'invalid_transition_count': invalid_transition_count,
        'invalid_transition_rate': invalid_transition_count / transition_count if transition_count else 0.0,
        'total_reward': total_reward,
        'avg_reward_per_transition': total_reward / transition_count if transition_count else 0.0,
        'total_action_reward': sum(_number(evaluation.get('total_action_reward')) for evaluation in evaluations),
        'total_terminal_reward': sum(_number(evaluation.get('total_terminal_reward')) for evaluation in evaluations),
        'reward_by_channel': reward_by_channel,
        'avg_reward_by_channel': {
            channel: value / transition_count
            for channel, value in reward_by_channel.items()
        } if transition_count else {},
        'action_count_by_source': _sum_number_maps(evaluation.get('action_count_by_source') for evaluation in evaluations),
        'action_count_by_runtime_mode': _sum_number_maps(evaluation.get('action_count_by_runtime_mode') for evaluation in evaluations),
    }


def _weighted_report_average(reports: list[dict[str, Any]], key: str) -> float:
    total_weight = sum(_number(report.get('episodes')) for report in reports)
    if total_weight <= 0:
        return 0.0
    return sum(_number(report.get(key)) * _number(report.get('episodes')) for report in reports) / total_weight


def _sum_number_maps(values: Any) -> dict[str, float]:
    totals: dict[str, float] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if isinstance(item, (int, float)):
                totals[str(key)] = totals.get(str(key), 0.0) + float(item)
    return totals


def _merged_list(values: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            text = str(item)
            if text not in seen:
                seen.add(text)
                merged.append(text)
    return merged


def _stddev(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    average = sum(values) / len(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))


def _first_present(values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


if __name__ == '__main__':
    raise SystemExit(main())
