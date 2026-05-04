# Heroism

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 heroism player-1`
- `/cast player-1 heroism player-1 --description Steel the caster against fear`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.heroism.test_heroism`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/heroism/test_heroism.py`.
