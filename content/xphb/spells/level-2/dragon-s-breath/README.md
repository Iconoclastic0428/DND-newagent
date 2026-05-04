# Dragon's Breath

## Status
- Runtime status: blocked for exact deterministic XPHB support.
- Planned cast syntax after the missing primitive exists: `/cast player-1 dragon-s-breath player-1 --damage-type fire`

## Exact Local XPHB Behavior
- Bonus action, touch, concentration up to 1 minute.
- Touch a willing creature and choose acid, cold, fire, lightning, or poison.
- The touched creature gains a Magic action that exhales a 15-foot cone.
- Creatures in the cone make a Dexterity save, taking 3d6 of the chosen damage type on a failure and half on a success.
- Higher-level slots add 1d6 damage per slot level above 2.

## Missing Shared Primitive
- Missing primitive: active-effect-granted reusable breath action primitive.
- The primitive must grant and later revoke a reusable action on the touched target while concentration lasts.
- It must store the chosen damage type and slot scaling on the granted action, not on the caster only.
- It must resolve the 15-foot cone from the target that received the spell, not from the original caster.

## Test Contract
- `executor.py` must keep returning `None` for the exact local spell until that primitive exists.
- `tests/test_dragon_s_breath.py` locks the blocked status, local source facts, and blocker wording.
