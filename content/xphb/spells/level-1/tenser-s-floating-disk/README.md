# Tenser's Floating Disk

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> tenser-s-floating-disk x y --description Lift the cargo`
Cargo syntax: `/interact <disk-id> transfer <ally-actor-id> <item-id>`

Local mirror notes:
- 1 action, range 30 ft, V/S/M a drop of mercury.
- The disk is 3 feet in diameter, floats 3 feet above the ground, and lasts 1 hour.
- It can carry up to 500 pounds total, including transferred cargo and mounted riders.
- It follows the caster if it moves too far away.
- It cannot cross a vertical distance of more than 10 feet.

Dedicated tests live in `tests/xphb_level1_spells/tenser_s_floating_disk/test_tenser_s_floating_disk.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> tenser-s-floating-disk x y --description Lift the cargo`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
