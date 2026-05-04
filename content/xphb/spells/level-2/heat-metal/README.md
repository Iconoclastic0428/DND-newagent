# Heat Metal

## Status
- Runtime status: blocked for exact deterministic XPHB support.
- Planned cast syntax after the missing primitive exists: `/cast player-1 heat-metal --object-id metal-weapon-1`

## Exact Local XPHB Behavior
- Action, 60 feet, concentration up to 1 minute.
- Target a visible manufactured metal object, such as a metal weapon or metal Medium or Heavy armor.
- On the cast and on later bonus actions while the object remains in range, creatures in physical contact with the object take 2d8 fire damage.
- A creature holding or wearing the heated object that takes this damage makes a Constitution save.
- On a failed save, the creature must drop the object if it can.
- If the object is not dropped, the creature has disadvantage on attack rolls and ability checks until your next turn.
- Higher-level slots add 1d8 damage per slot level above 2.

## Missing Shared Primitive
- Missing primitive: item-linked harmful effect primitive.
- The primitive must anchor the spell to a specific object rather than a creature.
- It must find the current holder or wearer on each damage pulse and reapply damage through later bonus actions.
- It must support the follow-up Constitution save, forced drop when legal, and the "until your next turn" disadvantage rider when the object remains in contact.

## Test Contract
- `executor.py` must keep returning `None` for the exact local spell until that primitive exists.
- `tests/test_heat_metal.py` locks the blocked status, local source facts, and blocker wording.
