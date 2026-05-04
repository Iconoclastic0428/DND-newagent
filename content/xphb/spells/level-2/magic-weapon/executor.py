from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import CapabilityDefinition, CapabilityKind, ChosenWeaponEnchantmentEffectDef, DurationAnchor, DurationSpec, EffectDurationType, TargetAffinity, TargetSelectionKind, TargetingSpec


SPELL_NAME = 'Magic Weapon'
SPELL_SLUG = 'magic-weapon'


def _canonical_name(raw_spell: Mapping[str, object]) -> str:
    return str(raw_spell.get('ENG_name') or raw_spell.get('name') or '').strip()


def build_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition | None:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return None
    if _canonical_name(raw_spell) != SPELL_NAME:
        return None
    return CapabilityDefinition(
        capability_id=SPELL_SLUG,
        name=SPELL_NAME,
        kind=CapabilityKind.SPELL,
        source='XPHB',
        action_cost='bonus-action',
        targeting=TargetingSpec(
            selection_kind=TargetSelectionKind.CREATURE,
            range_ft=5,
            affinity=TargetAffinity.ANY,
            requires_target_to_be_seen=True,
            max_targets=1,
        ),
        effect=ChosenWeaponEnchantmentEffectDef(
            name=SPELL_NAME,
            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
            concentration=False,
            item_parameter_key='item',
            requires_weapon=True,
            requires_melee=False,
            requires_held=False,
            enchanted_attack_bonus=1,
            enchanted_damage_bonus=1,
            slot_level_parameter_key='slot-level',
            base_slot_level=2,
            scaled_enchanted_bonus_tiers=((3, 2), (6, 3)),
            select_item_from_target_actor=True,
        ),
    )
