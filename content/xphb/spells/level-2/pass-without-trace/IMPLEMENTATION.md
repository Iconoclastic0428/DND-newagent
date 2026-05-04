# Pass without Trace

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/pass-without-trace`
- Canonical runtime item record: `XPHB:spell:pass-without-trace`

## Implementation Family
- party-aura-stealth

## Runtime Behavior
- Blocked: Exact Pass without Trace needs a no-tracks / trail-suppression consumer; the current runtime has the stealth bonus primitive but no authoritative track suppression primitive.
- Cast syntax: `/cast player-1 pass-without-trace`
- Local summary: Exact XPHB Pass without Trace grants +10 Stealth in the aura and suppresses tracks.
- Blocker contract: this item remains out of the runtime registry until trail suppression is implemented.

## Item-Specific Edge Cases
- Exact Pass without Trace needs a no-tracks / trail-suppression consumer; the current runtime has the stealth bonus primitive but no authoritative track suppression primitive.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_pass_without_trace.py` verifies the directory payload and the blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared primitive and remain out of the runtime registry.
