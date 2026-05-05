# Bane

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast player-1 bane monster-mage-1 --target monster-goblin-1 --target monster-goblin-2`

Local XPHB use case: up to three creatures you can see within 30 feet must make a Charisma saving throw.

Covered by: `tests/xphb_level1_spells/bane/test_bane.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 bane monster-mage-1 --target monster-goblin-1 --target monster-goblin-2`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
