# Divine Favor

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 divine-favor`
- `/cast player-1 divine-favor --description Invoke divine aid for radiant weapon strikes`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.divine_favor.test_divine_favor`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/divine_favor/test_divine_favor.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 divine-favor`
- Example: `/cast player-1 divine-favor --description Invoke divine aid for radiant weapon strikes`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
