# Heat Metal

## Source of Truth
- Local mirror: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Item directory: `content/xphb/spells/level-2/heat-metal`
- Canonical id: `XPHB:spell:heat-metal`

## Blocking Contract
- Runtime status stays `blocked`.
- `build_capability_definition(...)` intentionally returns `None` for the exact spell.
- This item becomes implementable only when the shared runtime can attach the spell to a concrete manufactured metal object and keep resolving consequences through that object over time.

## Exact Primitive Still Needed
- item-linked harmful effect primitive.
- Required behavior:
  - select and persist a concrete target object,
  - reapply bonus-action damage through that object while it stays in range,
  - determine who is holding or wearing the object at each pulse,
  - force a drop on a failed Constitution save when the holder can drop it,
  - apply attack-roll and ability-check disadvantage until the caster's next turn when the object is not dropped.

## Why Current Runtime Is Not Exact Enough
- The runtime has no object-targeted harmful effect that persists against an item and follows that item's holder or wearer.
- Current disadvantage support only includes one-shot next-attack disadvantage and protected-target cases, not the full "attack rolls and ability checks until your next turn" rider.
- Existing damage, command, and active-effect helpers do not encode the holder or wearer drop loop from the local XPHB text.

## Verification
- Keep the docs and tests aligned with the blocked status.
- Do not claim an implementation until the shared primitive exists.
