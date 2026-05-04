# Spiritual Weapon

## Status
- Runtime status: blocked for exact deterministic XPHB support.
- Planned cast syntax after the missing primitive exists: `/cast player-1 spiritual-weapon 5 2 --target monster-skeleton-1`

## Exact Local XPHB Behavior
- Bonus action, 60 feet, concentration up to 1 minute.
- Create a floating spectral weapon at a point you choose in range.
- When the spell is cast, you immediately make a melee spell attack against a creature within 5 feet of the weapon.
- On a hit, the target takes 1d8 + your spellcasting ability modifier force damage.
- On later turns, you can use a bonus action to move the weapon up to 20 feet and repeat the same attack against a creature within 5 feet of it.
- Higher-level slots add 1d8 damage per slot level above 2.

## Missing Shared Primitive
- Missing primitive: floating weapon command primitive.
- The primitive must create a persistent weapon anchor that is not just a one-shot attack.
- It must support the immediate attack on cast and the later bonus-action move-and-attack loop.
- It must resolve attacks from the weapon's position rather than from the caster's square.

## Test Contract
- `executor.py` must keep returning `None` for the exact local spell until that primitive exists.
- `tests/test_spiritual_weapon.py` locks the blocked status, local source facts, and blocker wording.
