# Silence

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/silence`
- Canonical runtime item record: `XPHB:spell:silence`

## Implementation Family
- spell-blocking-zone

## Runtime Behavior
- Blocked: Exact Silence needs an authoritative sound-blocking area that can suppress verbal casting and hearing-based effects.
- Cast syntax: `/cast player-1 silence 5 2`
- Local summary: Blocked: the current runtime does not have an exact sound-propagation and verbal-component suppression zone primitive.
- Blocker contract: this item remains out of the runtime registry until the shared sound-blocking zone primitive exists.

## Item-Specific Edge Cases
- Exact Silence needs an authoritative sound-blocking area that can suppress verbal casting and hearing-based effects.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_silence.py` verifies the directory payload and the blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared primitive and remain out of the runtime registry.
