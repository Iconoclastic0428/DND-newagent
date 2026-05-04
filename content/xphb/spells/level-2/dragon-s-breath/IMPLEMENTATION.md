# Dragon's Breath

## Source of Truth
- Local mirror: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Item directory: `content/xphb/spells/level-2/dragon-s-breath`
- Canonical id: `XPHB:spell:dragon-s-breath`

## Blocking Contract
- Runtime status stays `blocked`.
- `build_capability_definition(...)` intentionally returns `None` for the exact spell.
- This item becomes implementable only when the shared runtime can attach a reusable granted action to another creature for the lifetime of an active effect.

## Exact Primitive Still Needed
- active-effect-granted reusable breath action primitive.
- Required behavior:
  - grant a Magic action to the touched target while the spell is active,
  - persist the chosen damage type and higher-slot scaling with that granted action,
  - spend the target's action economy when the target exhales,
  - resolve a 15-foot cone from the target,
  - cleanly revoke the granted action when concentration ends.

## Why Current Runtime Is Not Exact Enough
- The runtime can resolve cone areas, but it cannot currently grant a reusable action to another creature through an active effect.
- Existing held-conjuration and instant-strike helpers are caster-centric and do not model this spell's "touch a creature, then that creature later uses a Magic action" flow.

## Verification
- Keep the docs and tests aligned with the blocked status.
- Do not claim an implementation until the shared primitive exists.
