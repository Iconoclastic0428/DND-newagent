# Cloud of Daggers

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/cloud-of-daggers`
- Canonical runtime item record: `XPHB:spell:cloud-of-daggers`

## Implementation Family
- persistent-zone-damage

## Runtime Behavior
- Blocked: exact local XPHB behavior is not safe to implement without a movable persistent-zone primitive.
- Status: blocked
- Cast syntax: `/cast player-1 cloud-of-daggers 5 2`
- Local summary: The spell creates a 5-foot cube of spinning daggers that damages creatures on entry, on ending turn in the cube, or when the cube moves into occupied space, and later allows the caster to move the cube 30 feet as an action.
- Blocker contract: this item remains out of the runtime registry until a shared primitive can re-anchor a persistent zone without losing its damage bookkeeping.

## Item-Specific Edge Cases
- Exact Cloud of Daggers needs a persistent zone that can be re-anchored by the caster.
- Exact Cloud of Daggers also needs once-per-turn damage bookkeeping to prevent repeat damage from the same creature in the same turn.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_cloud_of_daggers.py` verifies the directory payload and blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared movable-zone primitive and remain out of the runtime registry.
