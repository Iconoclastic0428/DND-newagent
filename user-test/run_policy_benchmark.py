from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
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
    scenario_id: str = 'lmop_first_combat',
    env_path: str | Path = '.env',
    base_url: str | None = None,
    max_combat_turns: int = 120,
    baseline_seed: int = 0,
    llm_player_specs: tuple[tuple[str, str | Path], ...] | None = None,
    llm_player_agent_factory: LLMPlayerAgentFactory | None = None,
    llm_player_max_actions_per_pump: int = 1,
) -> dict[str, Any]:
    if not policies:
        raise ValueError('At least one policy must be provided.')
    benchmark_dir = Path(output_dir) / f'{scenario_id}-benchmark-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    entries: list[tuple[str, dict[str, Any]]] = []
    batch_reports: list[dict[str, Any]] = []
    for raw_policy in policies:
        label, policy = _parse_policy_entry(raw_policy)
        policy_dir = benchmark_dir / 'batches' / _safe_label(label)
        report = run_batch(
            episodes=episodes,
            output_dir=policy_dir,
            scenario_id=scenario_id,
            env_path=env_path,
            base_url=base_url,
            max_combat_turns=max_combat_turns,
            policy=policy,
            llm_player_specs=llm_player_specs,
            llm_player_agent_factory=llm_player_agent_factory,
            llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
            baseline_seed=baseline_seed,
        )
        entries.append((label, report))
        batch_reports.append({
            'label': label,
            'policy': policy,
            'batch_id': report.get('batch_id'),
            'report_path': report.get('report_path'),
            'success_rate': report.get('success_rate'),
            'avg_reward': report.get('avg_reward'),
            'avg_invalid_actions': report.get('avg_invalid_actions'),
        })
    comparison = compare_policy_batches(entries)
    comparison_path = benchmark_dir / 'policy_comparison.json'
    write_policy_comparison_report(comparison, comparison_path)
    markdown_summary_path = benchmark_dir / 'benchmark_summary.md'
    write_policy_comparison_markdown(comparison, markdown_summary_path)
    benchmark_report = {
        'benchmark_id': benchmark_dir.name,
        'scenario_id': scenario_id,
        'episodes_per_policy': episodes,
        'baseline_seed': baseline_seed,
        'max_combat_turns': max_combat_turns,
        'output_dir': str(benchmark_dir),
        'comparison_path': str(comparison_path),
        'markdown_summary_path': str(markdown_summary_path),
        'batch_reports': batch_reports,
        'comparison': comparison,
    }
    benchmark_path = benchmark_dir / 'benchmark_report.json'
    benchmark_report['benchmark_path'] = str(benchmark_path)
    benchmark_path.write_text(json.dumps(benchmark_report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return benchmark_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run multiple policy batches and write a comparison report.')
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
    report = run_policy_benchmark(
        episodes=args.episodes,
        output_dir=args.output_dir,
        policies=tuple(args.policy) if args.policy else DEFAULT_POLICIES,
        scenario_id=args.scenario_id,
        env_path=args.env_path,
        base_url=args.base_url,
        max_combat_turns=args.max_combat_turns,
        baseline_seed=args.baseline_seed,
        llm_player_specs=parse_llm_player_specs(args.llm_player) if args.llm_player else None,
        llm_player_max_actions_per_pump=args.llm_player_max_actions_per_pump,
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


if __name__ == '__main__':
    raise SystemExit(main())
