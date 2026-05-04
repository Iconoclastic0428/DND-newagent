# Protection from Poison

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/protection-from-poison`
- Canonical runtime item record: `XPHB:spell:protection-from-poison`

## Implementation Family
- condition-removal-plus-resistance

## Runtime Behavior
- Blocked: Exact Protection from Poison needs source-aware poison-save advantage plus poison-condition cleanup; the current runtime does not have a poison-specific save hook without guessing.
- Cast syntax: `/cast player-1 protection-from-poison player-1`
- Local summary: Exact XPHB Protection from Poison ends poisoned, grants advantage on saves to avoid or end poisoned, and gives poison resistance.
- Blocker contract: this item remains out of the runtime registry until the poison-specific save hook exists.

## Item-Specific Edge Cases
- Exact Protection from Poison needs source-aware poison-save advantage plus poison-condition cleanup; the current runtime does not have a poison-specific save hook without guessing.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_protection_from_poison.py` verifies the directory payload and the blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared primitive and remain out of the runtime registry.
