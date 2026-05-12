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
