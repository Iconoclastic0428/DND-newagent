# Create or Destroy Water

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> create-or-destroy-water 2 0 --mode create --description Fill the bucket`

Local mirror notes:
- 1 action, range 30 ft, V/S/M water and sand.
- Create: up to 10 gallons of clean water in an open container, or rain in a 30-foot cube.
- Destroy: up to 10 gallons of water in an open container, or clear fog in a 30-foot cube.

Dedicated tests live in `tests/xphb_level1_spells/create_or_destroy_water/test_create_or_destroy_water.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> create-or-destroy-water 2 0 --mode create --description Fill the bucket`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
