# Spiritual Weapon

## Source of Truth
- Local mirror: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Item directory: `content/xphb/spells/level-2/spiritual-weapon`
- Canonical id: `XPHB:spell:spiritual-weapon`

## Blocking Contract
- Runtime status stays `blocked`.
- `build_capability_definition(...)` intentionally returns `None` for the exact spell.
- This item becomes implementable only when the shared runtime can maintain a persistent floating weapon location and let the caster reuse a bonus action to command it.

## Exact Primitive Still Needed
- floating weapon command primitive.
- Required behavior:
  - create a persistent weapon anchor at a chosen point in range,
  - make the immediate melee spell attack on cast,
  - allow later bonus actions to move the weapon up to 20 feet,
  - resolve the repeated melee spell attack from the weapon's position,
  - remove the weapon cleanly when the spell ends.

## Why Current Runtime Is Not Exact Enough
- The runtime can summon creatures and create objects, but it has no non-initiative floating-weapon command model.
- Instant strikes do not preserve weapon position for later turns.
- The current command flow does not provide a shared primitive for this spell's combined summon point, immediate attack, and later move-and-attack reuse.

## Verification
- Keep the docs and tests aligned with the blocked status.
- Do not claim an implementation until the shared primitive exists.
