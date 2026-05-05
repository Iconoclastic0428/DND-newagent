# Armor of Agathys

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

## Story Cast Examples
- `/cast player-1 armor-of-agathys`
- `/cast player-1 armor-of-agathys --description Frost armor flares around the caster`

## Coverage
- Per-spell test module: `tests.xphb_level1_spells.armor_of_agathys.test_armor_of_agathys`
- Behavior is currently validated through the authoritative story-adjudication path.
Covered by: `tests/xphb_level1_spells/armor_of_agathys/test_armor_of_agathys.py`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 armor-of-agathys`
- Example: `/cast player-1 armor-of-agathys --description Frost armor flares around the caster`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
