# False Life

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 false-life`
- `/cast player-1 false-life --description Harden your constitution with necromantic vigor`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.false_life.test_false_life`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/false_life/test_false_life.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 false-life`
- Example: `/cast player-1 false-life --description Harden your constitution with necromantic vigor`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
