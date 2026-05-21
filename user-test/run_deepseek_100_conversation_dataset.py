from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_quality import validate_preference_dataset, validate_transition_dataset, write_dataset_quality_report
from training.preferences import build_preference_pairs, write_preference_pairs_jsonl
from training.trajectory_summary import summarize_trajectory
from training.transitions import build_training_transitions, write_training_transitions_jsonl


PLAYER_CONTROLLER_IDS = (
    'player-1-controller',
    'player-2-controller',
    'player-3-controller',
    'player-4-controller',
)
SCENARIO_ID = 'lmop_full_story_demo'


class DeepSeekDatasetRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class EpisodeSpec:
    index: int
    episode_id: str
    label: str
    behavior_profile: str
    negative_intensity: float
    http_port: int
    ws_port: int
    phase: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate a 100-conversation DeepSeek DM/player RL dataset.')
    parser.add_argument('--output-root', type=Path, default=Path('runs/deepseek-100-conversation-dataset'))
    parser.add_argument('--run-id', help='Optional run id. Defaults to deepseek-100-<utc timestamp>-<suffix>.')
    parser.add_argument('--episodes', type=int, default=100)
    parser.add_argument('--positive-count', type=int, default=50)
    parser.add_argument('--pilot-size', type=int, default=10)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--http-port-base', type=int, default=8100)
    parser.add_argument('--ws-port-base', type=int, default=9100)
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='DeepSeek env file for the DM runtime.')
    parser.add_argument('--player-env-path', type=Path, help='DeepSeek env file for player agents. Defaults to --env-path.')
    parser.add_argument('--character-load-path', type=Path, help='Optional prebuilt four-character party JSON file.')
    parser.add_argument('--campaign-root', type=Path, help='Optional campaign markdown root override.')
    parser.add_argument('--mirror-root', type=Path, default=Path('5etools-mirror-2.github.io'))
    parser.add_argument('--base-url', help='Optional 5etools base URL. Defaults to file:///<mirror-root>/ when present.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--max-actions', type=int, default=90)
    parser.add_argument('--poll-interval-seconds', type=float, default=0.5)
    parser.add_argument('--monster-turn-delay-seconds', type=float, default=0.1)
    parser.add_argument('--request-timeout-seconds', type=float, default=0.0)
    parser.add_argument('--server-start-timeout-seconds', type=float, default=90.0)
    parser.add_argument('--pre-connector-delay-seconds', type=float, default=0.5)
    parser.add_argument('--connector-timeout-seconds', type=float, default=5400.0)
    parser.add_argument('--negative-intensity', type=float, default=0.5)
    parser.add_argument('--min-transitions', type=int, default=1)
    parser.add_argument('--dry-run', action='store_true', help='Write plan/report without launching servers or model calls.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_dataset(args)
    except DeepSeekDatasetRunnerError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_dataset(args: argparse.Namespace, *, episode_runner=None) -> dict[str, Any]:
    _validate_basic_args(args)
    run_id = args.run_id or f'deepseek-100-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = _resolve_output_root(args.output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    plan = build_episode_plan(
        episodes=args.episodes,
        positive_count=args.positive_count,
        pilot_size=args.pilot_size,
        http_port_base=args.http_port_base,
        ws_port_base=args.ws_port_base,
        negative_intensity=args.negative_intensity,
    )
    plan_path = run_dir / 'episode_plan.json'
    _write_json(plan_path, {'run_id': run_id, 'episodes': [asdict(spec) for spec in plan]})

    if args.dry_run:
        quality = build_dataset_quality_report([], expected_episodes=args.episodes, expected_positive_count=args.positive_count)
        report = {
            'status': 'dry_run',
            'run_id': run_id,
            'run_dir': str(run_dir),
            'episode_count': len(plan),
            'label_counts': _label_counts(asdict(spec) for spec in plan),
            'plan_path': str(plan_path),
            'quality_report': quality,
        }
        report_path = run_dir / 'dataset_run_report.json'
        report['report_path'] = str(report_path)
        _write_json(report_path, report)
        return report

    dm_env_path = _resolve_existing(args.env_path, label='DM env file')
    player_env_path = _resolve_existing(args.player_env_path or args.env_path, label='player env file')
    character_load_path = _resolve_optional(args.character_load_path, label='character party file')
    base_url = _resolve_base_url(args.base_url, args.mirror_root)
    episode_runner = episode_runner or run_episode

    pilot_plan = plan[:args.pilot_size]
    remaining_plan = plan[args.pilot_size:]
    results: list[dict[str, Any]] = []
    if pilot_plan:
        results.extend(
            _run_episode_specs(
                pilot_plan,
                args=args,
                run_dir=run_dir,
                dm_env_path=dm_env_path,
                player_env_path=player_env_path,
                character_load_path=character_load_path,
                base_url=base_url,
                episode_runner=episode_runner,
            )
        )
    control_decision = evaluate_pilot_control(results, current_negative_intensity=args.negative_intensity)
    control_path = run_dir / 'pilot_control_decision.json'
    _write_json(control_path, control_decision)
    adjusted_remaining = tuple(
        replace(spec, negative_intensity=control_decision['negative_intensity'])
        if spec.label == 'negative'
        else spec
        for spec in remaining_plan
    )
    if adjusted_remaining:
        results.extend(
            _run_episode_specs(
                adjusted_remaining,
                args=args,
                run_dir=run_dir,
                dm_env_path=dm_env_path,
                player_env_path=player_env_path,
                character_load_path=character_load_path,
                base_url=base_url,
                episode_runner=episode_runner,
            )
        )

    conversations_path = run_dir / 'conversations.jsonl'
    _write_jsonl(conversations_path, sorted(results, key=lambda item: int(item.get('index', 0))))
    combined = _write_combined_datasets(run_dir, results)
    quality = build_dataset_quality_report(results, expected_episodes=args.episodes, expected_positive_count=args.positive_count)
    quality['transition_dataset_quality'] = combined.get('transition_quality')
    quality['preference_dataset_quality'] = combined.get('preference_quality')
    _add_combined_dataset_quality_issues(quality, combined)
    quality_path = run_dir / 'dataset_quality_report.json'
    _write_json(quality_path, quality)
    report = {
        'status': 'completed' if quality['status'] in {'pass', 'warn'} else 'failed',
        'run_id': run_id,
        'run_dir': str(run_dir),
        'episode_count': len(results),
        'label_counts': quality['label_counts'],
        'completed_count': quality['completed_count'],
        'control_decision_path': str(control_path),
        'plan_path': str(plan_path),
        'conversations_path': str(conversations_path),
        'combined_transition_path': combined.get('transition_path'),
        'combined_preference_path': combined.get('preference_path'),
        'quality_report_path': str(quality_path),
        'quality_status': quality['status'],
        'reward_summary': quality['reward_summary'],
    }
    report_path = run_dir / 'dataset_run_report.json'
    report['report_path'] = str(report_path)
    _write_json(report_path, report)
    return report


def build_episode_plan(
    *,
    episodes: int,
    positive_count: int,
    pilot_size: int,
    http_port_base: int,
    ws_port_base: int,
    negative_intensity: float,
) -> tuple[EpisodeSpec, ...]:
    if episodes <= 0:
        raise DeepSeekDatasetRunnerError('--episodes must be > 0.')
    if positive_count < 0 or positive_count > episodes:
        raise DeepSeekDatasetRunnerError('--positive-count must be between 0 and --episodes.')
    if pilot_size < 0 or pilot_size > episodes:
        raise DeepSeekDatasetRunnerError('--pilot-size must be between 0 and --episodes.')
    if negative_intensity < 0 or negative_intensity > 1:
        raise DeepSeekDatasetRunnerError('--negative-intensity must be between 0 and 1.')
    negative_count = episodes - positive_count
    pilot_positive = min(positive_count, pilot_size // 2 + pilot_size % 2)
    pilot_negative = min(negative_count, pilot_size - pilot_positive)
    if pilot_positive + pilot_negative < pilot_size:
        missing = pilot_size - pilot_positive - pilot_negative
        if positive_count - pilot_positive >= missing:
            pilot_positive += missing
        else:
            pilot_negative += missing
    labels: list[str] = _interleaved_labels(pilot_positive, pilot_negative)
    labels.extend(_interleaved_labels(positive_count - pilot_positive, negative_count - pilot_negative))
    specs = []
    for index, label in enumerate(labels, start=1):
        specs.append(
            EpisodeSpec(
                index=index,
                episode_id=f'conversation-{index:03d}-{label}',
                label=label,
                behavior_profile=label,
                negative_intensity=(negative_intensity if label == 'negative' else 0.0),
                http_port=http_port_base + (index - 1) * 2,
                ws_port=ws_port_base + (index - 1) * 2,
                phase='pilot' if index <= pilot_size else 'main',
            )
        )
    return tuple(specs)


def evaluate_pilot_control(
    pilot_results: Iterable[dict[str, Any]],
    *,
    current_negative_intensity: float,
) -> dict[str, Any]:
    rows = list(pilot_results)
    positives = [row for row in rows if row.get('label') == 'positive']
    negatives = [row for row in rows if row.get('label') == 'negative']
    positive_avg = _average(row.get('total_reward') for row in positives)
    negative_avg = _average(row.get('total_reward') for row in negatives)
    negative_failure_rate = _failure_rate(negatives)
    negative_penalty_avg = _average(_reward_channel(row, 'penalty') for row in negatives)
    next_intensity = current_negative_intensity
    action = 'keep_negative_intensity'
    reason = 'Pilot rewards have the expected positive/negative separation.'
    if positives and negatives and negative_avg >= positive_avg - 0.05:
        next_intensity = min(1.0, current_negative_intensity + 0.2)
        action = 'increase_negative_intensity'
        reason = 'Pilot negative rewards are not lower than positive rewards; increase stalling/repetition pressure while keeping actions legal.'
    elif negatives and negative_failure_rate > 0.5:
        next_intensity = max(0.1, current_negative_intensity - 0.2)
        action = 'decrease_negative_intensity'
        reason = 'More than half of negative pilot conversations failed, so reduce intensity to preserve processable trajectories.'
    elif negatives and negative_penalty_avg > -0.05:
        next_intensity = min(1.0, current_negative_intensity + 0.1)
        action = 'increase_negative_intensity'
        reason = 'Negative pilot conversations did not accumulate enough penalty-channel reward.'
    return {
        'action': action,
        'reason': reason,
        'input_episode_count': len(rows),
        'positive_avg_reward': positive_avg,
        'negative_avg_reward': negative_avg,
        'negative_failure_rate': negative_failure_rate,
        'negative_penalty_avg': negative_penalty_avg,
        'previous_negative_intensity': current_negative_intensity,
        'negative_intensity': next_intensity,
    }


def build_dataset_quality_report(
    results: Iterable[dict[str, Any]],
    *,
    expected_episodes: int,
    expected_positive_count: int,
) -> dict[str, Any]:
    rows = list(results)
    expected_negative_count = expected_episodes - expected_positive_count
    label_counts = _label_counts(rows)
    issues: list[dict[str, Any]] = []
    if len(rows) != expected_episodes:
        issues.append(_issue('fail', 'episode_count_mismatch', f'Expected {expected_episodes} conversations, found {len(rows)}.'))
    if label_counts.get('positive', 0) != expected_positive_count or label_counts.get('negative', 0) != expected_negative_count:
        issues.append(
            _issue(
                'fail',
                'label_split_mismatch',
                f'Expected positive/negative split {expected_positive_count}/{expected_negative_count}, found {label_counts}.',
            )
        )
    missing_artifact_count = 0
    for row in rows:
        terminal_reason = row.get('terminal_reason')
        if not isinstance(terminal_reason, str) or not terminal_reason:
            issues.append(_issue('fail', 'missing_terminal_reason', f'{row.get("episode_id")} has no terminal reason.'))
        artifacts = row.get('artifact_paths') if isinstance(row.get('artifact_paths'), dict) else {}
        for key in ('transcript', 'trajectory', 'raw_interactions'):
            path = artifacts.get(key)
            if not isinstance(path, str) or not Path(path).exists():
                missing_artifact_count += 1
                issues.append(_issue('fail', 'missing_artifact', f'{row.get("episode_id")} missing artifact {key}.'))
        if row.get('status') != 'completed':
            trajectory_path = artifacts.get('trajectory')
            if isinstance(trajectory_path, str) and Path(trajectory_path).exists():
                issues.append(_issue('warn', 'failed_episode_with_trajectory', f'{row.get("episode_id")} failed after writing trajectory data.'))
            else:
                issues.append(_issue('fail', 'failed_episode_without_trajectory', f'{row.get("episode_id")} failed before writing processable trajectory data.'))
    completed_count = sum(1 for row in rows if row.get('status') == 'completed')
    reward_values = [float(row.get('total_reward')) for row in rows if isinstance(row.get('total_reward'), (int, float))]
    reward_channel_totals = _reward_channel_totals(rows)
    fail_count = sum(1 for issue in issues if issue['severity'] == 'fail')
    warn_count = sum(1 for issue in issues if issue['severity'] == 'warn')
    return {
        'status': 'fail' if fail_count else 'warn' if warn_count else 'pass',
        'expected_episodes': expected_episodes,
        'recorded_episodes': len(rows),
        'expected_positive_count': expected_positive_count,
        'expected_negative_count': expected_negative_count,
        'label_counts': label_counts,
        'completed_count': completed_count,
        'failed_count': len(rows) - completed_count,
        'missing_artifact_count': missing_artifact_count,
        'reward_summary': {
            'avg_total_reward': _average(reward_values),
            'min_total_reward': min(reward_values) if reward_values else 0.0,
            'max_total_reward': max(reward_values) if reward_values else 0.0,
        },
        'reward_channel_totals': reward_channel_totals,
        'issues': issues,
        'fail_count': fail_count,
        'warn_count': warn_count,
    }


def _add_combined_dataset_quality_issues(report: dict[str, Any], combined: dict[str, Any]) -> None:
    for key, code in (
        ('transition_quality', 'combined_transition_dataset_quality'),
        ('preference_quality', 'combined_preference_dataset_quality'),
    ):
        quality = combined.get(key)
        if not isinstance(quality, dict):
            continue
        status = quality.get('status')
        if status == 'pass':
            continue
        severity = 'fail' if status == 'fail' else 'warn'
        report['issues'].append(_issue(severity, code, f'{code} status is {status}.'))
    _refresh_quality_counts(report)


def _refresh_quality_counts(report: dict[str, Any]) -> None:
    issues = report.get('issues')
    if not isinstance(issues, list):
        return
    fail_count = sum(1 for issue in issues if isinstance(issue, dict) and issue.get('severity') == 'fail')
    warn_count = sum(1 for issue in issues if isinstance(issue, dict) and issue.get('severity') == 'warn')
    report['fail_count'] = fail_count
    report['warn_count'] = warn_count
    report['status'] = 'fail' if fail_count else 'warn' if warn_count else 'pass'


def run_episode(
    spec: EpisodeSpec,
    *,
    args: argparse.Namespace,
    run_dir: Path,
    dm_env_path: Path,
    player_env_path: Path,
    character_load_path: Path | None,
    base_url: str | None,
) -> dict[str, Any]:
    episode_dir = run_dir / 'episodes' / spec.episode_id
    paths = _episode_paths(episode_dir)
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    server_command = _server_command(args, spec, paths, dm_env_path, character_load_path, base_url)
    connector_command = _connector_command(args, spec, paths, player_env_path)
    result: dict[str, Any] = {
        **asdict(spec),
        'status': 'failed',
        'terminal_reason': None,
        'artifact_paths': {
            'transcript': str(paths['transcript']),
            'raw_interactions': str(paths['raw_interactions']),
            'campaign_root': str(paths['campaign_root']),
        },
        'server_command': _printable_command(server_command),
        'connector_command': _printable_command(connector_command),
    }
    server_process: subprocess.Popen[bytes] | None = None
    try:
        server_process = _start_logged_process(
            server_command,
            cwd=REPO_ROOT,
            stdout_path=paths['logs'] / 'web-server.stdout.log',
            stderr_path=paths['logs'] / 'web-server.stderr.log',
        )
        _wait_for_server(
            url=f'http://{args.host}:{spec.http_port}/automation/state?controller_id=dm',
            process=server_process,
            timeout_seconds=args.server_start_timeout_seconds,
            stderr_path=paths['logs'] / 'web-server.stderr.log',
        )
        if args.pre_connector_delay_seconds > 0:
            time.sleep(args.pre_connector_delay_seconds)
        connector_return_code = _run_logged_process(
            connector_command,
            cwd=REPO_ROOT,
            stdout_path=paths['logs'] / 'party-connector.stdout.log',
            stderr_path=paths['logs'] / 'party-connector.stderr.log',
            timeout_seconds=args.connector_timeout_seconds,
        )
        if connector_return_code != 0:
            raise DeepSeekDatasetRunnerError(f'party connector exited with code {connector_return_code}')
        trajectory_path = _latest_trajectory(paths['web_trajectories'])
        episode_dataset = _write_episode_datasets(spec, trajectory_path=trajectory_path, episode_dir=episode_dir)
        summary = summarize_trajectory(trajectory_path)
        result.update(
            {
                'status': 'completed',
                'terminal_reason': _terminal_reason(summary),
                'trajectory_summary': summary,
                'record_count': summary.get('record_count', 0),
                'turn_count': summary.get('turn_count', 0),
                'invalid_action_count': summary.get('invalid_action_count', 0),
                'total_reward': summary.get('total_reward', 0.0),
                'reward_channels': episode_dataset.get('reward_channels', {}),
                'transition_count': episode_dataset.get('transition_count', 0),
                'preference_pair_count': episode_dataset.get('preference_pair_count', 0),
                'artifact_paths': {
                    **result['artifact_paths'],
                    'trajectory': str(trajectory_path),
                    'transitions': episode_dataset.get('transition_path'),
                    'preferences': episode_dataset.get('preference_path'),
                },
            }
        )
        if result['transition_count'] < args.min_transitions:
            result['status'] = 'failed'
            result['terminal_reason'] = 'insufficient-transitions'
    except Exception as exc:
        result['terminal_reason'] = result.get('terminal_reason') or 'episode-error'
        result['error'] = str(exc)
    finally:
        if server_process is not None:
            _stop_process(server_process)
    result_path = episode_dir / 'episode_result.json'
    result['result_path'] = str(result_path)
    _write_json(result_path, result)
    return result


def _run_episode_specs(
    specs: Iterable[EpisodeSpec],
    *,
    args: argparse.Namespace,
    run_dir: Path,
    dm_env_path: Path,
    player_env_path: Path,
    character_load_path: Path | None,
    base_url: str | None,
    episode_runner,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs_tuple = tuple(specs)
    workers = max(1, min(int(args.workers), len(specs_tuple)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                episode_runner,
                spec,
                args=args,
                run_dir=run_dir,
                dm_env_path=dm_env_path,
                player_env_path=player_env_path,
                character_load_path=character_load_path,
                base_url=base_url,
            ): spec
            for spec in specs_tuple
        }
        for future in as_completed(futures):
            rows.append(future.result())
    return sorted(rows, key=lambda item: int(item.get('index', 0)))


def _write_episode_datasets(spec: EpisodeSpec, *, trajectory_path: Path, episode_dir: Path) -> dict[str, Any]:
    dataset_dir = episode_dir / 'datasets'
    transitions = build_training_transitions(trajectory_path)
    for transition in transitions:
        transition['conversation_id'] = spec.episode_id
        transition['conversation_label'] = spec.label
        transition['behavior_profile'] = spec.behavior_profile
    transition_path = dataset_dir / 'training_transitions.jsonl'
    write_training_transitions_jsonl(transitions, transition_path)
    preferences = build_preference_pairs(transitions)
    for pair in preferences:
        pair['conversation_id'] = spec.episode_id
        pair['conversation_label'] = spec.label
        pair['transition_path'] = str(transition_path)
    preference_path = dataset_dir / 'preference_pairs.jsonl'
    write_preference_pairs_jsonl(preferences, preference_path)
    transition_quality = validate_transition_dataset(transition_path)
    preference_quality = validate_preference_dataset(preference_path)
    write_dataset_quality_report(transition_quality, dataset_dir / 'transition_quality.json')
    write_dataset_quality_report(preference_quality, dataset_dir / 'preference_quality.json')
    return {
        'transition_path': str(transition_path),
        'preference_path': str(preference_path),
        'transition_count': len(transitions),
        'preference_pair_count': len(preferences),
        'reward_channels': _reward_channel_totals(transitions),
        'transition_quality_status': transition_quality['status'],
        'preference_quality_status': preference_quality['status'],
    }


def _write_combined_datasets(run_dir: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    dataset_dir = run_dir / 'datasets'
    transition_sources = [
        Path(row['artifact_paths']['transitions'])
        for row in results
        if isinstance(row.get('artifact_paths'), dict) and row['artifact_paths'].get('transitions')
    ]
    transition_path = dataset_dir / 'combined_training_transitions.jsonl'
    preference_path = dataset_dir / 'combined_preference_pairs.jsonl'
    _concatenate_jsonl(transition_sources, transition_path)
    preferences = build_preference_pairs(
        transition_path,
        context_strategy='scene',
        max_pairs_per_context=10,
    )
    write_preference_pairs_jsonl(preferences, preference_path)
    transition_quality = validate_transition_dataset(transition_path)
    preference_quality = validate_preference_dataset(preference_path)
    transition_quality_path = write_dataset_quality_report(transition_quality, dataset_dir / 'combined_transition_quality.json')
    preference_quality_path = write_dataset_quality_report(preference_quality, dataset_dir / 'combined_preference_quality.json')
    return {
        'transition_path': str(transition_path),
        'preference_path': str(preference_path),
        'transition_quality_path': str(transition_quality_path),
        'preference_quality_path': str(preference_quality_path),
        'transition_quality': transition_quality,
        'preference_quality': preference_quality,
    }


def _server_command(
    args: argparse.Namespace,
    spec: EpisodeSpec,
    paths: dict[str, Path],
    dm_env_path: Path,
    character_load_path: Path | None,
    base_url: str | None,
) -> list[str]:
    campaign_root = _prepare_episode_campaign_root(args.campaign_root, paths['campaign_root'])
    command = [
        sys.executable,
        'user-test/web_story_demo_server.py',
        '--host',
        args.host,
        '--http-port',
        str(spec.http_port),
        '--ws-port',
        str(spec.ws_port),
        '--env-path',
        str(dm_env_path),
        '--trajectory-dir',
        str(paths['web_trajectories']),
    ]
    if character_load_path is not None:
        command.extend(['--load-characters', str(character_load_path)])
    if base_url is not None:
        command.extend(['--base-url', base_url])
    command.extend(['--campaign-root', str(campaign_root)])
    return command


def _connector_command(args: argparse.Namespace, spec: EpisodeSpec, paths: dict[str, Path], player_env_path: Path) -> list[str]:
    return [
        sys.executable,
        'user-test/web_story_demo_party_connector.py',
        '--base-url',
        f'http://{args.host}:{spec.http_port}',
        '--env-path',
        str(player_env_path),
        '--max-actions',
        str(args.max_actions),
        '--poll-interval-seconds',
        str(args.poll_interval_seconds),
        '--monster-turn-delay-seconds',
        str(args.monster_turn_delay_seconds),
        '--request-timeout-seconds',
        str(args.request_timeout_seconds),
        '--transcript-path',
        str(paths['transcript']),
        '--interaction-log-path',
        str(paths['raw_interactions']),
        '--behavior-profile',
        spec.behavior_profile,
        '--negative-intensity',
        str(spec.negative_intensity),
        '--verbose',
    ]


def _episode_paths(episode_dir: Path) -> dict[str, Path]:
    return {
        'episode_dir': episode_dir,
        'logs': episode_dir / 'logs',
        'web_trajectories': episode_dir / 'web-trajectories',
        'campaign_root': episode_dir / 'campaign-root',
        'transcript': episode_dir / 'deepseek-party-transcript.md',
        'raw_interactions': episode_dir / 'raw-llm-interactions.jsonl',
    }


def _prepare_episode_campaign_root(source_root: Path | None, target_root: Path) -> Path:
    resolved_source = _resolve_path(source_root) if source_root is not None else (REPO_ROOT / 'campaigns').resolve()
    if not resolved_source.exists():
        raise DeepSeekDatasetRunnerError(f'campaign root not found: {resolved_source}')
    resolved_target = target_root.resolve()
    if resolved_source == resolved_target:
        return resolved_target
    episode_dir = target_root.parent.resolve()
    if not _path_is_relative_to(resolved_target, episode_dir):
        raise DeepSeekDatasetRunnerError(f'episode campaign root escapes episode directory: {resolved_target}')
    if resolved_target.exists():
        shutil.rmtree(resolved_target)
    shutil.copytree(resolved_source, resolved_target)
    return resolved_target


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _terminal_reason(summary: dict[str, Any]) -> str:
    if summary.get('final_runtime_mode') == 'demo-complete':
        return 'demo-complete'
    if summary.get('terminal') is not None:
        return str(summary.get('final_runtime_mode') or 'terminal')
    return 'max-actions-or-unprocessed'


def _validate_basic_args(args: argparse.Namespace) -> None:
    if args.workers <= 0:
        raise DeepSeekDatasetRunnerError('--workers must be > 0.')
    if hasattr(args, 'max_actions') and args.max_actions <= 0:
        raise DeepSeekDatasetRunnerError('--max-actions must be > 0.')


def _resolve_output_root(path: Path) -> Path:
    return _resolve_path(path)


def _resolve_path(path: Path) -> Path:
    return (REPO_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _resolve_existing(path: Path, *, label: str) -> Path:
    resolved = _resolve_path(path)
    if not resolved.exists():
        raise DeepSeekDatasetRunnerError(f'{label} not found: {resolved}')
    return resolved


def _resolve_optional(path: Path | None, *, label: str) -> Path | None:
    if path is None:
        return None
    return _resolve_existing(path, label=label)


def _resolve_base_url(base_url: str | None, mirror_root: Path) -> str | None:
    if base_url:
        return base_url
    resolved_mirror = _resolve_path(mirror_root)
    if resolved_mirror.exists():
        return resolved_mirror.as_uri().rstrip('/') + '/'
    return None


def _start_logged_process(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> subprocess.Popen[bytes]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_path.open('wb')
    stderr_handle = stderr_path.open('wb')
    try:
        process = subprocess.Popen(command, cwd=cwd, stdout=stdout_handle, stderr=stderr_handle, env=_subprocess_env())
        stdout_handle.close()
        stderr_handle.close()
        return process
    except Exception:
        stdout_handle.close()
        stderr_handle.close()
        raise


def _run_logged_process(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path, timeout_seconds: float) -> int:
    process = _start_logged_process(command, cwd=cwd, stdout_path=stdout_path, stderr_path=stderr_path)
    try:
        return process.wait(timeout=timeout_seconds if timeout_seconds > 0 else None)
    except subprocess.TimeoutExpired as exc:
        _stop_process(process)
        raise DeepSeekDatasetRunnerError(f'process timed out after {timeout_seconds} seconds: {_printable_command(command)}') from exc


def _wait_for_server(*, url: str, process: subprocess.Popen[bytes], timeout_seconds: float, stderr_path: Path) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise DeepSeekDatasetRunnerError(f'web server exited before ready. stderr tail: {_read_tail(stderr_path)}')
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except URLError:
            pass
        time.sleep(0.5)
    raise DeepSeekDatasetRunnerError(f'web server did not become ready at {url} within {timeout_seconds} seconds.')


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _latest_trajectory(trajectory_root: Path) -> Path:
    candidates = [path for path in trajectory_root.glob('**/trajectory.jsonl') if path.is_file()]
    if not candidates:
        raise DeepSeekDatasetRunnerError(f'no trajectory.jsonl files were written under {trajectory_root}')
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get('PYTHONPATH')
    env['PYTHONPATH'] = str(REPO_ROOT) if not existing else f'{REPO_ROOT}{os.pathsep}{existing}'
    return env


def _read_tail(path: Path, *, max_chars: int = 2000) -> str:
    if not path.exists():
        return ''
    return path.read_text(encoding='utf-8', errors='replace')[-max_chars:].strip()


def _printable_command(command: list[str]) -> str:
    return ' '.join(f'"{part}"' if ' ' in part else part for part in command)


def _interleaved_labels(positive_count: int, negative_count: int) -> list[str]:
    labels: list[str] = []
    while positive_count or negative_count:
        if positive_count:
            labels.append('positive')
            positive_count -= 1
        if negative_count:
            labels.append('negative')
            negative_count -= 1
    return labels


def _label_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {'negative': 0, 'positive': 0}
    for row in rows:
        label = row.get('label')
        if label in counts:
            counts[label] += 1
    return {key: value for key, value in counts.items() if value}


def _reward_channel(row: dict[str, Any], channel: str) -> float:
    channels = row.get('reward_channels')
    if isinstance(channels, dict) and isinstance(channels.get(channel), (int, float)):
        return float(channels[channel])
    return 0.0


def _reward_channel_totals(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        channels = row.get('reward_channels')
        if not isinstance(channels, dict):
            continue
        for channel, value in channels.items():
            if isinstance(value, (int, float)):
                totals[str(channel)] = totals.get(str(channel), 0.0) + float(value)
    return dict(sorted(totals.items()))


def _failure_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.get('status') != 'completed') / len(rows)


def _average(values: Iterable[Any]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return 0.0
    return sum(numeric) / len(numeric)


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {'severity': severity, 'code': code, 'message': message}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
    return path


def _concatenate_jsonl(sources: Iterable[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as output:
        for source in sources:
            if not source.exists():
                continue
            for line in source.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    output.write(line + '\n')
    return output_path


if __name__ == '__main__':
    raise SystemExit(main())
