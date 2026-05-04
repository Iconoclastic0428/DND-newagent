# Flaming Sphere

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/flaming-sphere`
- Canonical runtime item record: `XPHB:spell:flaming-sphere`

## Implementation Family
- movable-damaging-sphere

## Runtime Behavior
- Blocked: exact local XPHB behavior is not safe to implement without a movable damaging sphere primitive.
- Status: blocked
- Cast syntax: `/cast player-1 flaming-sphere 5 2`
- Local summary: The spell creates a 5-foot-diameter fire sphere that damages creatures ending their turns nearby, can be moved 30 feet as a bonus action, stops when it enters a creature's space, and ignites unattended combustibles.
- Blocker contract: this item remains out of the runtime registry until the shared runtime can move a persistent damage zone with exact collision and ignition behavior.

## Item-Specific Edge Cases
- Exact Flaming Sphere needs the zone to move as a bonus action without recasting the spell.
- Exact Flaming Sphere also needs collision-stop behavior when the sphere enters a creature's space.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_flaming_sphere.py` verifies the directory payload and blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared movable-damaging-sphere primitive and remain out of the runtime registry.
