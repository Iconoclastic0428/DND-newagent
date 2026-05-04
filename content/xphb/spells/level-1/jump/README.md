# Jump

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 jump player-1`
- `/cast player-1 jump player-1 --description Leap over the wagon rail`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.jump.test_jump`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/jump/test_jump.py`.
