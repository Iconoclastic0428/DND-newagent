# Enhance Ability

Status: implemented

Cast syntax:
- `/cast player-1 enhance-ability player-1 --ability STR`
- Multi-target upcasts use `--targets a,b` together with per-target ability mapping like `--target-abilities player-1:STR,player-2:WIS`.

Tests:
- `content/xphb/spells/level-2/enhance-ability/tests/test_enhance_ability.py`

Summary:
- Exact XPHB Enhance Ability grants advantage on checks with the chosen ability for 1 hour.

See `IMPLEMENTATION.md` for the exact local-text classification and blockers.
