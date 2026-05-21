from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import json
from typing import Any, Iterable

from training.evaluation import load_transition_records


def build_preference_pairs(
    transitions_or_path: str | Path | Iterable[dict[str, Any]],
    *,
    min_reward_gap: float = 0.05,
    max_pairs_per_context: int = 3,
    include_errors: bool = True,
    context_strategy: str = 'exact',
) -> list[dict[str, Any]]:
    if isinstance(transitions_or_path, (str, Path)):
        transitions = load_transition_records(transitions_or_path)
        transition_path = str(Path(transitions_or_path))
    else:
        transitions = list(transitions_or_path)
        transition_path = None

    groups: dict[str, list[dict[str, Any]]] = {}
    for transition in transitions:
        if not include_errors and transition.get('error'):
            continue
        signature = _signature_for_strategy(transition, context_strategy=context_strategy)
        groups.setdefault(signature, []).append(transition)

    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for signature, context_transitions in sorted(groups.items()):
        if len(context_transitions) < 2:
            continue
        sorted_transitions = sorted(
            context_transitions,
            key=lambda item: (_numeric(item.get('reward')), _numeric(item.get('action_reward'))),
            reverse=True,
        )
        context_pair_count = 0
        for chosen in sorted_transitions:
            if context_pair_count >= max_pairs_per_context:
                break
            for rejected in reversed(sorted_transitions):
                if context_pair_count >= max_pairs_per_context:
                    break
                if chosen is rejected:
                    continue
                if str(chosen.get('action') or '') == str(rejected.get('action') or ''):
                    continue
                reward_gap = _numeric(chosen.get('reward')) - _numeric(rejected.get('reward'))
                if reward_gap < min_reward_gap:
                    continue
                pair_key = (signature, str(chosen.get('sample_id')), str(rejected.get('sample_id')))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                pairs.append(
                    _preference_pair(
                        signature,
                        chosen=chosen,
                        rejected=rejected,
                        transition_path=transition_path,
                        context_strategy=context_strategy,
                    )
                )
                context_pair_count += 1
    return pairs


def write_preference_pairs_jsonl(pairs: Iterable[dict[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, ensure_ascii=False, sort_keys=True) + '\n')
    return path


def load_preference_pairs(path: str | Path) -> list[dict[str, Any]]:
    pair_path = Path(path)
    pairs: list[dict[str, Any]] = []
    for line_number, line in enumerate(pair_path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            pair = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid preference-pair JSON on line {line_number} of {pair_path}: {exc}') from exc
        if not isinstance(pair, dict):
            raise ValueError(f'Preference-pair line {line_number} of {pair_path} is not a JSON object.')
        pairs.append(pair)
    return pairs


def context_signature(transition: dict[str, Any]) -> str:
    payload = _context_payload(transition)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest()[:24]


def scene_context_signature(transition: dict[str, Any]) -> str:
    payload = _scene_context_payload(transition)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest()[:24]


def render_preference_prompt(transition: dict[str, Any]) -> str:
    observation = _dict_or_empty(transition.get('observation'))
    state_before = _dict_or_empty(transition.get('state_before'))
    lines: list[str] = [
        f'Agent: {transition.get("agent_id") or ""}',
        f'Actor: {transition.get("acting_actor_id") or state_before.get("active_actor_id") or ""}',
        f'Runtime mode: {transition.get("runtime_mode") or state_before.get("runtime_mode") or ""}',
        f'Scene: {state_before.get("scene_id") or ""}',
        '',
        'Observation:',
    ]
    for summary_line in _string_list(observation.get('summary_lines')):
        lines.append(str(summary_line))
    prompt = observation.get('prompt')
    if isinstance(prompt, dict) and prompt.get('text'):
        lines.extend(('', 'Active prompt:', str(prompt.get('text'))))
    available_actions = transition.get('available_actions')
    if isinstance(available_actions, list) and available_actions:
        lines.extend(('', 'Available actions:'))
        for action in available_actions:
            if not isinstance(action, dict):
                continue
            label = str(action.get('label') or action.get('option_id') or '')
            detail = str(action.get('detail') or '')
            group_id = str(action.get('group_id') or '')
            suffix = f' - {detail}' if detail else ''
            lines.append(f'- {group_id}: {label}{suffix}')
    lines.extend(('', 'Choose one command or concise player action for this situation.'))
    return '\n'.join(lines).strip()


def _preference_pair(
    signature: str,
    *,
    chosen: dict[str, Any],
    rejected: dict[str, Any],
    transition_path: str | None,
    context_strategy: str,
) -> dict[str, Any]:
    reward_gap = _numeric(chosen.get('reward')) - _numeric(rejected.get('reward'))
    return {
        'pair_id': f'{signature}:{chosen.get("sample_id")}:{rejected.get("sample_id")}',
        'context_signature': signature,
        'context_strategy': context_strategy,
        'transition_path': transition_path,
        'prompt': render_preference_prompt(chosen),
        'chosen': str(chosen.get('action') or ''),
        'rejected': str(rejected.get('action') or ''),
        'chosen_reward': _numeric(chosen.get('reward')),
        'rejected_reward': _numeric(rejected.get('reward')),
        'reward_gap': reward_gap,
        'chosen_sample_id': chosen.get('sample_id'),
        'rejected_sample_id': rejected.get('sample_id'),
        'chosen_metadata': _pair_transition_metadata(chosen),
        'rejected_metadata': _pair_transition_metadata(rejected),
        'scenario_id': chosen.get('scenario_id'),
        'runtime_mode': chosen.get('runtime_mode'),
        'acting_actor_id': chosen.get('acting_actor_id'),
    }


def _pair_transition_metadata(transition: dict[str, Any]) -> dict[str, Any]:
    return {
        'agent_id': transition.get('agent_id'),
        'source': transition.get('source'),
        'reward': transition.get('reward'),
        'action_reward': transition.get('action_reward'),
        'terminal_reward': transition.get('terminal_reward'),
        'reward_channels': _dict_or_empty(transition.get('reward_channels')),
        'error': transition.get('error'),
        'conversation_id': transition.get('conversation_id'),
        'conversation_label': transition.get('conversation_label'),
        'behavior_profile': transition.get('behavior_profile'),
    }


def _context_payload(transition: dict[str, Any]) -> dict[str, Any]:
    observation = _dict_or_empty(transition.get('observation'))
    state_before = _dict_or_empty(transition.get('state_before'))
    return {
        'scenario_id': transition.get('scenario_id'),
        'runtime_mode': transition.get('runtime_mode') or state_before.get('runtime_mode'),
        'acting_actor_id': transition.get('acting_actor_id') or state_before.get('active_actor_id'),
        'scene_id': state_before.get('scene_id'),
        'location_id': state_before.get('location_id'),
        'round_number': state_before.get('round_number'),
        'encounter_phase': state_before.get('encounter_phase'),
        'active_actor_id': state_before.get('active_actor_id'),
        'summary_lines': _string_list(observation.get('summary_lines')),
        'prompt': _prompt_payload(observation.get('prompt')),
        'available_actions': _available_action_payload(transition.get('available_actions')),
    }


def _scene_context_payload(transition: dict[str, Any]) -> dict[str, Any]:
    observation = _dict_or_empty(transition.get('observation'))
    state_before = _dict_or_empty(transition.get('state_before'))
    return {
        'scenario_id': transition.get('scenario_id'),
        'runtime_mode': transition.get('runtime_mode') or state_before.get('runtime_mode'),
        'scene_id': state_before.get('scene_id'),
        'location_id': state_before.get('location_id'),
        'agent_id': transition.get('agent_id'),
        'acting_actor_id': transition.get('acting_actor_id') or state_before.get('active_actor_id'),
        'prompt': _prompt_payload(observation.get('prompt')),
        'available_actions': _available_action_payload(transition.get('available_actions')),
    }


def _signature_for_strategy(transition: dict[str, Any], *, context_strategy: str) -> str:
    if context_strategy == 'exact':
        return context_signature(transition)
    if context_strategy == 'scene':
        return scene_context_signature(transition)
    raise ValueError(f'Unsupported preference context_strategy: {context_strategy}')


def _prompt_payload(prompt: Any) -> dict[str, Any] | None:
    if not isinstance(prompt, dict):
        return None
    return {
        'prompt_kind': prompt.get('prompt_kind'),
        'text': prompt.get('text'),
    }


def _available_action_payload(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    actions: list[dict[str, str]] = []
    for action in value:
        if not isinstance(action, dict):
            continue
        actions.append(
            {
                'group_id': str(action.get('group_id') or ''),
                'option_id': str(action.get('option_id') or ''),
                'label': str(action.get('label') or ''),
                'detail': str(action.get('detail') or ''),
            }
        )
    return actions


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _numeric(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0
