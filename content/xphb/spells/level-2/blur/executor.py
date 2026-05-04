from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import ActiveEffectDefinition, CapabilityDefinition, CapabilityKind, DurationAnchor, DurationSpec, EffectDurationType, StartActiveEffectDef, TargetSelectionKind, TargetingSpec


SPELL_NAME = 'Blur'
SPELL_SLUG = 'blur'


def _canonical_name(raw_spell: Mapping[str, object]) -> str:
    english_name = raw_spell.get('ENG_name')
    if isinstance(english_name, str) and english_name.strip():
        return english_name.strip()
    raw_name = raw_spell.get('name')
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    return ''


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
        action_cost='action',
        targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF),
        effect=StartActiveEffectDef(
            active_effect=ActiveEffectDefinition(
                name=SPELL_NAME,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                concentration=True,
                replace_existing_same_name_from_source=True,
                attackers_rely_on_sight_have_disadvantage=True,
            )
        ),
    )
