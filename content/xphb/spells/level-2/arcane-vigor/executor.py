from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import (
    CapabilityDefinition,
    CapabilityKind,
    HealingBonusSource,
    SpendHitDiceHealingEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)


SPELL_NAME = 'Arcane Vigor'
SPELL_SLUG = 'arcane-vigor'


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
        action_cost='bonus',
        targeting=TargetingSpec(
            selection_kind=TargetSelectionKind.SELF,
            affinity=TargetAffinity.SELF_ONLY,
        ),
        effect=SpendHitDiceHealingEffectDef(
            count_parameter_key='count',
            minimum_count=1,
            maximum_count=2,
            bonus_source=HealingBonusSource.ACTOR_SPELLCASTING_MODIFIER,
            slot_level_parameter_key='slot-level',
            base_slot_level=2,
            bonus_maximum_count_per_slot_level=1,
        ),
    )
