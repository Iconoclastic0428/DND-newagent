---
id: xphb-level1-spell-casts-c
type: dm_summary
title: XPHB Level-1 Spell Casts for Worker C
campaign: lmop
visibility: public
state_scope: summary
token_budget_hint: small
---
# XPHB Level-1 Spell Casts for Worker C

These are the spell forms exercised by the current worker-C spell tests under `tests/xphb_level1_spells/`.

## Deterministic combat and area spells
- `Divine Smite`
  - Triggered cast: `/attack player-1 <melee-weapon> <target>` then choose the `Divine Smite` post-hit option with `/react player-1 <option-id>`.
  - Test file: `tests/xphb_level1_spells/divine_smite/test_divine_smite.py`
- `Hail of Thorns`
  - Triggered cast: `/attack player-1 <ranged-weapon> <target>` then choose the `Hail of Thorns` post-hit option with `/react player-1 <option-id>`.
  - Test file: `tests/xphb_level1_spells/hail_of_thorns/test_hail_of_thorns.py`
- `Hellish Rebuke`
  - Triggered cast: after taking damage from a visible creature within 60 ft, choose the `Hellish Rebuke` reaction option with `/react player-1 <option-id>`.
  - Test file: `tests/xphb_level1_spells/hellish_rebuke/test_hellish_rebuke.py`
- `Witch Bolt`
  - Initial cast: `/cast player-1 witch-bolt <target-id>`
  - Sustain follow-up: `/cast player-1 witch-bolt <target-id> --mode sustain`
  - Test file: `tests/xphb_level1_spells/witch_bolt/test_witch_bolt.py`
- `Fog Cloud`
  - Cast form: `/cast player-1 fog-cloud x y`
  - Test file: `tests/xphb_level1_spells/fog_cloud/test_fog_cloud.py`
- `Entangle`
  - Cast form: `/cast player-1 entangle x y`
  - Test file: `tests/xphb_level1_spells/entangle/test_entangle.py`

## Story-mode controlled social spells
- `Animal Friendship`
  - Cast form: `/cast player-1 animal-friendship --description <what the caster is trying to do>`
  - Test file: `tests/xphb_level1_spells/animal_friendship/test_animal_friendship.py`
- `Charm Person`
  - Cast form: `/cast player-1 charm-person <target-id> --description <how the caster uses the spell in the scene>`
  - Test file: `tests/xphb_level1_spells/charm_person/test_charm_person.py`

## Notes
- The six combat/area spells above now run through the deterministic encounter runtime, not the story-adjudicated fallback.
- `Animal Friendship` and `Charm Person` remain authoritative story-mode spells with witness/social reaction handling and dedicated tests.
