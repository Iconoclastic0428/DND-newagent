from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Callable
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

USER_TEST_ROOT = Path(__file__).resolve().parent
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from dm_agent.client import LLMClient
from dm_agent.config import load_llm_config
from session_server.llm_player import LLMPlayerAgent
from shared_types.encounter_models import ActorSide, EncounterPhase
from shared_types.storytelling import RuntimeMode
from story_demo_system_server import build_full_story_demo_manual_session
from training.trajectory import TrajectoryRecorder
from training.trajectory_summary import summarize_batch, summarize_trajectory
from web_story_demo_server import LocalDemoLLMTransport


FIRST_COMBAT_SCRIPT = REPO_ROOT / 'user-test' / 'full-story-demo' / 'scripts' / 'lmop-friendly-live-web-run.json'
PLAYER_CONTROLLER_IDS = (
    'player-1-controller',
    'player-2-controller',
    'player-3-controller',
    'player-4-controller',
)
POLICIES = {'scripted', 'llm-party'}
LLMPlayerAgentFactory = Callable[[], tuple[LLMPlayerAgent, ...]]


class TrainingBatchError(RuntimeError):
    pass


def run_batch(
    *,
    episodes: int,
    output_dir: str | Path,
    scenario_id: str = 'lmop_first_combat',
    env_path: str | Path = '.env',
    base_url: str | None = None,
    max_combat_turns: int = 80,
    policy: str = 'scripted',
    llm_player_specs: tuple[tuple[str, str | Path], ...] | None = None,
    llm_player_agent_factory: LLMPlayerAgentFactory | None = None,
    llm_player_max_actions_per_pump: int = 1,
) -> dict[str, Any]:
    if episodes <= 0:
        raise TrainingBatchError('episodes must be greater than 0.')
    if scenario_id != 'lmop_first_combat':
        raise TrainingBatchError(f'Unsupported scenario_id: {scenario_id!r}.')
    policy = _normalize_policy(policy)
    resolved_llm_specs = _resolve_llm_player_specs(policy=policy, env_path=env_path, llm_player_specs=llm_player_specs)
    batch_dir = Path(output_dir) / f'{scenario_id}-batch-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    episode_output_dir = batch_dir / 'episodes'
    episode_summaries: list[dict[str, Any]] = []
    for episode_index in range(1, episodes + 1):
        try:
            trajectory_path = run_first_combat_episode(
                output_dir=episode_output_dir,
                episode_id=f'{scenario_id}-{episode_index:04d}',
                scenario_id=scenario_id,
                env_path=env_path,
                base_url=base_url,
                max_combat_turns=max_combat_turns,
                policy=policy,
                llm_player_agents=_build_episode_llm_agents(
                    resolved_llm_specs,
                    llm_player_agent_factory=llm_player_agent_factory,
                ),
                llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
            )
            summary = summarize_trajectory(trajectory_path)
        except Exception as exc:
            summary = {
                'episode_id': f'{scenario_id}-{episode_index:04d}',
                'scenario_id': scenario_id,
                'record_count': 0,
                'turn_count': 0,
                'invalid_action_count': 1,
                'total_reward': 0.0,
                'success': False,
                'terminal': None,
                'final_runtime_mode': None,
                'final_scene_id': None,
                'final_party_hp_ratio': None,
                'action_count_by_agent': {},
                'action_count_by_source': {},
                'error_messages': [str(exc)],
            }
        episode_summaries.append(summary)
    report = {
        'batch_id': batch_dir.name,
        'scenario_id': scenario_id,
        'policy': policy,
        'llm_player_controllers': [controller_id for controller_id, _env_path in resolved_llm_specs],
        'llm_player_max_actions_per_pump': llm_player_max_actions_per_pump,
        'max_combat_turns': max_combat_turns,
        'output_dir': str(batch_dir),
        **summarize_batch(episode_summaries),
    }
    batch_dir.mkdir(parents=True, exist_ok=True)
    report_path = batch_dir / 'batch_report.json'
    report['report_path'] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


def run_first_combat_episode(
    *,
    output_dir: str | Path,
    episode_id: str,
    scenario_id: str,
    env_path: str | Path,
    base_url: str | None,
    max_combat_turns: int,
    policy: str = 'scripted',
    llm_player_agents: tuple[LLMPlayerAgent, ...] = (),
    llm_player_max_actions_per_pump: int = 1,
) -> Path:
    policy = _normalize_policy(policy)
    recorder = TrajectoryRecorder(output_dir=output_dir, scenario_id=scenario_id, episode_id=episode_id)
    session = build_full_story_demo_manual_session(
        base_url=base_url,
        env_path=env_path,
        client_transport=LocalDemoLLMTransport(),
        llm_player_agents=llm_player_agents,
        llm_player_autopump=(policy == 'llm-party'),
        llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
        trajectory_recorder=recorder,
    )
    _run_script_until_combat(session)
    if policy == 'scripted':
        _finish_first_combat(session, max_combat_turns=max_combat_turns)
    else:
        _finish_first_combat_with_llm_players(
            session,
            max_combat_turns=max_combat_turns,
            llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
        )
    return recorder.path


def build_llm_player_agents(specs: tuple[tuple[str, str | Path], ...]) -> tuple[LLMPlayerAgent, ...]:
    agents: list[LLMPlayerAgent] = []
    for controller_id, env_path in specs:
        config = load_llm_config(env_path=env_path)
        agents.append(
            LLMPlayerAgent(
                controller_id=controller_id,
                client=LLMClient(config),
                label=config.responses_model,
            )
        )
    return tuple(agents)


def parse_llm_player_specs(raw_specs: list[str]) -> tuple[tuple[str, Path], ...]:
    specs: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for raw_spec in raw_specs:
        if '=' not in raw_spec:
            raise TrainingBatchError(f'LLM player spec must be CONTROLLER_ID=ENV_PATH: {raw_spec!r}.')
        controller_id, env_path_text = raw_spec.split('=', 1)
        controller_id = controller_id.strip()
        env_path_text = env_path_text.strip()
        if controller_id not in PLAYER_CONTROLLER_IDS:
            raise TrainingBatchError(f'Unknown player controller for LLM player: {controller_id!r}.')
        if controller_id in seen:
            raise TrainingBatchError(f'Duplicate LLM player controller: {controller_id!r}.')
        if not env_path_text:
            raise TrainingBatchError(f'LLM player {controller_id!r} is missing an env path.')
        seen.add(controller_id)
        specs.append((controller_id, Path(env_path_text)))
    return tuple(specs)


def _normalize_policy(policy: str) -> str:
    normalized = policy.strip().lower()
    if normalized not in POLICIES:
        raise TrainingBatchError(f'Unsupported policy: {policy!r}. Expected one of: {", ".join(sorted(POLICIES))}.')
    return normalized


def _resolve_llm_player_specs(
    *,
    policy: str,
    env_path: str | Path,
    llm_player_specs: tuple[tuple[str, str | Path], ...] | None,
) -> tuple[tuple[str, str | Path], ...]:
    if policy != 'llm-party':
        return ()
    if llm_player_specs is not None:
        return tuple(llm_player_specs)
    return tuple((controller_id, env_path) for controller_id in PLAYER_CONTROLLER_IDS)


def _build_episode_llm_agents(
    specs: tuple[tuple[str, str | Path], ...],
    *,
    llm_player_agent_factory: LLMPlayerAgentFactory | None,
) -> tuple[LLMPlayerAgent, ...]:
    if llm_player_agent_factory is not None:
        return tuple(llm_player_agent_factory())
    if not specs:
        return ()
    return build_llm_player_agents(specs)


def _run_script_until_combat(session) -> None:
    script = json.loads(FIRST_COMBAT_SCRIPT.read_text(encoding='utf-8'))
    for step in script['steps']:
        if step.get('type') == 'repeat':
            break
        if step.get('type') not in {'command', 'command_if_prompt'}:
            continue
        controller_id = step['controller_id']
        if step['type'] == 'command_if_prompt':
            prompt = session.prompt_for_controller(controller_id)
            if prompt is None or prompt.prompt_kind != step.get('prompt_kind'):
                continue
        session.handle_input(controller_id, step['input'])
        if step.get('input') == '/travel engage':
            break
    if session.story_session is None or session.story_session.story_state.runtime_mode != RuntimeMode.COMBAT:
        raise TrainingBatchError('First-combat setup did not enter combat.')


def _finish_first_combat(session, *, max_combat_turns: int) -> None:
    assert session.story_session is not None
    for _turn in range(max_combat_turns):
        session._refresh_demo_completion()
        state = session.story_session.state
        if state.phase == EncounterPhase.COMPLETE:
            break
        active_actor_id = state.active_actor_id
        if active_actor_id is None:
            raise TrainingBatchError('Combat has no active actor.')
        actor = state.actors[active_actor_id]
        if actor.side == ActorSide.MONSTER:
            session.handle_input('dm', f'/endturn {active_actor_id}')
            continue
        controller_id = f'{active_actor_id}-controller'
        living_enemies = [
            candidate for candidate in state.actors.values()
            if candidate.side != actor.side and candidate.current_hit_points > 0
        ]
        if not living_enemies:
            break
        target = living_enemies[0]
        if 'magic-missile' in actor.spells:
            session.handle_input(controller_id, f'/cast {active_actor_id} magic-missile {target.actor_id}')
        elif 'fire-bolt' in actor.spells:
            session.handle_input(controller_id, f'/cast {active_actor_id} fire-bolt {target.actor_id}')
        else:
            session.handle_input(controller_id, f'/endturn {active_actor_id}')
            continue
        session._refresh_demo_completion()
        if session.story_session.state.phase != EncounterPhase.COMPLETE:
            session.handle_input(controller_id, f'/endturn {active_actor_id}')
    session._refresh_demo_completion()
    if session._completion_state is None:
        raise TrainingBatchError(f'First combat did not complete within {max_combat_turns} turns.')


def _finish_first_combat_with_llm_players(
    session,
    *,
    max_combat_turns: int,
    llm_player_max_actions_per_pump: int,
) -> None:
    assert session.story_session is not None
    for _turn in range(max_combat_turns):
        session._refresh_demo_completion()
        state = session.story_session.state
        if state.phase == EncounterPhase.COMPLETE:
            break
        active_actor_id = state.active_actor_id
        if active_actor_id is None:
            raise TrainingBatchError('Combat has no active actor.')
        actor = state.actors[active_actor_id]
        if actor.side == ActorSide.MONSTER:
            session.handle_input('dm', f'/endturn {active_actor_id}')
            continue
        actions = session.pump_llm_players(max_actions=llm_player_max_actions_per_pump)
        if actions:
            continue
        controller_id = session.story_session.encounter_session.control_runtime.controller_for_actor(active_actor_id)
        session.handle_input(controller_id, f'/endturn {active_actor_id}')
    session._refresh_demo_completion()
    if session._completion_state is None:
        raise TrainingBatchError(f'LLM-player first combat did not complete within {max_combat_turns} turns.')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run repeated training/evaluation episodes and summarize trajectories.')
    parser.add_argument('--episodes', type=int, default=1, help='Number of episodes to run.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/batches'), help='Directory for batch reports and episode trajectories.')
    parser.add_argument('--scenario-id', default='lmop_first_combat', help='Scenario to run. Currently supports lmop_first_combat.')
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='Environment file used by the demo runtime.')
    parser.add_argument('--base-url', default=None, help='Optional explicit 5etools mirror base URL.')
    parser.add_argument('--max-combat-turns', type=int, default=80, help='Maximum combat turns before an episode is marked failed.')
    parser.add_argument('--policy', choices=sorted(POLICIES), default='scripted', help='Player policy to evaluate after the deterministic setup.')
    parser.add_argument(
        '--llm-player',
        action='append',
        default=[],
        metavar='CONTROLLER_ID=ENV_PATH',
        help='Assign one player controller to an LLM env file. Repeat for mixed or full LLM parties. If omitted with --policy llm-party, all four players use --env-path.',
    )
    parser.add_argument('--llm-player-max-actions-per-pump', type=int, default=1, help='Maximum LLM player actions to process per combat pump.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_batch(
        episodes=args.episodes,
        output_dir=args.output_dir,
        scenario_id=args.scenario_id,
        env_path=args.env_path,
        base_url=args.base_url,
        max_combat_turns=args.max_combat_turns,
        policy=args.policy,
        llm_player_specs=parse_llm_player_specs(args.llm_player) if args.llm_player else None,
        llm_player_max_actions_per_pump=args.llm_player_max_actions_per_pump,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
