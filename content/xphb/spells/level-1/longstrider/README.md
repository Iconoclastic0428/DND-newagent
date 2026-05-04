# Longstrider

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 longstrider player-1`
- `/cast player-1 longstrider player-1 --description Increase the caster's pace`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.longstrider.test_longstrider`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/longstrider/test_longstrider.py`.
