# Flame Blade

## Source of Truth
- Local mirror: `D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json`
- Item directory: `content/xphb/spells/level-2/flame-blade`
- Canonical id: `XPHB:spell:flame-blade`

## Blocking Contract
- Runtime status stays `blocked`.
- `build_capability_definition(...)` intentionally returns `None` for the exact spell.
- This item becomes implementable only when the shared runtime can model a conjured weapon that persists in a hand, disappears on release, and can be resummoned by the same spell effect.

## Exact Primitive Still Needed
- held conjured weapon lifecycle primitive.
- Required behavior:
  - reserve a free hand for the conjured blade,
  - grant a reusable Magic action melee spell attack,
  - dismiss the blade when the wielder lets go,
  - allow a bonus action to resummon the same blade while concentration lasts,
  - carry the spell's light emission and higher-slot scaling.

## Why Current Runtime Is Not Exact Enough
- The shared held-conjuration runtime only covers Dancing Lights, Mage Hand, and Produce Flame.
- Instant strikes are one-shot effects and do not model a persistent held weapon.
- Summoned creatures and created objects do not capture the hand-bound lifecycle or the resummon rule from the local XPHB text.

## Verification
- Keep the docs and tests aligned with the blocked status.
- Do not claim an implementation until the shared primitive exists.
