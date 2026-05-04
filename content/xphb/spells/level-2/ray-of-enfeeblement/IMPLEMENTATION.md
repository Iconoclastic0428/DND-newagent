# Ray of Enfeeblement

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/ray-of-enfeeblement`
- Canonical runtime item record: `XPHB:spell:ray-of-enfeeblement`

## Implementation Family
- save-plus-repeatable-debuff

## Runtime Behavior
- Blocked: Exact Ray of Enfeeblement needs a shared active-effect primitive for ability-keyed D20-test disadvantage across attack rolls, ability checks, and saving throws, plus a persistent damage-roll penalty modifier applied to every rolled damage component from the affected source.
- Cast syntax: `/cast player-1 ray-of-enfeeblement monster-mage-1`
- Local summary: Exact local XPHB Ray of Enfeeblement applies a Constitution save rider. On success, the target has disadvantage on its next attack roll until your next turn starts. On failure, the target has disadvantage on Strength-based D20 tests and takes a `1d8` penalty on all damage rolls until it saves at the end of its turns.

## Item-Specific Edge Cases
- The success rider is not concentration and expires at the start of the caster's next turn after affecting only the next attack roll.
- The failure rider is concentration-backed, repeats the Constitution save at the end of each target turn, and must penalize Strength-based attack rolls, ability checks, and saving throws without spilling onto non-Strength rolls.
- The `1d8` reduction applies to each rolled damage component from the affected source, not to fixed damage that is not rolled.

## Test Matrix
- `definition.json` mirrors the exact blocker classification and local-text summary.
- `registry.json` records the blocked runtime status for the item directory.
- `tests/test_ray_of_enfeeblement.py` verifies the blocker contract until the shared primitive exists.

## Dependencies
- Exact primitive still needed: a reusable active-effect modifier that can impose ability-keyed D20-test disadvantage across attack rolls, ability checks, and saving throws, plus a reusable outgoing damage-roll penalty modifier for the affected source.
- Current executor status: intentionally returns `None` so the runtime does not pretend the spell is deterministic before the shared primitive exists.
