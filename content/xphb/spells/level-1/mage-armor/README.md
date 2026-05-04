# Mage Armor

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 mage-armor player-1`
- `/cast player-1 mage-armor player-1 --description Wards the caster in conjured armor`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.mage_armor.test_mage_armor`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/mage_armor/test_mage_armor.py`.
