# Enhance Ability

## Source of Truth
- Normalized source id: `XPHB:spell:enhance-ability`
- Official source book/tag: `XPHB`
- Level/class/feature category: level-2 spell
- Local normalized data: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`

## Implementation Family
- Exact mechanic family: touch concentration buff with chosen ability-check advantage.
- Why this family is correct: the local text grants advantage on checks using one chosen ability, and higher slots add targets that can each receive a different chosen ability.
- Shared runtime primitives reused: `ChosenAbilityCheckAdvantageEffectDef`, `ParameterizedTargetCountGateEffectDef`, per-target ability metadata on one concentration effect.

## Runtime Behavior
- Action economy usage: action.
- Resource consumption: spell slot handled by the shared spell-cast path.
- Targeting model: touched ally target; higher-slot multi-target casts use `--targets` and `--target-abilities actor-id:ABILITY`.
- Duration/concentration model: concentration, up to 1 hour.
- Active-effect lifecycle: one concentration effect carries either a single chosen ability or per-target chosen-ability metadata.
- Battlefield integration: touch-range validation for each target.
- State mutations: grants advantage on ability checks for the chosen ability per affected target.
- Observer/social implications if any: none beyond ordinary visible spellcasting.

## Item-Specific Edge Cases
- Single-target casts require `--ability`.
- Multi-target casts require `--target-abilities` entries for every target.
- The local mirror text for this repo does not include the old temp-HP rider, so the implementation does not invent it.

## Test Matrix
- Smoke registration and metadata test.
- Core execution tests for single-target chosen ability application.
- Edge-case tests for case-insensitive abilities, higher-slot target-count gating, and per-target ability mappings.
- Replay/idempotency relevance: concentration and metadata application are verified through authoritative event application.

## Dependencies
- Shared primitives required: per-target ability metadata in actor effect recomputation.
- Unresolved blockers: none for the local XPHB text.
