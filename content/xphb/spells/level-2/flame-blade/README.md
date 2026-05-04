# Flame Blade

## Status
- Runtime status: blocked for exact deterministic XPHB support.
- Planned cast syntax after the missing primitive exists: `/cast player-1 flame-blade`

## Exact Local XPHB Behavior
- Bonus action, self, concentration up to 10 minutes.
- Conjure a blade of fire in a free hand.
- If you let go of the blade, it disappears, and you can use a bonus action to resummon it.
- You use a Magic action to make a melee spell attack with the blade.
- On a hit, the target takes 3d6 fire damage plus your spellcasting ability modifier.
- The blade sheds bright light in a 10-foot radius and dim light for another 10 feet.
- Higher-level slots add 1d6 damage per slot level above 2.

## Missing Shared Primitive
- Missing primitive: held conjured weapon lifecycle primitive.
- The primitive must keep the blade attached to a free hand, dismiss it when released, and allow the spell's bonus-action resummon.
- It must grant a reusable melee spell attack while the spell remains active.
- It must carry the spell's light emission and higher-slot damage scaling without ad hoc local bookkeeping.

## Test Contract
- `executor.py` must keep returning `None` for the exact local spell until that primitive exists.
- `tests/test_flame_blade.py` locks the blocked status, local source facts, and blocker wording.
