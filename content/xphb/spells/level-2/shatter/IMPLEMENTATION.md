# Shatter

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/shatter`
- Canonical runtime item record: `XPHB:spell:shatter`

## Implementation Family
- unattended-object-damage

## Runtime Behavior
- Blocked: exact local XPHB behavior is not safe to implement without an unattended-object damage primitive.
- Status: blocked
- Cast syntax: `/cast player-1 shatter 5 2`
- Local summary: The spell creates a 10-foot-radius thunder burst that damages creatures and also damages nonmagical objects in the area that are not worn or carried.
- Blocker contract: this item remains out of the runtime registry until the shared runtime can target and damage unattended objects directly.

## Item-Specific Edge Cases
- Exact Shatter needs a rules-level primitive for selecting unattended, nonmagical objects in the spell area.
- Exact Shatter also needs to preserve creature save resolution and construct disadvantage while object damage resolves.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_shatter.py` verifies the directory payload and blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared unattended-object damage primitive and remain out of the runtime registry.
