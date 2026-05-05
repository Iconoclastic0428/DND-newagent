# Chromatic Orb

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast player-1 chromatic-orb monster-mage-1 --damage-type fire --material diamond-50-gp`

Local XPHB use case: choose a damage type and supply the costly diamond component.

Covered by: `tests/xphb_level1_spells/chromatic_orb/test_chromatic_orb.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 chromatic-orb monster-mage-1 --damage-type fire --material diamond-50-gp`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
