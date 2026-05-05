# Purify Food and Drink

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> purify-food-and-drink x y`

Local mirror notes:
- 1 action, range 10 ft.
- The spell purifies nonmagical food and drink in a 5-foot-radius sphere.

Dedicated tests live in `tests/xphb_level1_spells/purify_food_and_drink/test_purify_food_and_drink.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> purify-food-and-drink x y`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
