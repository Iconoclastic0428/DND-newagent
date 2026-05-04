# Mind Spike

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/mind-spike`
- Canonical runtime item record: `XPHB:spell:mind-spike`

## Implementation Family
- save-plus-tracking

## Runtime Behavior
- Blocked: Exact Mind Spike needs an authoritative tracking payload that can reveal location while suppressing stealth in the way the spell text specifies.
- Cast syntax: `/cast player-1 mind-spike monster-skeleton-1`
- Local summary: Blocked: the current runtime does not have an exact location-reveal and hidden-state suppression primitive for Mind Spike.
- Blocker contract: this item remains out of the runtime registry until the shared observer-tracking primitive exists.

## Item-Specific Edge Cases
- Exact Mind Spike needs an authoritative tracking payload that can reveal location while suppressing stealth in the way the spell text specifies.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_mind_spike.py` verifies the directory payload and the blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared primitive and remain out of the runtime registry.
