# Melf''s Acid Arrow

## Source of Truth
- normalized source id: XPHB:spell:melf-s-acid-arrow
- official source book/tag: XPHB
- level/class/feature category: spell, level 2
- links/refs to normalized local data: D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json

## Implementation Family
- exact mechanic family: $(System.Collections.Hashtable.Family)
- why that family is correct: the local XPHB text maps directly onto this deterministic runtime pattern without requiring DM-only interpretation.
- which shared runtime primitives it reuses: AttackRollGateEffect plus ParameterizedDamageEffectDef and ParameterizedActiveEffectDef.

## Runtime Behavior
- action economy usage: $(System.Collections.Hashtable.ActionCost)
- resource consumption: consumes the normal spellcasting resource path for a 2nd-level spell cast.
- targeting model: range $(System.Collections.Hashtable.Range) feet using the executor-defined typed targeting rules.
- duration/concentration model: concentration=$(System.Collections.Hashtable.Concentration.ToString().ToLower())
- active-effect lifecycle: Makes a ranged spell attack that deals initial acid damage on a hit, half initial damage on a miss, and delayed acid damage at the end of the target's next turn on a hit.
- battlefield integration: uses the shared encounter legality and active-effect systems.
- state mutations: authoritative through typed capability execution only.
- observer/social implications if any: no frontend or DM projection mutation outside the normal spellcast event path.

## Item-Specific Edge Cases
- Higher-level slots scale both the initial and delayed damage packages by 1d4 per slot level above 2.
- the runtime rejects illegal targets, missing required parameters, and unsupported slot/target combinations instead of guessing.
- stacking or exclusivity rules follow the shared active-effect replacement semantics for the item family.
- ambiguity-resolution notes: this item is only marked implemented because the exact local text maps cleanly to deterministic runtime behavior.

## Test Matrix
- smoke registration test: the item definition and registry mark the spell deterministic.
- core execution test(s): the per-item spell suite exercises the primary cast path.
- edge-case test(s): the per-item spell suite covers invalid parameters or exact local-text boundaries.
- replay/idempotency test if relevant: replacement or delayed-resolution behavior is covered where the item requires it.

## Dependencies
- shared primitives required: AttackRollGateEffect plus ParameterizedDamageEffectDef and ParameterizedActiveEffectDef.
- unresolved blockers if any: none for this deterministic slice.
