# XPHB Level-2 Spell Content

This tree holds the Tier-2 level-2 spell rollout. Each spell must live in its own directory with:
- `definition.*`
- `executor.*`
- `registry.*`
- `IMPLEMENTATION.md`
- `README.md`
- `tests/test_<slug>.py`

Runtime wiring must flow through `rules_engine/tier2_spell_registry.py` and the shared capability runtime.
