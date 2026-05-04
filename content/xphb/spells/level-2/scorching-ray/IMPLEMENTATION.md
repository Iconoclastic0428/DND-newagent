# Scorching Ray

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/scorching-ray`
- Canonical runtime item record: `XPHB:spell:scorching-ray`

## Implementation Family
- multi-ray-attack

## Runtime Behavior
- Blocked: Exact Scorching Ray needs a shared repeated spell-attack consumer that resolves an ordered list of duplicate or split per-ray targets, rolls one ranged spell attack per ray, and scales the ray count by slot level inside a single cast.
- Cast syntax: `/cast player-1 scorching-ray --targets monster-mage-1,monster-mage-1,monster-skeleton-1`
- Local summary: Exact local XPHB Scorching Ray fires three rays, allows all rays on one target or split targeting across multiple creatures, and requires a separate ranged spell attack roll for each ray. Higher slots add one ray per slot level above 2.

## Item-Specific Edge Cases
- The shared consumer must preserve ordered duplicate or split per-ray targets so all three base rays can be directed at the same creature without collapsing target ids.
- The spell requires one attack roll per ray rather than one attack roll followed by area or chain logic.
- Upcasting increases ray count, not damage per hit, so slot scaling must add attacks while preserving the per-ray `2d6` fire damage.

## Test Matrix
- `definition.json` mirrors the exact blocker classification and local-text summary.
- `registry.json` records the blocked runtime status for the item directory.
- `tests/test_scorching_ray.py` verifies the blocker contract until the shared primitive exists.

## Dependencies
- Exact primitive still needed: a reusable multi-attack spell effect that consumes an ordered per-ray target list, permits duplicate targets, resolves one spell attack per ray inside a single cast, and adds one extra ray per slot level above 2.
- Current executor status: intentionally returns `None` so the runtime does not pretend the spell is deterministic before the shared primitive exists.
