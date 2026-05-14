from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import subprocess
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
    character_loadout_scenarios: tuple[dict[str, Any], ...] | None = None,
    manifest_path: str | Path | None = None,
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
    loadout_scenarios = _resolve_character_loadout_scenarios(
        character_load_path=character_load_path,
        character_loadout_scenarios=character_loadout_scenarios,
    )
    output_root = Path(output_dir)
    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    benchmark_dir = output_root / f'{scenario_id}-benchmark-{created_at.replace("-", "").replace(":", "")}-{uuid4().hex[:8]}'
    entries: list[tuple[str, dict[str, Any]]] = []
    batch_reports: list[dict[str, Any]] = []
    seed_batch_reports: list[dict[str, Any]] = []
    for policy_config in resolved_policy_configs:
        label = str(policy_config['label'])
        policy = str(policy_config['policy'])
        policy_llm_player_specs = policy_config.get('llm_player_specs', llm_player_specs)
        policy_loadout_scenarios = _resolve_character_loadout_scenarios(
            character_load_path=policy_config.get('character_load_path'),
            character_loadout_scenarios=policy_config.get('character_loadout_scenarios'),
            fallback_scenarios=loadout_scenarios,
        )
        seed_reports: list[dict[str, Any]] = []
        for loadout_scenario in policy_loadout_scenarios:
            loadout_label = str(loadout_scenario['label'])
            loadout_path = loadout_scenario.get('character_load_path')
            for seed in seed_values:
                policy_dir = benchmark_dir / 'batches' / _safe_label(label) / _safe_label(loadout_label) / f'seed-{seed}'
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
                    character_load_path=loadout_path,
                )
                report['character_loadout_label'] = loadout_label
                report['character_load_path'] = str(loadout_path) if loadout_path is not None else report.get('character_load_path')
                seed_reports.append(report)
                seed_batch_reports.append({
                    'label': label,
                    'policy': policy,
                    'character_loadout_label': loadout_label,
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
            loadout_scenarios=policy_loadout_scenarios,
        )
        entries.append((label, report))
        batch_reports.append({
            'label': label,
            'policy': policy,
            'batch_id': report.get('batch_id'),
            'seed_count': len(seed_values),
            'loadout_count': len(policy_loadout_scenarios),
            'seeds': list(seed_values),
            'character_loadouts': report.get('character_loadouts'),
            'character_loadout_labels': report.get('character_loadout_labels'),
            'report_paths': report.get('seed_report_paths'),
            'success_rate': report.get('success_rate'),
            'avg_reward': report.get('avg_reward'),
            'avg_reward_stddev': report.get('avg_reward_stddev'),
            'avg_invalid_actions': report.get('avg_invalid_actions'),
            'character_load_path': report.get('character_load_path'),
            'character_load_paths': report.get('character_load_paths'),
        })
    comparison = compare_policy_batches(entries)
    comparison['benchmark_metadata'] = {
        'episodes_per_seed': episodes,
        'seed_count': len(seed_values),
        'seeds': list(seed_values),
        'loadout_count': len(loadout_scenarios),
        'character_loadouts': _serialize_loadout_scenarios(loadout_scenarios),
    }
    comparison_path = benchmark_dir / 'policy_comparison.json'
    write_policy_comparison_report(comparison, comparison_path)
    markdown_summary_path = benchmark_dir / 'benchmark_summary.md'
    write_policy_comparison_markdown(comparison, markdown_summary_path)
    benchmark_report = {
        'benchmark_id': benchmark_dir.name,
        'created_at': created_at,
        'git_commit': _current_git_commit(),
        'scenario_id': scenario_id,
        'manifest_path': str(manifest_path) if manifest_path is not None else None,
        'episodes_per_seed': episodes,
        'episodes_per_policy': episodes * len(seed_values) * len(loadout_scenarios),
        'baseline_seed': baseline_seed,
        'seed_count': len(seed_values),
        'seeds': list(seed_values),
        'character_loadout_count': len(loadout_scenarios),
        'character_loadouts': _serialize_loadout_scenarios(loadout_scenarios),
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
    history_paths = _append_benchmark_history(benchmark_report, output_root)
    benchmark_report.update(history_paths)
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
        policy_configs=_manifest_policy_configs(manifest.get('policies', list(DEFAULT_POLICIES)), manifest_dir, root_manifest=manifest),
        scenario_id=str(manifest.get('scenario_id', 'lmop_first_combat')),
        env_path=_manifest_path(manifest.get('env_path', '.env'), manifest_dir),
        base_url=manifest.get('base_url'),
        max_combat_turns=_manifest_int(manifest, 'max_combat_turns', default=120),
        baseline_seed=_manifest_int(manifest, 'baseline_seed', default=0),
        seeds=_manifest_seeds(manifest),
        llm_player_specs=_manifest_llm_player_specs(manifest.get('llm_players'), manifest_dir),
        llm_player_max_actions_per_pump=_manifest_int(manifest, 'llm_player_max_actions_per_pump', default=1),
        character_load_path=_manifest_character_load_path(manifest, manifest_dir),
        character_loadout_scenarios=_manifest_character_loadout_scenarios(manifest, manifest_dir),
        manifest_path=path,
    )
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
    parser.add_argument('--scenario-id', default='lmop_first_combat', help='Scenario to run. Supports lmop_first_combat and lmop_story_opening_choices.')
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


def _manifest_policy_configs(value: Any, manifest_dir: Path, *, root_manifest: dict[str, Any] | None = None) -> tuple[dict[str, Any], ...]:
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
        policy_character_load_path = _manifest_character_load_path(entry, manifest_dir, lookup_manifest=root_manifest)
        if policy_character_load_path is not None:
            config['character_load_path'] = policy_character_load_path
        policy_loadout_scenarios = _manifest_character_loadout_scenarios(entry, manifest_dir, lookup_manifest=root_manifest)
        if policy_loadout_scenarios is not None:
            config['character_loadout_scenarios'] = policy_loadout_scenarios
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


def _manifest_character_load_path(
    manifest: dict[str, Any],
    manifest_dir: Path,
    *,
    lookup_manifest: dict[str, Any] | None = None,
) -> Path | None:
    if manifest.get('character_load_path') is not None:
        return _manifest_path(manifest['character_load_path'], manifest_dir)
    loadout_name = manifest.get('character_loadout')
    if loadout_name is None:
        return None
    loadout_source = manifest if isinstance(manifest.get('character_loadouts'), dict) else lookup_manifest or manifest
    loadouts = loadout_source.get('character_loadouts')
    if not isinstance(loadouts, dict):
        raise ValueError('character_loadout requires a character_loadouts object.')
    if loadout_name not in loadouts:
        raise ValueError(f'Unknown character_loadout {loadout_name!r}.')
    return _manifest_path(loadouts[loadout_name], manifest_dir)


def _manifest_character_loadout_scenarios(
    manifest: dict[str, Any],
    manifest_dir: Path,
    *,
    lookup_manifest: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...] | None:
    raw_scenarios = manifest.get('character_loadout_scenarios')
    if raw_scenarios is None:
        return None
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError('character_loadout_scenarios must be a non-empty list.')
    scenarios: list[dict[str, Any]] = []
    named_loadout_source = manifest if isinstance(manifest.get('character_loadouts'), dict) else lookup_manifest or manifest
    for index, entry in enumerate(raw_scenarios, start=1):
        if isinstance(entry, str):
            scenarios.append(_manifest_named_character_loadout(entry, named_loadout_source, manifest_dir))
            continue
        if not isinstance(entry, dict):
            raise ValueError('character_loadout_scenarios entries must be strings or objects.')
        label = str(entry.get('label') or entry.get('character_loadout') or f'loadout-{index}').strip()
        if not label:
            raise ValueError('character_loadout_scenarios entry has an empty label.')
        if entry.get('character_load_path') is not None:
            character_load_path = _manifest_path(entry['character_load_path'], manifest_dir)
        elif entry.get('character_loadout') is not None:
            character_load_path = _manifest_named_character_loadout(str(entry['character_loadout']), named_loadout_source, manifest_dir)['character_load_path']
        else:
            character_load_path = None
        scenarios.append({
            'label': label,
            'character_load_path': character_load_path,
        })
    return tuple(scenarios)


def _manifest_named_character_loadout(name: str, manifest: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    loadouts = manifest.get('character_loadouts')
    if not isinstance(loadouts, dict):
        raise ValueError('Named character loadout scenarios require a character_loadouts object.')
    if name not in loadouts:
        raise ValueError(f'Unknown character loadout scenario {name!r}.')
    return {
        'label': name,
        'character_load_path': _manifest_path(loadouts[name], manifest_dir),
    }


def _resolve_character_loadout_scenarios(
    *,
    character_load_path: str | Path | None = None,
    character_loadout_scenarios: tuple[dict[str, Any], ...] | None = None,
    fallback_scenarios: tuple[dict[str, Any], ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    if character_loadout_scenarios is not None:
        if not character_loadout_scenarios:
            raise ValueError('At least one character loadout scenario must be provided.')
        return tuple(_normalize_loadout_scenario(scenario, index) for index, scenario in enumerate(character_loadout_scenarios, start=1))
    if character_load_path is not None:
        return ({
            'label': Path(character_load_path).stem or 'loaded-party',
            'character_load_path': character_load_path,
        },)
    if fallback_scenarios is not None:
        return fallback_scenarios
    return ({'label': 'default', 'character_load_path': None},)


def _normalize_loadout_scenario(scenario: dict[str, Any], index: int) -> dict[str, Any]:
    label = str(scenario.get('label') or f'loadout-{index}').strip()
    if not label:
        raise ValueError('Character loadout scenario label cannot be empty.')
    return {
        'label': label,
        'character_load_path': scenario.get('character_load_path'),
    }


def _serialize_loadout_scenarios(scenarios: tuple[dict[str, Any], ...]) -> list[dict[str, str | None]]:
    return [
        {
            'label': str(scenario['label']),
            'character_load_path': str(scenario['character_load_path']) if scenario.get('character_load_path') is not None else None,
        }
        for scenario in scenarios
    ]


def _append_benchmark_history(benchmark_report: dict[str, Any], output_root: Path) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    history_entry = _benchmark_history_entry(benchmark_report)
    history_jsonl_path = output_root / 'benchmark_history.jsonl'
    with history_jsonl_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(history_entry, ensure_ascii=False, sort_keys=True) + '\n')
    history_markdown_path = output_root / 'benchmark_history.md'
    _write_benchmark_history_markdown(history_jsonl_path, history_markdown_path)
    return {
        'benchmark_history_path': str(history_jsonl_path),
        'benchmark_history_markdown_path': str(history_markdown_path),
    }


def _benchmark_history_entry(benchmark_report: dict[str, Any]) -> dict[str, Any]:
    comparison = benchmark_report.get('comparison') if isinstance(benchmark_report.get('comparison'), dict) else {}
    leaderboard = comparison.get('leaderboard') if isinstance(comparison.get('leaderboard'), list) else []
    return {
        'benchmark_id': benchmark_report.get('benchmark_id'),
        'created_at': benchmark_report.get('created_at'),
        'git_commit': benchmark_report.get('git_commit'),
        'scenario_id': benchmark_report.get('scenario_id'),
        'manifest_path': benchmark_report.get('manifest_path'),
        'benchmark_path': benchmark_report.get('benchmark_path'),
        'comparison_path': benchmark_report.get('comparison_path'),
        'markdown_summary_path': benchmark_report.get('markdown_summary_path'),
        'episodes_per_seed': benchmark_report.get('episodes_per_seed'),
        'episodes_per_policy': benchmark_report.get('episodes_per_policy'),
        'seed_count': benchmark_report.get('seed_count'),
        'seeds': benchmark_report.get('seeds'),
        'character_loadout_count': benchmark_report.get('character_loadout_count'),
        'character_loadouts': benchmark_report.get('character_loadouts'),
        'max_combat_turns': benchmark_report.get('max_combat_turns'),
        'winner_label': (comparison.get('diagnostics') or {}).get('winner_label') if isinstance(comparison.get('diagnostics'), dict) else None,
        'policies': [
            _benchmark_history_policy_row(row)
            for row in leaderboard
            if isinstance(row, dict)
        ],
    }


def _benchmark_history_policy_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'rank': row.get('rank'),
        'label': row.get('label'),
        'policy': row.get('policy'),
        'llm_player_controllers': row.get('llm_player_controllers') or [],
        'episodes': row.get('episodes'),
        'success_rate': row.get('success_rate'),
        'avg_reward': row.get('avg_reward'),
        'avg_reward_stddev': row.get('avg_reward_stddev'),
        'avg_invalid_actions': row.get('avg_invalid_actions'),
        'avg_turns': row.get('avg_turns'),
        'avg_party_hp_remaining': row.get('avg_party_hp_remaining'),
        'comparison_score': row.get('comparison_score'),
        'reward_by_channel': row.get('reward_by_channel') or {},
    }


def _write_benchmark_history_markdown(history_jsonl_path: Path, output_path: Path) -> None:
    entries = _load_benchmark_history_entries(history_jsonl_path)
    lines = [
        '# Benchmark History',
        '',
        '| Created | Benchmark | Commit | Scenario | Seeds | Loadouts | Winner | Top Score | Report |',
        '| --- | --- | --- | --- | ---: | ---: | --- | ---: | --- |',
    ]
    for entry in reversed(entries):
        top_policy = _top_history_policy(entry)
        lines.append(
            '| '
            + ' | '.join([
                _markdown_cell(entry.get('created_at')),
                _markdown_cell(entry.get('benchmark_id')),
                _markdown_cell(_short_commit(entry.get('git_commit'))),
                _markdown_cell(entry.get('scenario_id')),
                _format_history_number(entry.get('seed_count'), digits=0),
                _format_history_number(entry.get('character_loadout_count'), digits=0),
                _markdown_cell(entry.get('winner_label')),
                _format_history_number(top_policy.get('comparison_score')),
                _markdown_link('report', entry.get('benchmark_path')),
            ])
            + ' |'
        )
    lines.extend(['', '## Latest Policy Rows', ''])
    if not entries:
        lines.append('No benchmark runs have been recorded yet.')
    else:
        latest = entries[-1]
        lines.extend([
            f'Latest benchmark: {_markdown_cell(latest.get("benchmark_id"))}',
            '',
            '| Rank | Policy | Success | Avg Reward | Invalid Actions | Avg Turns | Party HP | Score |',
            '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |',
        ])
        for policy in latest.get('policies', []):
            if not isinstance(policy, dict):
                continue
            lines.append(
                '| '
                + ' | '.join([
                    _format_history_number(policy.get('rank'), digits=0),
                    _markdown_cell(policy.get('label')),
                    _format_history_percent(policy.get('success_rate')),
                    _format_history_number(policy.get('avg_reward')),
                    _format_history_number(policy.get('avg_invalid_actions')),
                    _format_history_number(policy.get('avg_turns')),
                    _format_history_percent(policy.get('avg_party_hp_remaining')),
                    _format_history_number(policy.get('comparison_score')),
                ])
                + ' |'
            )
    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _load_benchmark_history_entries(history_jsonl_path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not history_jsonl_path.exists():
        return entries
    for line in history_jsonl_path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _top_history_policy(entry: dict[str, Any]) -> dict[str, Any]:
    policies = entry.get('policies') if isinstance(entry.get('policies'), list) else []
    for policy in policies:
        if isinstance(policy, dict) and policy.get('rank') == 1:
            return policy
    for policy in policies:
        if isinstance(policy, dict):
            return policy
    return {}


def _current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short=12', 'HEAD'],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _short_commit(value: Any) -> str:
    text = str(value) if value is not None else ''
    return text[:12]


def _markdown_link(label: str, value: Any) -> str:
    if value is None:
        return ''
    target = str(value).replace(')', '%29')
    return f'[{_markdown_cell(label)}]({target})'


def _markdown_cell(value: Any) -> str:
    text = str(value) if value is not None else ''
    return text.replace('|', '\\|').replace('\n', ' ')


def _format_history_number(value: Any, *, digits: int = 3) -> str:
    if not isinstance(value, (int, float)):
        return '0'
    if digits <= 0:
        return str(int(value))
    return f'{float(value):.{digits}f}'


def _format_history_percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return '0.0%'
    return f'{float(value) * 100.0:.1f}%'


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
    loadout_scenarios: tuple[dict[str, Any], ...],
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
        'batch_id': f'{label}-aggregate-{len(seed_reports)}-runs',
        'scenario_id': scenario_id,
        'policy': policy,
        'label': label,
        'seed_count': len(seed_values),
        'seeds': list(seed_values),
        'run_count': len(seed_reports),
        'loadout_count': len(loadout_scenarios),
        'character_loadouts': _serialize_loadout_scenarios(loadout_scenarios),
        'seed_report_paths': [str(report.get('report_path')) for report in seed_reports if report.get('report_path')],
        'character_loadout_labels': _merged_list(report.get('character_loadout_label') for report in seed_reports),
        'character_load_path': _first_present(report.get('character_load_path') for report in seed_reports),
        'character_load_paths': _merged_list(report.get('character_load_path') for report in seed_reports),
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
        if value is None:
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
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
