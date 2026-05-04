from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import (
    ActiveEffectDefinition,
    CapabilityDefinition,
    CapabilityKind,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    StartActiveEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)


SPELL_NAME = 'Barkskin'
SPELL_SLUG = 'barkskin'


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
            selection_kind=TargetSelectionKind.CREATURE,
            range_ft=5,
            affinity=TargetAffinity.ALLY,
            requires_target_to_be_seen=False,
            max_targets=1,
        ),
        effect=StartActiveEffectDef(
            active_effect=ActiveEffectDefinition(
                name=SPELL_NAME,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                armor_class_minimum=17,
            )
        ),
    )
