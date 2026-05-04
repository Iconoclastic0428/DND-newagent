# Invisibility

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/invisibility`
- Canonical runtime item record: `XPHB:spell:invisibility`

## Implementation Family
- visibility-condition-buff

## Runtime Behavior
- Implemented exactly from the local XPHB text.
- Cast syntax: `/cast player-1 invisibility player-1`
- Multi-target upcasts create independent invisible child effects tied to one concentration source.
- Local summary: Invisibility gives the touched creature the Invisible condition for 1 hour, ending early if it attacks or casts a spell.

Tests:
- `content/xphb/spells/level-2/invisibility/tests/test_invisibility.py`

## Item-Specific Edge Cases
- Deterministic from the local XPHB text and the invisible-condition lifecycle.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_invisibility.py` verifies the directory payload and the runtime path when implemented.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared primitive and remain out of the runtime registry.
