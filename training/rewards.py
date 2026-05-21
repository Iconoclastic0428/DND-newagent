from __future__ import annotations

from collections import Counter
import re
from typing import Any


_WORD_RE = re.compile(r"[a-z0-9']+")
_REPETITION_STOPWORDS = {
    'a',
    'an',
    'and',
    'are',
    'as',
    'at',
    'be',
    'by',
    'for',
    'from',
    'i',
    'in',
    'is',
    'it',
    'of',
    'on',
    'or',
    'our',
    'that',
    'the',
    'this',
    'to',
    'we',
    'with',
    'you',
    'your',
}


def action_reward_components(
    *,
    error: str | None,
    state_before: dict[str, Any] | None,
    state_after: dict[str, Any] | None,
    raw_text: str | None = None,
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
    _add_count_delta_reward(
        components,
        before,
        after,
        field_name='scene_goal_completion_count',
        component_name='scene_goal_completed',
        scale=0.35,
    )
    _add_count_delta_reward(
        components,
        before,
        after,
        field_name='hidden_subgoal_completion_count',
        component_name='hidden_subgoal_completed',
        scale=0.35,
    )
    _add_count_delta_reward(
        components,
        before,
        after,
        field_name='known_discovery_count',
        component_name='discovery_made',
        scale=0.12,
    )
    _add_count_delta_reward(
        components,
        before,
        after,
        field_name='social_revealed_topic_count',
        component_name='social_topic_revealed',
        scale=0.08,
    )
    _add_count_reduction_reward(
        components,
        before,
        after,
        field_name='party_goal_count',
        component_name='party_goal_resolved',
        scale=0.25,
    )
    _add_count_reduction_reward(
        components,
        before,
        after,
        field_name='open_loop_count',
        component_name='open_loop_resolved',
        scale=0.2,
    )
    if raw_text is not None:
        repetitive_words = _repetitive_word_penalty(raw_text)
        if repetitive_words:
            components['repetitive_words'] = repetitive_words
        repetitive_action = _repetitive_action_penalty(raw_text, before)
        if repetitive_action:
            components['repetitive_action'] = repetitive_action
    if _is_stalled_story_scene_turn(before, after):
        components['stalled_scene_turn'] = -0.06
    if before.get('runtime_mode') == 'combat' or after.get('runtime_mode') == 'combat':
        components['combat_step_cost'] = -0.04
    monster_hp_before = _numeric(before.get('monster_hp_current'))
    monster_hp_after = _numeric(after.get('monster_hp_current'))
    monster_damage = max(0.0, monster_hp_before - monster_hp_after)
    if monster_damage > 0:
        components['enemy_damage'] = monster_damage * 0.03
    party_hp_before = _numeric(before.get('party_hp_current'))
    party_hp_after = _numeric(after.get('party_hp_current'))
    party_healing = max(0.0, party_hp_after - party_hp_before)
    if party_healing > 0:
        components['ally_healing'] = party_healing * 0.03
    party_damage = max(0.0, party_hp_before - party_hp_after)
    if party_damage > 0:
        components['party_damage_taken'] = party_damage * -0.03
    enemy_healing = max(0.0, monster_hp_after - monster_hp_before)
    if enemy_healing > 0:
        components['enemy_healing'] = enemy_healing * -0.03
    party_temp_hp_before = _numeric(before.get('party_temp_hp'))
    party_temp_hp_after = _numeric(after.get('party_temp_hp'))
    party_temp_hp_gained = max(0.0, party_temp_hp_after - party_temp_hp_before)
    if party_temp_hp_gained > 0:
        components['ally_temp_hp_gained'] = party_temp_hp_gained * 0.02
    enemy_temp_hp_before = _numeric(before.get('monster_temp_hp'))
    enemy_temp_hp_after = _numeric(after.get('monster_temp_hp'))
    enemy_temp_hp_gained = max(0.0, enemy_temp_hp_after - enemy_temp_hp_before)
    if enemy_temp_hp_gained > 0:
        components['enemy_temp_hp_gained'] = enemy_temp_hp_gained * -0.02
    living_monsters_before = _numeric(before.get('living_monster_count'))
    living_monsters_after = _numeric(after.get('living_monster_count'))
    enemy_defeats = max(0.0, living_monsters_before - living_monsters_after)
    if enemy_defeats > 0:
        components['enemy_defeated'] = enemy_defeats * 0.25
    living_party_before = _numeric(before.get('living_party_count'))
    living_party_after = _numeric(after.get('living_party_count'))
    ally_defeats = max(0.0, living_party_before - living_party_after)
    if ally_defeats > 0:
        components['ally_defeated'] = ally_defeats * -0.5
    _add_delta_reward(
        components,
        before,
        after,
        field_name='party_buff_effect_count',
        component_name='ally_buff_applied',
        scale=0.1,
    )
    _add_delta_reward(
        components,
        before,
        after,
        field_name='party_help_effect_count',
        component_name='ally_help_provided',
        scale=0.08,
    )
    _add_delta_reward(
        components,
        before,
        after,
        field_name='monster_buff_effect_count',
        component_name='enemy_buff_applied',
        scale=-0.1,
    )
    _add_delta_reward(
        components,
        before,
        after,
        field_name='monster_help_effect_count',
        component_name='enemy_help_provided',
        scale=-0.08,
    )
    for field_name, component_name, scale in (
        ('monster_action_debuff_count', 'enemy_action_debuff_applied', 0.25),
        ('monster_control_debuff_count', 'enemy_control_applied', 0.2),
        ('monster_accuracy_debuff_count', 'enemy_accuracy_debuff_applied', 0.12),
        ('monster_defense_debuff_count', 'enemy_defense_debuff_applied', 0.12),
        ('monster_mobility_debuff_count', 'enemy_mobility_debuff_applied', 0.12),
        ('monster_general_debuff_count', 'enemy_general_debuff_applied', 0.08),
        ('party_action_debuff_count', 'ally_action_debuffed', -0.25),
        ('party_control_debuff_count', 'ally_control_debuffed', -0.2),
        ('party_accuracy_debuff_count', 'ally_accuracy_debuffed', -0.12),
        ('party_defense_debuff_count', 'ally_defense_debuffed', -0.12),
        ('party_mobility_debuff_count', 'ally_mobility_debuffed', -0.12),
        ('party_general_debuff_count', 'ally_general_debuffed', -0.08),
    ):
        _add_delta_reward(
            components,
            before,
            after,
            field_name=field_name,
            component_name=component_name,
            scale=scale,
        )
    return components


def terminal_reward_components(
    *,
    success: bool,
    party_hp_current: int | float | None = None,
    party_hp_max: int | float | None = None,
    round_number: int | float | None = None,
) -> dict[str, float]:
    if success:
        components = {
            'episode_success': 1.0,
        }
        max_hp = _numeric(party_hp_max)
        if max_hp > 0:
            components['party_survival'] = max(0.0, _numeric(party_hp_current)) / max_hp
        rounds = max(1.0, _numeric(round_number))
        components['encounter_efficiency'] = min(0.25, 0.25 / rounds)
        return components
    components = {
        'episode_failure': -1.0,
    }
    max_hp = _numeric(party_hp_max)
    if max_hp > 0:
        components['party_survival'] = max(0.0, _numeric(party_hp_current)) / max_hp
    return components


def reward_total(components: dict[str, float] | None) -> float:
    return float(sum((components or {}).values()))


def _numeric(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _add_count_delta_reward(
    components: dict[str, float],
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    field_name: str,
    component_name: str,
    scale: float,
) -> None:
    delta = max(0.0, _numeric(after.get(field_name)) - _numeric(before.get(field_name)))
    if delta > 0:
        components[component_name] = delta * scale


def _add_count_reduction_reward(
    components: dict[str, float],
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    field_name: str,
    component_name: str,
    scale: float,
) -> None:
    delta = max(0.0, _numeric(before.get(field_name)) - _numeric(after.get(field_name)))
    if delta > 0:
        components[component_name] = delta * scale


def _is_stalled_story_scene_turn(before: dict[str, Any], after: dict[str, Any]) -> bool:
    if before.get('runtime_mode') != 'storytelling' or after.get('runtime_mode') != 'storytelling':
        return False
    if before.get('scene_id') != after.get('scene_id'):
        return False
    progress_delta = (
        max(0.0, _numeric(after.get('scene_goal_completion_count')) - _numeric(before.get('scene_goal_completion_count')))
        + max(0.0, _numeric(after.get('hidden_subgoal_completion_count')) - _numeric(before.get('hidden_subgoal_completion_count')))
        + max(0.0, _numeric(after.get('known_discovery_count')) - _numeric(before.get('known_discovery_count')))
        + max(0.0, _numeric(after.get('social_revealed_topic_count')) - _numeric(before.get('social_revealed_topic_count')))
        + max(0.0, _numeric(before.get('party_goal_count')) - _numeric(after.get('party_goal_count')))
        + max(0.0, _numeric(before.get('open_loop_count')) - _numeric(after.get('open_loop_count')))
    )
    return progress_delta <= 0


def _repetitive_word_penalty(raw_text: str) -> float:
    tokens = _content_tokens(raw_text)
    if len(tokens) < 8:
        return 0.0
    counts = Counter(tokens)
    excessive_repetitions = sum(max(0, count - 3) for count in counts.values())
    repeated_token_share = sum(count for count in counts.values() if count > 1) / len(tokens)
    phrase_repeats = _repeated_ngram_count(tokens, n=3)
    penalty = 0.0
    if excessive_repetitions:
        penalty += 0.025 * excessive_repetitions
    if repeated_token_share >= 0.55:
        penalty += 0.04
    if phrase_repeats:
        penalty += 0.04 * phrase_repeats
    return -min(0.18, penalty) if penalty else 0.0


def _repeated_ngram_count(tokens: list[str], *, n: int) -> int:
    if len(tokens) < n * 2:
        return 0
    grams = Counter(tuple(tokens[index:index + n]) for index in range(0, len(tokens) - n + 1))
    return sum(count - 1 for count in grams.values() if count > 1)


def _repetitive_action_penalty(raw_text: str, state_before: dict[str, Any]) -> float:
    raw_tokens = set(_content_tokens(raw_text))
    normalized_raw = _normalize_action_text(raw_text)
    if not raw_tokens or not normalized_raw:
        return 0.0
    recent_texts = state_before.get('recent_player_input_texts') or state_before.get('recent_player_action_texts') or ()
    if not isinstance(recent_texts, (list, tuple)):
        return 0.0
    worst_penalty = 0.0
    for recent in list(recent_texts)[-8:]:
        if not isinstance(recent, str):
            continue
        normalized_recent = _normalize_action_text(recent)
        if normalized_recent and normalized_recent == normalized_raw:
            worst_penalty = min(worst_penalty, -0.22)
            continue
        recent_tokens = set(_content_tokens(recent))
        if not recent_tokens:
            continue
        similarity = len(raw_tokens & recent_tokens) / len(raw_tokens | recent_tokens)
        if similarity >= 0.85:
            worst_penalty = min(worst_penalty, -0.16)
        elif similarity >= 0.7:
            worst_penalty = min(worst_penalty, -0.1)
    return worst_penalty


def _content_tokens(text: str) -> list[str]:
    return [
        token
        for token in _WORD_RE.findall(text.lower())
        if len(token) > 2 and token not in _REPETITION_STOPWORDS
    ]


def _normalize_action_text(text: str) -> str:
    return ' '.join(_content_tokens(text))


def _add_delta_reward(
    components: dict[str, float],
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    field_name: str,
    component_name: str,
    scale: float,
) -> None:
    delta = max(0.0, _numeric(after.get(field_name)) - _numeric(before.get(field_name)))
    if delta > 0:
        components[component_name] = delta * scale
