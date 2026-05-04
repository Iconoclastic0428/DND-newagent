# Darkvision

## Source of Truth
- Normalized source id: `XPHB:spell:darkvision`
- Official source book/tag: `XPHB`
- Level/class/feature category: level-2 spell
- Local normalized data: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`

## Implementation Family
- Exact mechanic family: touch-applied vision buff.
- Why this family is correct: the local text grants 150-foot darkvision to the touched willing creature for 8 hours.
- Shared runtime primitives reused: `StartActiveEffectDef`, actor-scoped darkvision radius in the visibility system.

## Runtime Behavior
- Action economy usage: action.
- Resource consumption: spell slot handled by the shared spell-cast path.
- Targeting model: touched creature.
- Duration/concentration model: 8 hours, no concentration.
- Active-effect lifecycle: one persistent active effect grants a 150-foot darkvision radius.
- Battlefield integration: visibility in darkness becomes observer-relative through the updated visibility model.
- State mutations: sets the target actor darkvision radius while the effect remains active.
- Observer/social implications if any: none beyond ordinary visible spellcasting.

## Item-Specific Edge Cases
- The effect does not bypass heavy obscurement.
- The effect is observer-relative; it changes what the affected target can see, not the battlefield lighting itself.
- Existing brighter light continues to work normally; darkvision only changes darkness handling.

## Test Matrix
- Smoke registration and metadata test.
- Core execution tests for radius application and visibility in darkness.
- Edge-case tests for out-of-radius darkness and heavy obscurement.
- Replay/idempotency relevance: duration refresh and effect replacement are verified through repeated casting.

## Dependencies
- Shared primitives required: actor-scoped darkvision radius in the visibility system.
- Unresolved blockers: none for the local XPHB text.
