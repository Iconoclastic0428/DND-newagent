# Unseen Servant

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> unseen-servant x y --description Carry the supplies`
Transfer syntax: `/interact <servant-id> transfer <ally-actor-id> <item-id>`

Local mirror notes:
- 1 action, range 60 ft, V/S/M string and wood, lasts 1 hour.
- The servant is invisible, mindless, shapeless, Medium, and made of force.
- It has AC 10, HP 1, Strength 2, cannot attack, and ends if reduced to 0 HP.
- It can be commanded as a bonus action to move 15 feet and interact with an object, but only perform simple tasks.
- It can receive transferable allied inventory items and use carried item capabilities while controlled by its owner.

Dedicated tests live in `tests/xphb_level1_spells/unseen_servant/test_unseen_servant.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> unseen-servant x y --description Carry the supplies`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
