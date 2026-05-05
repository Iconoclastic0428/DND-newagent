# Protection from Evil and Good

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 protection-from-evil-and-good player-1`
- `/cast player-1 protection-from-evil-and-good player-1 --description Ward the caster from fiends and undead`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.protection_from_evil_and_good.test_protection_from_evil_and_good`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/protection_from_evil_and_good/test_protection_from_evil_and_good.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 protection-from-evil-and-good player-1`
- Example: `/cast player-1 protection-from-evil-and-good player-1 --description Ward the caster from fiends and undead`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
