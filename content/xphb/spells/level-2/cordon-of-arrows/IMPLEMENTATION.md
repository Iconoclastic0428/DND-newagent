# Cordon of Arrows

## Source of Truth
- Local XPHB mirror entry: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Local item directory: `content/xphb/spells/level-2/cordon-of-arrows`
- Canonical runtime item record: `XPHB:spell:cordon-of-arrows`

## Implementation Family
- armed-ward

## Runtime Behavior
- Blocked: exact local XPHB behavior is not safe to implement without a ward-charge primitive.
- Status: blocked
- Cast syntax: `/cast player-1 cordon-of-arrows player-1`
- Local summary: The spell plants up to four nonmagical arrows or bolts in the caster's space and fires one arrow at a creature that first enters or ends a turn within 30 feet of them; each shot destroys an arrow, and the spell ends when all arrows are spent.
- Blocker contract: this item remains out of the runtime registry until the shared runtime can track armed ward charges and consume one charge per trigger.

## Item-Specific Edge Cases
- Exact Cordon of Arrows needs the spell to track the number of planted arrows as discrete charges.
- Exact Cordon of Arrows also needs a proximity trigger that can fire on entry or end-of-turn within the ward radius.

## Test Matrix
- `definition.json` mirrors the local source and status metadata.
- `registry.json` records local item status without touching shared registries.
- `tests/test_cordon_of_arrows.py` verifies the directory payload and blocker contract.

## Dependencies
- Implemented items depend on the shared capability runtime only.
- Blocked items depend on a future shared ward-charge primitive and remain out of the runtime registry.
