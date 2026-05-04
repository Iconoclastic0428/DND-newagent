# Blur

## Source of Truth
- Normalized source id: `XPHB:spell:blur`
- Official source book/tag: `XPHB`
- Level/class/feature category: level-2 spell
- Local normalized data: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`

## Implementation Family
- Exact mechanic family: self-only concentration defense buff.
- Why this family is correct: the local text makes the caster blurred for 1 minute and gives attackers disadvantage unless they can perceive the target through blindsight or truesight.
- Shared runtime primitives reused: `StartActiveEffectDef`, sight-reliant incoming attack disadvantage, attacker blindsight/truesight radius checks.

## Runtime Behavior
- Action economy usage: action.
- Resource consumption: spell slot handled by the shared spell-cast path.
- Targeting model: self only.
- Duration/concentration model: concentration, up to 1 minute.
- Active-effect lifecycle: one concentration effect on the caster marks attacks against the target as sight-reliant disadvantage unless the attacker has qualifying nonvisual precision.
- Battlefield integration: attack modifier resolution checks attacker senses against the target's position.
- State mutations: none beyond the active defensive effect and concentration.
- Observer/social implications if any: none beyond ordinary visible spellcasting.

## Item-Specific Edge Cases
- Blindsight or truesight inside range bypass the disadvantage completely.
- The effect is distinct from invisibility and does not hide the target.
- Heavy obscurement and other normal visibility modifiers still stack through the usual attack-modifier path.

## Test Matrix
- Smoke registration and metadata test.
- Core execution tests for disadvantage on incoming attacks.
- Edge-case tests for blindsight and truesight bypass plus concentration replacement.
- Replay/idempotency relevance: repeated casting and duration replacement are verified through authoritative events.

## Dependencies
- Shared primitives required: sight-reliant incoming attack disadvantage plus attacker blindsight/truesight radii.
- Unresolved blockers: none for the local XPHB text.
