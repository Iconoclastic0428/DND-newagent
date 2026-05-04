# Hold Person

## Source of Truth
- Normalized source id: `XPHB:spell:hold-person`
- Official source book/tag: `XPHB`
- Level/class/feature category: level-2 spell
- Local normalized data: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`

## Implementation Family
- Exact mechanic family: save-gated concentration control effect with repeat saves.
- Why this family is correct: the local text is a WIS save against a humanoid target, inflicts `Paralyzed`, repeats the save at the end of each target turn, and adds humanoid targets on higher slots.
- Shared runtime primitives reused: `SaveGateEffect`, `StartActiveEffectDef`, `ParameterizedTargetCountGateEffectDef`, grouped split-target concentration anchor handling.

## Runtime Behavior
- Action economy usage: action.
- Resource consumption: spell slot handled by the shared spell-cast path.
- Targeting model: visible humanoid within 60 feet; higher-slot multi-target via `--targets` plus `--slot-level`.
- Duration/concentration model: concentration, up to 1 minute.
- Active-effect lifecycle: single-target casts use one concentration effect; multi-target casts create one concentration anchor plus one child effect per failed humanoid target so repeat saves clear independently.
- Battlefield integration: creature-type filtering is authoritative and enforced at target validation time.
- State mutations: applies `Paralyzed` to failed targets.
- Observer/social implications if any: none beyond ordinary visible spellcasting.

## Item-Specific Edge Cases
- Only humanoids are legal targets.
- Higher-slot extra targets are enforced by the target-count gate.
- Multi-target exactness requires grouped start-effect handling so one failed target does not replace concentration for another.

## Test Matrix
- Smoke registration and metadata test.
- Core execution tests for paralyzed application and end-of-turn repeat save removal.
- Edge-case tests for creature-type rejection, higher-slot multi-target casts, and independent per-target expiry.
- Replay/idempotency relevance: repeat-save cleanup is verified via the normal timing queue.

## Dependencies
- Shared primitives required: grouped split-target concentration anchor handling for started active effects.
- Unresolved blockers: none for the local XPHB text.
