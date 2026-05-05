# Goodberry

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> goodberry`

Local mirror notes:
- 1 action, touch, V/S/M mistletoe.
- The spell creates 10 berries.
- A creature can eat a berry as a bonus action to regain 1 HP and receive a day's nourishment.
- Uneaten berries vanish after 24 hours.

Dedicated tests live in `tests/xphb_level1_spells/goodberry/test_goodberry.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> goodberry`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
