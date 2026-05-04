# Find Familiar

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> find-familiar 2 0 --form owl --type celestial --material incense --description Summon an owl familiar`

Local mirror notes:
- 1 hour, range 10 ft, V/S/M incense worth 1,000 cp and consumed.
- The familiar appears in one of the listed forms, or another CR 0 beast if the rules allow it.
- The familiar shares telepathic contact within 100 ft and can deliver touch spells.

Dedicated tests live in `tests/xphb_level1_spells/find_familiar/test_find_familiar.py`.
