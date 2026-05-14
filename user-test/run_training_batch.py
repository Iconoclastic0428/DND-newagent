from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
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
from shared_types.encounter_models import GridPosition
from shared_types.storytelling import RuntimeMode
from story_demo_system_server import build_full_story_demo_manual_session
from training.dataset_manifest import write_dataset_manifest
from training.evaluation import summarize_policy_evaluation, write_policy_evaluation_report
from training.preferences import build_preference_pairs, write_preference_pairs_jsonl
from training.rewards import reward_total
from training.trajectory import TrajectoryRecorder
from training.trajectory_summary import summarize_batch, summarize_trajectory
from training.transitions import build_training_transitions, write_training_transitions_jsonl
from web_story_demo_server import LocalDemoLLMTransport


FIRST_COMBAT_SCRIPT = REPO_ROOT / 'user-test' / 'full-story-demo' / 'scripts' / 'lmop-friendly-live-web-run.json'
SUPPORTED_SCENARIOS = {
    'lmop_first_combat',
    'lmop_legal_attack_probe',
    'lmop_story_opening_choices',
}
PLAYER_CONTROLLER_IDS = (
    'player-1-controller',
    'player-2-controller',
    'player-3-controller',
    'player-4-controller',
)
POLICIES = {'scripted', 'llm-party', 'random-legal'}
LLMPlayerAgentFactory = Callable[[], tuple[LLMPlayerAgent, ...]]
TARGETED_OFFENSE_SPELLS = frozenset({
    'fire-bolt',
    'guiding-bolt',
    'magic-missile',
    'ray-of-frost',
    'sacred-flame',
    'vicious-mockery',
})
TARGETED_HEALING_SPELLS = frozenset({
    'cure-wounds',
    'healing-word',
})

STORY_OPENING_CANDIDATES = (
    {
        'controller_id': 'player-1-controller',
        'action': 'I thank Gundren for trusting us and ask what danger he expects on the road to Phandalin.',
        'reward_components': {'valid_action': 0.01, 'story_progress': 0.08, 'state_progress': 0.02},
    },
    {
        'controller_id': 'player-2-controller',
        'action': 'I ask Sildar what signs of trouble he has seen between Waterdeep and Phandalin.',
        'reward_components': {'valid_action': 0.01, 'story_progress': 0.07, 'state_progress': 0.02},
    },
    {
        'controller_id': 'player-3-controller',
        'action': 'I inspect the wagon contract and supplies for anything that could become important later.',
        'reward_components': {'valid_action': 0.01, 'story_progress': 0.04, 'state_progress': 0.02},
    },
    {
        'controller_id': 'player-4-controller',
        'action': 'I ignore Gundren and try to start a tavern brawl instead of preparing for the job.',
        'reward_components': {'valid_action': 0.01},
    },
)

STORY_OPENING_CONTEXT_CUES = (
    'Gundren worries that word of the Rockseeker contract has already reached the wrong ears.',
    'Sildar quietly asks the party to watch for signs of organized bandit activity.',
    'The supply wagon includes fragile trade goods that should arrive intact.',
    'Gundren hints that speed matters because another group may be chasing the same lead.',
    'Sildar mentions that Phandalin has been short on reliable guards.',
    'A nervous teamster reports fresh wheel tracks leaving the High Road.',
    'Gundren asks the party to keep the mining details discreet until they reach town.',
    'The party notices the oxen are skittish before the road journey begins.',
    'Sildar wants the party to learn who has been intimidating travelers near Triboar Trail.',
    'Gundren reminds everyone that the job is more than a simple delivery.',
    'A merchant warns that the weather could make the trail difficult by dusk.',
    'Sildar suggests that careful questions may reveal danger before swords are drawn.',
)
STORY_OPENING_CONTEXT_PRESSURES = (
    'prioritize caution without stalling the job',
    'balance secrecy with useful questions',
    'protect the supplies and the people traveling with them',
    'gather actionable information before leaving Waterdeep',
    'show the employer that the party is organized and trustworthy',
)


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
    baseline_seed: int = 0,
    character_load_path: str | Path | None = None,
    campaign_root: str | Path | None = None,
) -> dict[str, Any]:
    if episodes <= 0:
        raise TrainingBatchError('episodes must be greater than 0.')
    if scenario_id not in SUPPORTED_SCENARIOS:
        raise TrainingBatchError(f'Unsupported scenario_id: {scenario_id!r}. Expected one of: {", ".join(sorted(SUPPORTED_SCENARIOS))}.')
    policy = _normalize_policy(policy)
    resolved_llm_specs = _resolve_llm_player_specs(policy=policy, env_path=env_path, llm_player_specs=llm_player_specs)
    batch_dir = Path(output_dir) / f'{scenario_id}-batch-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
    episode_output_dir = batch_dir / 'episodes'
    episode_summaries: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    for episode_index in range(1, episodes + 1):
        try:
            trajectory_path = run_training_episode(
                output_dir=episode_output_dir,
                episode_id=f'{scenario_id}-{episode_index:04d}',
                scenario_id=scenario_id,
                env_path=env_path,
                base_url=base_url,
                max_combat_turns=max_combat_turns,
                policy=policy,
                baseline_seed=baseline_seed + episode_index - 1,
                character_load_path=character_load_path,
                campaign_root=campaign_root,
                llm_player_agents=_build_episode_llm_agents(
                    resolved_llm_specs,
                    llm_player_agent_factory=llm_player_agent_factory,
                ),
                llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
                )
            summary = summarize_trajectory(trajectory_path)
            transition_rows.extend(build_training_transitions(trajectory_path))
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
        'baseline_seed': baseline_seed,
        'character_load_path': str(character_load_path) if character_load_path is not None else None,
        'campaign_root': str(campaign_root) if campaign_root is not None else None,
        'max_combat_turns': max_combat_turns,
        'output_dir': str(batch_dir),
        **summarize_batch(episode_summaries),
    }
    batch_dir.mkdir(parents=True, exist_ok=True)
    transitions_path = batch_dir / 'training_transitions.jsonl'
    write_training_transitions_jsonl(transition_rows, transitions_path)
    report['transition_path'] = str(transitions_path)
    report['transition_count'] = len(transition_rows)
    trajectory_paths = [
        str(summary['trajectory_path'])
        for summary in episode_summaries
        if isinstance(summary.get('trajectory_path'), str)
    ]
    dataset_context = _batch_dataset_context(
        report=report,
        env_path=env_path,
        character_load_path=character_load_path,
    )
    transition_manifest_path = write_dataset_manifest(
        dataset_type='training_transitions',
        dataset_path=transitions_path,
        record_count=len(transition_rows),
        source_paths=trajectory_paths,
        filters={
            'include_roles': ['player'],
            'include_sources': None,
            'include_errors': True,
        },
        context=dataset_context,
    )
    report['transition_manifest_path'] = str(transition_manifest_path)
    preference_pairs = build_preference_pairs(transition_rows)
    for pair in preference_pairs:
        pair['transition_path'] = str(transitions_path)
    preference_path = batch_dir / 'preference_pairs.jsonl'
    write_preference_pairs_jsonl(preference_pairs, preference_path)
    report['preference_path'] = str(preference_path)
    report['preference_pair_count'] = len(preference_pairs)
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
        context={**dataset_context, 'transition_path': str(transitions_path)},
    )
    report['preference_manifest_path'] = str(preference_manifest_path)
    evaluation_report = summarize_policy_evaluation(transition_rows, episode_summaries=episode_summaries)
    evaluation_report['transition_path'] = str(transitions_path)
    evaluation_path = batch_dir / 'policy_evaluation.json'
    write_policy_evaluation_report(evaluation_report, evaluation_path)
    report['evaluation_path'] = str(evaluation_path)
    report['policy_evaluation'] = evaluation_report
    report_path = batch_dir / 'batch_report.json'
    report['report_path'] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


def _batch_dataset_context(
    *,
    report: dict[str, Any],
    env_path: str | Path,
    character_load_path: str | Path | None,
) -> dict[str, Any]:
    return {
        'batch_id': report.get('batch_id'),
        'scenario_id': report.get('scenario_id'),
        'policy': report.get('policy'),
        'baseline_seed': report.get('baseline_seed'),
        'episodes': report.get('episodes'),
        'successes': report.get('successes'),
        'success_rate': report.get('success_rate'),
        'llm_player_controllers': report.get('llm_player_controllers') or [],
        'llm_player_max_actions_per_pump': report.get('llm_player_max_actions_per_pump'),
        'character_load_path': str(character_load_path) if character_load_path is not None else None,
        'env_path': str(env_path),
        'max_combat_turns': report.get('max_combat_turns'),
    }


def run_training_episode(
    *,
    output_dir: str | Path,
    episode_id: str,
    scenario_id: str,
    env_path: str | Path,
    base_url: str | None,
    max_combat_turns: int,
    policy: str = 'scripted',
    baseline_seed: int = 0,
    character_load_path: str | Path | None = None,
    campaign_root: str | Path | None = None,
    llm_player_agents: tuple[LLMPlayerAgent, ...] = (),
    llm_player_max_actions_per_pump: int = 1,
) -> Path:
    if scenario_id == 'lmop_first_combat':
        return run_first_combat_episode(
            output_dir=output_dir,
            episode_id=episode_id,
            scenario_id=scenario_id,
            env_path=env_path,
            base_url=base_url,
            max_combat_turns=max_combat_turns,
            policy=policy,
            baseline_seed=baseline_seed,
            character_load_path=character_load_path,
            campaign_root=campaign_root,
            llm_player_agents=llm_player_agents,
            llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
        )
    if scenario_id == 'lmop_story_opening_choices':
        return run_story_opening_choice_episode(
            output_dir=output_dir,
            episode_id=episode_id,
            scenario_id=scenario_id,
            env_path=env_path,
            base_url=base_url,
            character_load_path=character_load_path,
            campaign_root=campaign_root,
        )
    if scenario_id == 'lmop_legal_attack_probe':
        return run_legal_attack_probe_episode(
            output_dir=output_dir,
            episode_id=episode_id,
            scenario_id=scenario_id,
            env_path=env_path,
            base_url=base_url,
            character_load_path=character_load_path,
            campaign_root=campaign_root,
        )
    raise TrainingBatchError(f'Unsupported scenario_id: {scenario_id!r}.')


def run_first_combat_episode(
    *,
    output_dir: str | Path,
    episode_id: str,
    scenario_id: str,
    env_path: str | Path,
    base_url: str | None,
    max_combat_turns: int,
    policy: str = 'scripted',
    baseline_seed: int = 0,
    character_load_path: str | Path | None = None,
    campaign_root: str | Path | None = None,
    llm_player_agents: tuple[LLMPlayerAgent, ...] = (),
    llm_player_max_actions_per_pump: int = 1,
) -> Path:
    policy = _normalize_policy(policy)
    recorder = TrajectoryRecorder(output_dir=output_dir, scenario_id=scenario_id, episode_id=episode_id)
    session = build_full_story_demo_manual_session(
        base_url=base_url,
        campaign_root=campaign_root,
        env_path=env_path,
        client_transport=LocalDemoLLMTransport(),
        llm_player_agents=llm_player_agents,
        llm_player_autopump=(policy == 'llm-party'),
        llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
        character_load_path=character_load_path,
        trajectory_recorder=recorder,
    )
    _run_script_until_combat(session)
    if policy == 'scripted':
        _finish_first_combat(session, max_combat_turns=max_combat_turns)
    elif policy == 'llm-party':
        _finish_first_combat_with_llm_players(
            session,
            max_combat_turns=max_combat_turns,
            llm_player_max_actions_per_pump=llm_player_max_actions_per_pump,
        )
    elif policy == 'random-legal':
        _finish_first_combat_with_random_legal_actions(
            session,
            max_combat_turns=max_combat_turns,
            rng=random.Random(baseline_seed),
        )
    else:
        raise TrainingBatchError(f'Unsupported policy: {policy!r}.')
    return recorder.path


def run_story_opening_choice_episode(
    *,
    output_dir: str | Path,
    episode_id: str,
    scenario_id: str,
    env_path: str | Path,
    base_url: str | None,
    character_load_path: str | Path | None = None,
    campaign_root: str | Path | None = None,
) -> Path:
    recorder = TrajectoryRecorder(output_dir=output_dir, scenario_id=scenario_id, episode_id=episode_id)
    session = build_full_story_demo_manual_session(
        base_url=base_url,
        campaign_root=campaign_root,
        env_path=env_path,
        client_transport=LocalDemoLLMTransport(),
        character_load_path=character_load_path,
        precreate_characters=(character_load_path is None),
        trajectory_recorder=None,
    )
    if session.story_session is None or session.story_session.story_state.runtime_mode != RuntimeMode.STORYTELLING:
        raise TrainingBatchError('Story-opening setup did not enter storytelling mode.')
    recorder.record_event(
        record_type='story_started',
        source='system',
        runtime_mode=RuntimeMode.STORYTELLING.value,
        metadata={'scenario_id': scenario_id},
    )
    before = session._trajectory_snapshot('player-1-controller')
    before = _story_opening_context_snapshot(before, episode_id=episode_id)
    after = _story_candidate_after_snapshot(before)
    for candidate in STORY_OPENING_CANDIDATES:
        _record_story_candidate(
            recorder,
            before=before,
            after=after,
            controller_id=str(candidate['controller_id']),
            raw_text=str(candidate['action']),
            reward_components=dict(candidate['reward_components']),
        )
    recorder.record_event(
        record_type='episode_completed',
        source='system',
        runtime_mode=RuntimeMode.STORYTELLING.value,
        reward_components={},
        metadata={
            'success': True,
            'reward_total': 0.0,
            'result_summary': 'Generated opening story preference candidates.',
            **after['state'],
        },
    )
    return recorder.path


def run_legal_attack_probe_episode(
    *,
    output_dir: str | Path,
    episode_id: str,
    scenario_id: str,
    env_path: str | Path,
    base_url: str | None,
    character_load_path: str | Path | None = None,
    campaign_root: str | Path | None = None,
) -> Path:
    recorder = TrajectoryRecorder(output_dir=output_dir, scenario_id=scenario_id, episode_id=episode_id)
    session = build_full_story_demo_manual_session(
        base_url=base_url,
        campaign_root=campaign_root,
        env_path=env_path,
        client_transport=LocalDemoLLMTransport(),
        character_load_path=character_load_path,
        trajectory_recorder=recorder,
    )
    _run_script_until_combat(session)
    _advance_to_next_player_turn(session, max_turns=8)
    assert session.story_session is not None
    state = session.story_session.state
    actor = state.actors[state.active_actor_id]
    target = _first_living_enemy(state, actor)
    actor.position = _adjacent_probe_position(state, target)
    controller_id = session.story_session.encounter_session.control_runtime.controller_for_actor(actor.actor_id)
    snapshot = session.story_session.encounter_session.command_interface.kernel.snapshot(state)
    attack_ids = _available_choice_option_ids(snapshot.available_choices, 'attacks')
    attacks = _available_attack_profiles(actor, available_attack_ids=attack_ids)
    commands = _available_attack_commands(state, actor, available_attacks=attacks)
    if not commands:
        raise TrainingBatchError('Legal-attack probe could not build a valid attack command.')
    _handle_baseline_input(session, controller_id, commands[0])
    after = session._trajectory_snapshot(controller_id)
    metadata = {
        'success': True,
        'reward_total': 0.0,
        'result_summary': 'Generated a controlled legal attack training example.',
        **after.get('state', {}),
    }
    recorder.record_event(
        record_type='episode_completed',
        source='system',
        runtime_mode=RuntimeMode.COMBAT.value,
        reward_components={},
        metadata=metadata,
    )
    return recorder.path


def _advance_to_next_player_turn(session, *, max_turns: int) -> None:
    assert session.story_session is not None
    for _index in range(max_turns):
        state = session.story_session.state
        active_actor_id = state.active_actor_id
        if active_actor_id is None:
            raise TrainingBatchError('Combat has no active actor.')
        actor = state.actors[active_actor_id]
        if actor.side == ActorSide.PLAYER:
            return
        session.handle_input('dm', f'/endturn {active_actor_id}')
    raise TrainingBatchError('Legal-attack probe could not advance to a player turn.')


def _first_living_enemy(state, actor):
    enemies = [
        candidate for candidate in state.actors.values()
        if candidate.side != actor.side and candidate.current_hit_points > 0
    ]
    if not enemies:
        raise TrainingBatchError('Legal-attack probe has no living enemy target.')
    return sorted(enemies, key=lambda candidate: candidate.actor_id)[0]


def _adjacent_probe_position(state, target) -> GridPosition:
    occupied = {
        (candidate.position.x, candidate.position.y)
        for candidate in state.actors.values()
        if candidate.actor_id != target.actor_id and candidate.current_hit_points > 0
    }
    for x_offset, y_offset in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        x = target.position.x + x_offset
        y = target.position.y + y_offset
        if (x, y) not in occupied:
            return GridPosition(x, y, target.position.z)
    raise TrainingBatchError('Legal-attack probe could not find an adjacent open position.')


def _story_opening_context_snapshot(before: dict[str, Any], *, episode_id: str) -> dict[str, Any]:
    snapshot = json.loads(json.dumps(before, ensure_ascii=False))
    observation = snapshot.get('observation') if isinstance(snapshot.get('observation'), dict) else {}
    context_index = _episode_context_index(episode_id)
    cue = STORY_OPENING_CONTEXT_CUES[context_index % len(STORY_OPENING_CONTEXT_CUES)]
    pressure = STORY_OPENING_CONTEXT_PRESSURES[
        (context_index // len(STORY_OPENING_CONTEXT_CUES)) % len(STORY_OPENING_CONTEXT_PRESSURES)
    ]
    summary_lines = list(observation.get('summary_lines') or [])
    summary_lines.append(f'Opening cue: {cue}')
    summary_lines.append(f'Current party priority: {pressure}.')
    observation['summary_lines'] = summary_lines
    prompt = observation.get('prompt')
    if isinstance(prompt, dict):
        prompt_text = str(prompt.get('text') or '').strip()
        context_text = f'Opening cue: {cue} Priority: {pressure}.'
        prompt['text'] = f'{prompt_text}\n\n{context_text}' if prompt_text else context_text
    snapshot['observation'] = observation
    state = snapshot.get('state') if isinstance(snapshot.get('state'), dict) else {}
    state['story_context_cue'] = cue
    state['story_context_priority'] = pressure
    snapshot['state'] = state
    return snapshot


def _episode_context_index(episode_id: str) -> int:
    suffix = episode_id.rsplit('-', 1)[-1]
    try:
        value = int(suffix)
    except ValueError:
        return 0
    return max(value - 1, 0)


def _story_candidate_after_snapshot(before: dict[str, Any]) -> dict[str, Any]:
    after = json.loads(json.dumps(before, ensure_ascii=False))
    state = after.get('state') if isinstance(after.get('state'), dict) else {}
    state['transcript_count'] = int(state.get('transcript_count') or 0) + 1
    state['event_count'] = int(state.get('event_count') or 0) + 1
    after['state'] = state
    return after


def _record_story_candidate(
    recorder: TrajectoryRecorder,
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    controller_id: str,
    raw_text: str,
    reward_components: dict[str, float],
) -> None:
    recorder.record_turn(
        agent_id=controller_id,
        role='player',
        runtime_mode=RuntimeMode.STORYTELLING.value,
        source='baseline',
        raw_text=raw_text,
        parsed_action={'kind': 'natural_language', 'utterance': raw_text},
        observation=before.get('observation'),
        post_observation=after.get('observation'),
        state_before=before.get('state'),
        state_after=after.get('state'),
        reward_components=reward_components,
        metadata={'reward_total': reward_total(reward_components)},
    )


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
        raw_input = step['input']
        if raw_input.startswith('/create') and session.story_session is not None:
            continue
        if step['type'] == 'command_if_prompt':
            prompt = session.prompt_for_controller(controller_id)
            if prompt is None or prompt.prompt_kind != step.get('prompt_kind'):
                continue
        session.handle_input(controller_id, raw_input)
        if raw_input == '/travel engage':
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


def _finish_first_combat_with_random_legal_actions(session, *, max_combat_turns: int, rng: random.Random) -> None:
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
        controller_id = session.story_session.encounter_session.control_runtime.controller_for_actor(active_actor_id)
        snapshot = session.story_session.encounter_session.command_interface.kernel.snapshot(state)
        commands = _random_legal_combat_commands(
            state,
            actor,
            rng,
            available_choices=snapshot.available_choices,
        )
        if not _try_baseline_commands(session, controller_id, commands):
            _handle_baseline_input(session, controller_id, f'/endturn {active_actor_id}')
            continue
        session._refresh_demo_completion()
        if session.story_session.state.phase == EncounterPhase.COMPLETE:
            break
        if session.story_session.state.active_actor_id == active_actor_id:
            _handle_baseline_input(session, controller_id, f'/endturn {active_actor_id}')
    session._refresh_demo_completion()
    if session._completion_state is None:
        raise TrainingBatchError(f'Random-legal first combat did not complete within {max_combat_turns} turns.')


def _random_legal_combat_commands(
    state,
    actor,
    rng: random.Random,
    *,
    available_choices: dict[str, tuple] | None = None,
) -> tuple[str, ...]:
    if not actor.action_available:
        return (f'/endturn {actor.actor_id}',)
    enemies = [
        candidate for candidate in state.actors.values()
        if candidate.side != actor.side and candidate.current_hit_points > 0
    ]
    allies_to_heal = [
        candidate for candidate in state.actors.values()
        if candidate.side == actor.side
        and candidate.current_hit_points > 0
        and candidate.current_hit_points < candidate.max_hit_points
    ]
    available_attack_ids = _available_choice_option_ids(available_choices, 'attacks')
    available_attacks = _available_attack_profiles(actor, available_attack_ids=available_attack_ids)
    commands: list[str] = []
    for spell_id in sorted(TARGETED_OFFENSE_SPELLS.intersection(actor.spells)):
        spell = actor.spells[spell_id]
        if spell.level > 0:
            continue
        if spell.remaining_uses == 0:
            continue
        for target in enemies:
            if _target_within_range(actor, target, spell.range_ft):
                commands.append(f'/cast {actor.actor_id} {spell_id} {target.actor_id}')
    for spell_id in sorted(TARGETED_HEALING_SPELLS.intersection(actor.spells)):
        spell = actor.spells[spell_id]
        if spell.level > 0:
            continue
        if spell.remaining_uses == 0:
            continue
        for target in allies_to_heal:
            if _target_within_range(actor, target, spell.range_ft):
                commands.append(f'/cast {actor.actor_id} {spell_id} {target.actor_id}')
    for attack in available_attacks:
        for target in enemies:
            if _target_within_attack_range(actor, target, attack):
                commands.append(f'/attack {actor.actor_id} {attack.attack_id} {target.actor_id}')
    if commands:
        rng.shuffle(commands)
        return tuple(commands)
    return (f'/dodge {actor.actor_id}', f'/endturn {actor.actor_id}')


def _available_choice_option_ids(available_choices: dict[str, tuple] | None, group_id: str) -> set[str]:
    if not isinstance(available_choices, dict):
        return set()
    choices = available_choices.get(group_id)
    if not isinstance(choices, (list, tuple)):
        return set()
    return {
        str(getattr(choice, 'option_id', '')).strip()
        for choice in choices
        if str(getattr(choice, 'option_id', '')).strip()
    }


def _available_attack_profiles(actor, *, available_attack_ids: set[str]) -> list:
    attacks = sorted(actor.attacks.values(), key=lambda candidate: candidate.attack_id)
    return [attack for attack in attacks if not available_attack_ids or attack.attack_id in available_attack_ids]


def _available_attack_commands(state, actor, *, available_attacks: list) -> list[str]:
    enemies = [
        candidate for candidate in state.actors.values()
        if candidate.side != actor.side and candidate.current_hit_points > 0
    ]
    return [
        f'/attack {actor.actor_id} {attack.attack_id} {target.actor_id}'
        for attack in available_attacks
        for target in enemies
        if _target_within_attack_range(actor, target, attack)
    ]


def _target_within_attack_range(actor, target, attack) -> bool:
    if attack.range_ft is not None:
        return _grid_distance_ft(actor.position, target.position) <= attack.range_ft
    if attack.reach_ft is not None:
        return _grid_distance_ft(actor.position, target.position) <= attack.reach_ft
    return True


def _target_within_range(actor, target, range_ft: int | None) -> bool:
    if range_ft is None:
        return True
    return _grid_distance_ft(actor.position, target.position) <= range_ft


def _grid_distance_ft(first, second) -> int:
    return max(abs(first.x - second.x), abs(first.y - second.y), abs(first.z - second.z)) * 5


def _try_baseline_commands(session, controller_id: str, commands: tuple[str, ...]) -> bool:
    for command in commands:
        try:
            _handle_baseline_input(session, controller_id, command)
            return True
        except Exception:
            continue
    return False


def _handle_baseline_input(session, controller_id: str, command: str):
    return session._handle_input_with_trajectory(controller_id, command, source='baseline')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run repeated training/evaluation episodes and summarize trajectories.')
    parser.add_argument('--episodes', type=int, default=1, help='Number of episodes to run.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/batches'), help='Directory for batch reports and episode trajectories.')
    parser.add_argument('--scenario-id', default='lmop_first_combat', choices=sorted(SUPPORTED_SCENARIOS), help='Scenario to run.')
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='Environment file used by the demo runtime.')
    parser.add_argument('--base-url', default=None, help='Optional explicit 5etools mirror base URL.')
    parser.add_argument('--max-combat-turns', type=int, default=80, help='Maximum combat turns before an episode is marked failed.')
    parser.add_argument('--policy', choices=sorted(POLICIES), default='scripted', help='Player policy to evaluate after the deterministic setup.')
    parser.add_argument('--baseline-seed', type=int, default=0, help='Seed for deterministic baseline policies such as random-legal.')
    parser.add_argument('--load-characters', type=Path, help='Load confirmed character records from this JSON party file before running episodes.')
    parser.add_argument('--campaign-root', type=Path, help='Optional campaign root to use instead of campaigns/lmop.')
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
        baseline_seed=args.baseline_seed,
        character_load_path=args.load_characters,
        campaign_root=args.campaign_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
