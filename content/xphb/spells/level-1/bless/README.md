# Bless

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast player-1 bless player-1 --target player-2 --target player-3`

Local XPHB use case: up to three creatures of your choice within 30 feet add 1d4 to attack rolls and saving throws.

Covered by: `tests/xphb_level1_spells/bless/test_bless.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 bless player-1 --target player-2 --target player-3`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
