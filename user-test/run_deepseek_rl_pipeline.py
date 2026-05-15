from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_collection import collect_training_datasets
from training.dataset_manifest import write_dataset_manifest
from training.evaluation import summarize_policy_evaluation, write_policy_evaluation_report
from training.mosaicml_plan import build_mosaicml_training_plan
from training.preferences import build_preference_pairs, write_preference_pairs_jsonl
from training.readiness_report import (
    build_training_readiness_report,
    write_training_readiness_markdown,
    write_training_readiness_report,
)
from training.supervised_baseline import run_supervised_action_baseline
from training.training_recipe import build_training_recipe
from training.training_smoke import build_training_smoke_report
from training.command_head_policy import run_command_head_policy_preflight
from training.trajectory_summary import summarize_batch, summarize_trajectory
from training.transitions import build_training_transitions, write_training_transitions_jsonl


PLAYER_CONTROLLER_IDS = (
    'player-1-controller',
    'player-2-controller',
    'player-3-controller',
    'player-4-controller',
)
SCENARIO_ID = 'lmop_full_story_demo'


class DeepSeekRLPipelineError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run DeepSeek DM + DeepSeek player agents, then feed the resulting trajectory into the RL data pipeline.'
    )
    parser.add_argument('--output-root', type=Path, default=Path('runs/deepseek-rl-pipeline'), help='Root directory for this combined run.')
    parser.add_argument('--run-id', help='Optional run id. Defaults to all-llm-pipeline-<utc timestamp>-<suffix>.')
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='DM DeepSeek env file.')
    parser.add_argument(
        '--player-env-path',
        type=Path,
        default=Path('user-test/llm-players/deepseek-v4-flash-player.env'),
        help='DeepSeek-compatible env file for the four autonomous player agents.',
    )
    parser.add_argument(
        '--character-load-path',
        type=Path,
        default=Path('user-test/saved-characters/lmop-balanced-test-party.json'),
        help='Prebuilt four-character party JSON file.',
    )
    parser.add_argument('--campaign-root', type=Path, help='Optional campaign markdown root override for the web server.')
    parser.add_argument('--mirror-root', type=Path, default=Path('5etools-mirror-2.github.io'), help='Local 5etools mirror root.')
    parser.add_argument('--base-url', help='Optional 5etools base URL. Defaults to file:///<mirror-root>/ when the mirror exists.')
    parser.add_argument('--host', default='127.0.0.1', help='Web server host.')
    parser.add_argument('--http-port', type=int, default=8000, help='Web server HTTP port.')
    parser.add_argument('--ws-port', type=int, default=8767, help='Web server websocket port.')
    parser.add_argument('--max-actions', type=int, default=60, help='Maximum autonomous player actions to request from the party connector.')
    parser.add_argument('--poll-interval-seconds', type=float, default=0.5, help='Party connector poll interval.')
    parser.add_argument('--monster-turn-delay-seconds', type=float, default=0.2, help='Delay before auto-ending DM monster turns.')
    parser.add_argument('--request-timeout-seconds', type=float, default=0.0, help='Connector HTTP timeout. Use 0 to disable.')
    parser.add_argument('--server-start-timeout-seconds', type=float, default=90.0, help='How long to wait for the web server to become ready.')
    parser.add_argument('--pre-connector-delay-seconds', type=float, default=5.0, help='Pause after the web server starts so you can open the browser view.')
    parser.add_argument('--connector-timeout-seconds', type=float, default=3600.0, help='How long to let the LLM party connector run.')
    parser.add_argument('--min-transitions', type=int, default=1, help='Fail if fewer player training transitions are exported.')
    parser.add_argument('--command-head-epochs', type=int, default=3, help='Local command-head preflight epochs.')
    parser.add_argument('--gpu-type', default='mosaicml-gpu', help='GPU type/preset recorded in the MosaicML handoff plan.')
    parser.add_argument('--container-image', default='dnd-agents-training', help='Container image recorded in the MosaicML handoff plan.')
    parser.add_argument('--keep-server-on-failure', action='store_true', help='Leave the web server running if the connector or pipeline fails.')
    parser.add_argument('--dry-run', action='store_true', help='Print the web/connector commands and output locations without calling DeepSeek.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_pipeline(args)
    except DeepSeekRLPipelineError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or f'all-llm-pipeline-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    run_dir = (REPO_ROOT / args.output_root / run_id).resolve()
    paths = _build_paths(run_dir)
    dm_env_path = _resolve_existing(args.env_path, label='DM env file')
    player_env_path = _resolve_existing(args.player_env_path, label='player env file')
    character_load_path = _resolve_existing(args.character_load_path, label='character party file')
    base_url = _resolve_base_url(args.base_url, args.mirror_root)
    server_command = _server_command(args, paths, dm_env_path, character_load_path, base_url)
    connector_command = _connector_command(args, paths, player_env_path)

    if args.dry_run:
        return {
            'status': 'dry_run',
            'run_id': run_id,
            'run_dir': str(run_dir),
            'web_url': f'http://{args.host}:{args.http_port}/?portal=dm&autoconnect=1',
            'server_command': _printable_command(server_command),
            'connector_command': _printable_command(connector_command),
            'note': 'No model calls were made. Remove --dry-run to run DeepSeek and generate trajectory data.',
        }

    for key, path in paths.items():
        if key != 'transcript':
            path.mkdir(parents=True, exist_ok=True)

    server_process: subprocess.Popen[bytes] | None = None
    try:
        server_process = _start_logged_process(
            server_command,
            cwd=REPO_ROOT,
            stdout_path=paths['logs'] / 'web-server.stdout.log',
            stderr_path=paths['logs'] / 'web-server.stderr.log',
        )
        _wait_for_server(
            url=f'http://{args.host}:{args.http_port}/healthz',
            process=server_process,
            timeout_seconds=args.server_start_timeout_seconds,
            stderr_path=paths['logs'] / 'web-server.stderr.log',
        )
        print(f'[pipeline] Web server ready: http://{args.host}:{args.http_port}/?portal=dm&autoconnect=1', flush=True)
        if args.pre_connector_delay_seconds > 0:
            print(f'[pipeline] Starting party connector in {args.pre_connector_delay_seconds:g} seconds...', flush=True)
            time.sleep(args.pre_connector_delay_seconds)
        connector_return_code = _run_logged_process(
            connector_command,
            cwd=REPO_ROOT,
            stdout_path=paths['logs'] / 'party-connector.stdout.log',
            stderr_path=paths['logs'] / 'party-connector.stderr.log',
            timeout_seconds=args.connector_timeout_seconds,
        )
        if connector_return_code != 0:
            raise DeepSeekRLPipelineError(
                f'party connector exited with code {connector_return_code}; see {paths["logs"] / "party-connector.stderr.log"}'
            )
    except Exception:
        if server_process is not None and args.keep_server_on_failure:
            print('[pipeline] Leaving web server running because --keep-server-on-failure was set.', flush=True)
            server_process = None
        raise
    finally:
        if server_process is not None:
            _stop_process(server_process)

    trajectory_path = _latest_trajectory(paths['web_trajectories'])
    batch_report = _write_batch_artifacts(
        trajectory_path=trajectory_path,
        batch_root=paths['batches'],
        dm_env_path=dm_env_path,
        player_env_path=player_env_path,
        character_load_path=character_load_path,
        transcript_path=paths['transcript'],
        base_url=base_url,
        args=args,
    )
    if batch_report['transition_count'] < args.min_transitions:
        raise DeepSeekRLPipelineError(
            f'exported {batch_report["transition_count"]} player transitions, below --min-transitions {args.min_transitions}.'
        )

    collected = collect_training_datasets([Path(batch_report['report_path'])], output_dir=paths['datasets'])
    readiness_json_path = paths['readiness'] / 'training_readiness.json'
    readiness_md_path = paths['readiness'] / 'training_readiness.md'
    readiness = build_training_readiness_report([paths['datasets']])
    write_training_readiness_report(readiness, readiness_json_path)
    write_training_readiness_markdown(readiness, readiness_md_path)
    smoke = build_training_smoke_report(
        [paths['datasets']],
        output_dir=paths['smoke'],
        run_name='all-llm-smoke',
        allow_not_ready=True,
    )
    recipe = build_training_recipe(
        Path(smoke['report_path']),
        output_dir=paths['recipes'],
        recipe_name='all-llm-training-recipe',
        objective_mix={
            'supervised_action_prediction': 0.6,
            'preference_ranking': 0.4,
        },
        allow_failed_smoke=True,
    )
    baseline = run_supervised_action_baseline(
        Path(recipe['recipe_path']),
        output_dir=paths['training_runs'],
        run_name='all-llm-supervised-baseline',
        split_strategy='tail',
    )
    command_head = run_command_head_policy_preflight(
        Path(recipe['recipe_path']),
        baseline_report_path=Path(baseline['report_path']),
        output_dir=paths['training_runs'],
        run_name='all-llm-command-head-policy',
        epochs=args.command_head_epochs,
        split_strategy='tail',
    )
    mosaicml_plan = build_mosaicml_training_plan(
        Path(recipe['recipe_path']),
        baseline_report_path=Path(baseline['report_path']),
        output_dir=paths['mosaicml_plans'],
        plan_name='all-llm-mosaicml-plan',
        accelerator='gpu',
        gpu_type=args.gpu_type,
        container_image=args.container_image,
    )

    pipeline_report = {
        'status': 'completed',
        'run_id': run_id,
        'run_dir': str(run_dir),
        'web_url': f'http://{args.host}:{args.http_port}/?portal=dm&autoconnect=1',
        'trajectory_path': str(trajectory_path),
        'transcript_path': str(paths['transcript']),
        'batch_report_path': batch_report['report_path'],
        'transition_count': batch_report['transition_count'],
        'preference_pair_count': batch_report['preference_pair_count'],
        'collection_report_path': collected.get('report_path'),
        'readiness_json_path': str(readiness_json_path),
        'readiness_md_path': str(readiness_md_path),
        'readiness_status': readiness.get('status'),
        'smoke_report_path': smoke['report_path'],
        'recipe_path': recipe['recipe_path'],
        'baseline_report_path': baseline['report_path'],
        'command_head_report_path': command_head['report_path'],
        'mosaicml_plan_path': mosaicml_plan['plan_path'],
        'logs_dir': str(paths['logs']),
    }
    pipeline_report_path = run_dir / 'all_llm_pipeline_report.json'
    pipeline_report['pipeline_report_path'] = str(pipeline_report_path)
    pipeline_report_path.write_text(json.dumps(pipeline_report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return pipeline_report


def _build_paths(run_dir: Path) -> dict[str, Path]:
    return {
        'run_dir': run_dir,
        'logs': run_dir / 'logs',
        'web_trajectories': run_dir / 'web-trajectories',
        'batches': run_dir / 'batches',
        'datasets': run_dir / 'datasets',
        'readiness': run_dir / 'readiness',
        'smoke': run_dir / 'smoke',
        'recipes': run_dir / 'recipes',
        'training_runs': run_dir / 'training-runs',
        'mosaicml_plans': run_dir / 'mosaicml-plans',
        'transcript': run_dir / 'deepseek-party-transcript.md',
    }


def _resolve_existing(path: Path, *, label: str) -> Path:
    resolved = (REPO_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.exists():
        raise DeepSeekRLPipelineError(f'{label} not found: {resolved}')
    return resolved


def _resolve_base_url(base_url: str | None, mirror_root: Path) -> str | None:
    if base_url:
        return base_url
    resolved_mirror = (REPO_ROOT / mirror_root).resolve() if not mirror_root.is_absolute() else mirror_root.resolve()
    if resolved_mirror.exists():
        return resolved_mirror.as_uri().rstrip('/') + '/'
    return None


def _server_command(
    args: argparse.Namespace,
    paths: dict[str, Path],
    dm_env_path: Path,
    character_load_path: Path,
    base_url: str | None,
) -> list[str]:
    command = [
        sys.executable,
        'user-test/web_story_demo_server.py',
        '--host',
        args.host,
        '--http-port',
        str(args.http_port),
        '--ws-port',
        str(args.ws_port),
        '--env-path',
        str(dm_env_path),
        '--load-characters',
        str(character_load_path),
        '--trajectory-dir',
        str(paths['web_trajectories']),
    ]
    if base_url is not None:
        command.extend(['--base-url', base_url])
    if args.campaign_root is not None:
        campaign_root = (REPO_ROOT / args.campaign_root).resolve() if not args.campaign_root.is_absolute() else args.campaign_root.resolve()
        command.extend(['--campaign-root', str(campaign_root)])
    return command


def _connector_command(args: argparse.Namespace, paths: dict[str, Path], player_env_path: Path) -> list[str]:
    return [
        sys.executable,
        'user-test/web_story_demo_party_connector.py',
        '--base-url',
        f'http://{args.host}:{args.http_port}',
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
        '--verbose',
    ]


def _start_logged_process(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path) -> subprocess.Popen[bytes]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_path.open('wb')
    stderr_handle = stderr_path.open('wb')
    env = _subprocess_env()
    try:
        process = subprocess.Popen(command, cwd=cwd, stdout=stdout_handle, stderr=stderr_handle, env=env)
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
        raise DeepSeekRLPipelineError(f'process timed out after {timeout_seconds} seconds: {_printable_command(command)}') from exc


def _wait_for_server(*, url: str, process: subprocess.Popen[bytes], timeout_seconds: float, stderr_path: Path) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            details = _read_tail(stderr_path)
            raise DeepSeekRLPipelineError(f'web server exited before becoming ready. stderr tail: {details}')
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except URLError:
            pass
        time.sleep(0.5)
    raise DeepSeekRLPipelineError(f'web server did not become ready at {url} within {timeout_seconds} seconds.')


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
        raise DeepSeekRLPipelineError(f'no trajectory.jsonl files were written under {trajectory_root}')
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _write_batch_artifacts(
    *,
    trajectory_path: Path,
    batch_root: Path,
    dm_env_path: Path,
    player_env_path: Path,
    character_load_path: Path,
    transcript_path: Path,
    base_url: str | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    batch_dir = batch_root / f'{SCENARIO_ID}-all-llm-web-batch-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    batch_episode_dir = batch_dir / 'episodes' / trajectory_path.parent.name
    batch_episode_dir.mkdir(parents=True, exist_ok=True)
    copied_trajectory_path = batch_episode_dir / 'trajectory.jsonl'
    shutil.copy2(trajectory_path, copied_trajectory_path)

    episode_summary = summarize_trajectory(copied_trajectory_path)
    transitions = build_training_transitions(copied_trajectory_path)
    transitions_path = batch_dir / 'training_transitions.jsonl'
    write_training_transitions_jsonl(transitions, transitions_path)
    transition_manifest_path = write_dataset_manifest(
        dataset_type='training_transitions',
        dataset_path=transitions_path,
        record_count=len(transitions),
        source_paths=[copied_trajectory_path],
        filters={
            'include_roles': ['player'],
            'include_sources': None,
            'include_errors': True,
        },
        context=_dataset_context(
            batch_id=batch_dir.name,
            dm_env_path=dm_env_path,
            player_env_path=player_env_path,
            character_load_path=character_load_path,
            transcript_path=transcript_path,
            base_url=base_url,
            args=args,
        ),
    )

    preference_pairs = build_preference_pairs(transitions)
    for pair in preference_pairs:
        pair['transition_path'] = str(transitions_path)
    preference_path = batch_dir / 'preference_pairs.jsonl'
    write_preference_pairs_jsonl(preference_pairs, preference_path)
    preference_manifest_path = write_dataset_manifest(
        dataset_type='preference_pairs',
        dataset_path=preference_path,
        record_count=len(preference_pairs),
        source_paths=[transitions_path],
        filters={
            'min_reward_gap': 0.05,
            'max_pairs_per_context': 3,
            'include_errors': True,
        },
        context={
            **_dataset_context(
                batch_id=batch_dir.name,
                dm_env_path=dm_env_path,
                player_env_path=player_env_path,
                character_load_path=character_load_path,
                transcript_path=transcript_path,
                base_url=base_url,
                args=args,
            ),
            'transition_path': str(transitions_path),
        },
    )
    evaluation_report = summarize_policy_evaluation(transitions, episode_summaries=[episode_summary])
    evaluation_report['transition_path'] = str(transitions_path)
    evaluation_path = batch_dir / 'policy_evaluation.json'
    write_policy_evaluation_report(evaluation_report, evaluation_path)

    report = {
        'batch_id': batch_dir.name,
        'scenario_id': SCENARIO_ID,
        'policy': 'all-llm-web',
        'dm_controller': 'deepseek-web-dm',
        'llm_player_controllers': list(PLAYER_CONTROLLER_IDS),
        'llm_player_max_actions_per_pump': None,
        'max_actions': args.max_actions,
        'character_load_path': str(character_load_path),
        'campaign_root': str(args.campaign_root) if args.campaign_root is not None else None,
        'base_url': base_url,
        'output_dir': str(batch_dir),
        'trajectory_path': str(copied_trajectory_path),
        'source_trajectory_path': str(trajectory_path),
        'transcript_path': str(transcript_path),
        'transition_path': str(transitions_path),
        'transition_manifest_path': str(transition_manifest_path),
        'transition_count': len(transitions),
        'preference_path': str(preference_path),
        'preference_manifest_path': str(preference_manifest_path),
        'preference_pair_count': len(preference_pairs),
        'evaluation_path': str(evaluation_path),
        'policy_evaluation': evaluation_report,
        **summarize_batch([episode_summary]),
    }
    report_path = batch_dir / 'batch_report.json'
    report['report_path'] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


def _dataset_context(
    *,
    batch_id: str,
    dm_env_path: Path,
    player_env_path: Path,
    character_load_path: Path,
    transcript_path: Path,
    base_url: str | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        'batch_id': batch_id,
        'scenario_id': SCENARIO_ID,
        'policy': 'all-llm-web',
        'dm_runtime': 'web_story_demo_server',
        'player_runtime': 'web_story_demo_party_connector',
        'dm_env_path': str(dm_env_path),
        'player_env_path': str(player_env_path),
        'character_load_path': str(character_load_path),
        'transcript_path': str(transcript_path),
        'base_url': base_url,
        'max_actions': args.max_actions,
        'host': args.host,
        'http_port': args.http_port,
        'ws_port': args.ws_port,
    }


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get('PYTHONPATH')
    env['PYTHONPATH'] = str(REPO_ROOT) if not existing else f'{REPO_ROOT}{os.pathsep}{existing}'
    return env


def _read_tail(path: Path, *, max_chars: int = 2000) -> str:
    if not path.exists():
        return ''
    text = path.read_text(encoding='utf-8', errors='replace')
    return text[-max_chars:].strip()


def _printable_command(command: list[str]) -> str:
    return ' '.join(f'"{part}"' if ' ' in part else part for part in command)


if __name__ == '__main__':
    raise SystemExit(main())
