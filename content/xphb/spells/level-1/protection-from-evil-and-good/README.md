# Protection from Evil and Good

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 protection-from-evil-and-good player-1`
- `/cast player-1 protection-from-evil-and-good player-1 --description Ward the caster from fiends and undead`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.protection_from_evil_and_good.test_protection_from_evil_and_good`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/protection_from_evil_and_good/test_protection_from_evil_and_good.py`.
