# Implement Tier-2 Spell

Follow `../implement-tier2-content-item/SKILL.md` first.

## Additional spell rules
1. Confirm the exact XPHB spell text in the local mirror and classify it before coding: deterministic now vs clarification-needed.
2. Reuse shared spell/runtime primitives for targeting, concentration, duration, active effects, movement, saves, damage, summons, zones, and observer visibility.
3. Keep spell legality, slot use, concentration, and state mutation authoritative in the rules engine.
4. Every spell directory must include its own executor module and its own individual test file.
5. Update `content/manifests/tier2_level2_spells_manifest.json` and `content/manifests/tier2_support_matrix.json`.
6. If the spell cannot be implemented exactly from the local text without guessing, mark it blocked and document why in the manifest and `IMPLEMENTATION.md`.
