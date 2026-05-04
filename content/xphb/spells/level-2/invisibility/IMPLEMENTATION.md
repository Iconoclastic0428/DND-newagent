# Invisibility

## Source of Truth
- Normalized source id: `XPHB:spell:invisibility`
- Official source book/tag: `XPHB`
- Level/class/feature category: level-2 spell
- Local normalized data: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`

## Implementation Family
- Exact mechanic family: touch concentration buff with per-target early termination.
- Why this family is correct: the local text grants `Invisible` for up to 1 hour and ends early for each target that attacks, deals damage, or casts a spell; higher slots add extra targets.
- Shared runtime primitives reused: `StartActiveEffectDef`, `ParameterizedTargetCountGateEffectDef`, grouped split-target concentration anchor handling, spell-cast and damage-trigger effect teardown hooks.

## Runtime Behavior
- Action economy usage: action.
- Resource consumption: spell slot handled by the shared spell-cast path.
- Targeting model: touched creature; higher-slot multi-target via `--targets` plus `--slot-level`.
- Duration/concentration model: concentration, up to 1 hour.
- Active-effect lifecycle: multi-target casts create one concentration anchor plus one child effect per target. Each child ends independently when that target attacks, deals damage, or casts any spell.
- Battlefield integration: touch-range validation for each target.
- State mutations: applies `Invisible` to each affected target.
- Observer/social implications if any: visibility is reconciled through the authoritative visibility system when the condition starts or ends.

## Item-Specific Edge Cases
- The local text says any spell cast ends the effect, not only harmful spells; the implementation therefore uses a dedicated spell-cast teardown hook.
- Damage dealt by the target also ends the effect, which is distinct from taking damage.
- Multi-target exactness requires one concentration anchor and independent child effects.

## Test Matrix
- Smoke registration and metadata test.
- Core execution tests for condition application and early termination on spell cast.
- Edge-case tests for higher-slot multi-target casts, overtarget rejection, and one target ending while another remains invisible.
- Replay/idempotency relevance: early termination is verified through normal attack, damage, and spell-cast event flow.

## Dependencies
- Shared primitives required: per-target spell-cast and damage-dealt teardown hooks plus grouped split-target concentration handling.
- Unresolved blockers: none for the local XPHB text.
