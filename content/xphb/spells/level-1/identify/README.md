# Identify

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> identify --item <item-id> --material pearl`

Local XPHB notes:
- 1 minute, touch, pearl worth 100+ gp.
- While casting, you must remain in contact with the object.
- You learn magical properties, use, attunement requirements, and current charges.
- You learn whether spell effects are present on the object, what spell created the object, and whether a creature is under a spell effect while you are in contact with it.

Test coverage: [tests/xphb_level1_spells/identify/test_identify.py](../../../../../tests/xphb_level1_spells/identify/test_identify.py)

Use cases and exact local text notes live in [docs/xphb-level1-spell-use-cases.md](../../../../../docs/xphb-level1-spell-use-cases.md).

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> identify --item <item-id> --material pearl`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
