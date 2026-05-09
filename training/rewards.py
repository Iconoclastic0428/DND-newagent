from __future__ import annotations

from typing import Any


def action_reward_components(
    *,
    error: str | None,
    state_before: dict[str, Any] | None,
    state_after: dict[str, Any] | None,
) -> dict[str, float]:
    if error is not None:
        return {
            'invalid_action': -1.0,
        }
    components: dict[str, float] = {
        'valid_action': 0.01,
    }
    before = state_before or {}
    after = state_after or {}
    if _numeric(after.get('transcript_count')) > _numeric(before.get('transcript_count')):
        components['story_progress'] = 0.05
    if _numeric(after.get('event_count')) > _numeric(before.get('event_count')):
        components['state_progress'] = 0.02
    if before.get('runtime_mode') != after.get('runtime_mode'):
        components['mode_progress'] = 0.1
    return components


def terminal_reward_components(*, success: bool) -> dict[str, float]:
    if success:
        return {
            'episode_success': 1.0,
        }
    return {
        'episode_failure': -1.0,
    }


def reward_total(components: dict[str, float] | None) -> float:
    return float(sum((components or {}).values()))


def _numeric(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
