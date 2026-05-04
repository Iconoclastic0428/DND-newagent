# Blindness/Deafness

## Source of Truth
- Normalized source id: `XPHB:spell:blindness-deafness`
- Official source book/tag: `XPHB`
- Level/class/feature category: level-2 spell
- Local normalized data: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`

## Implementation Family
- Exact mechanic family: save-gated per-target condition effect with repeat saves.
- Why this family is correct: the local text is a CON save, a caster-chosen blinded/deafened condition, 1-minute duration, repeat CON save at the end of each affected target's turn, and extra targets on higher slots.
- Shared runtime primitives reused: `SaveGateEffect`, `ParameterizedConditionEffectDef`, `ParameterizedTargetCountGateEffectDef`, grouped split-target active effects.

## Runtime Behavior
- Action economy usage: action.
- Resource consumption: spell slot handled by the shared spell-cast path.
- Targeting model: visible creature within 120 feet; multi-target via `--targets` plus `--slot-level`.
- Duration/concentration model: 1 minute, not concentration.
- Active-effect lifecycle: each failed target gets its own active effect so end-of-turn save success clears only that target.
- Battlefield integration: standard visible creature targeting.
- State mutations: applies `Blinded` or `Deafened` to failed targets.
- Observer/social implications if any: none beyond ordinary visible spellcasting.

## Item-Specific Edge Cases
- The caster must provide `--condition blinded` or `--condition deafened`; the engine does not guess.
- Higher-slot extra targets are enforced by a target-count gate.
- Because the local text is not concentration, the split-target helper must not create a concentration anchor.

## Test Matrix
- Smoke registration and metadata test.
- Core execution tests for blinded and deafened modes.
- Edge-case tests for low-slot overtarget rejection and independent per-target expiry.
- Replay/idempotency relevance: repeat-save resolution is verified through the authoritative turn-boundary flow.

## Dependencies
- Shared primitives required: grouped split-target active-effect application for non-concentration repeat-save effects.
- Unresolved blockers: none for the local XPHB text.
