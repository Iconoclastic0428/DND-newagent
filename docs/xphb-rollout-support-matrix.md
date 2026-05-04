# XPHB Full Rollout Support Matrix

## Scope

This matrix tracks the first full official 2024 `XPHB` rollout target set on top of the shared capability execution layer.

Target scope:

- all `XPHB` non-magical weapons
- all required mundane ammunition referenced by those weapons
- all `XPHB` cantrips
- all `XPHB` 1st-level spells
- all base-class level-1 `XPHB` class features, plus the attached level-1 option entries exposed as separate `classFeature` records in the mirror

The authoritative machine-readable inventory is [xphb-rollout-manifest.json](/d:/DND-newagent/docs/xphb-rollout-manifest.json).

## Target Inventory

| Content family | Target count | Current manifest status |
| --- | ---: | --- |
| Non-magical weapons | 38 | inventoried |
| Mundane ammunition refs | 5 | inventoried |
| Cantrips | 34 | inventoried |
| 1st-level spells | 64 | inventoried |
| Level-1 class-feature records | 40 | inventoried |

Class-feature note:

- The raw `XPHB` class-feature payload exposes 33 base level-1 features and 7 attached level-1 option entries as separate records.
- The rollout manifest tracks the raw source-entry set, not only the top-level class headings, so option bundles cannot disappear silently.

## Current Execution Coverage

This section reflects current repo coverage at the time the rollout manifest was generated.

| Content family | Implemented now | Notes |
| --- | ---: | --- |
| Non-magical weapons | 0 / 38 | Player weapon runtime, ammunition, and mastery execution are not yet modeled end to end. |
| Mundane ammunition refs | 0 / 5 | No authoritative ammunition ledger yet. |
| Cantrips + 1st-level spells | 8 / 98 | Only the current curated spell proof set is executable through the shared capability layer. |
| Level-1 class-feature records | 10 / 40 | Coverage is still starter-pack sized and includes repeated `Weapon Mastery` entries across classes. |

## Implemented Today

Current `XPHB` coverage already executing through the shared runtime:

- Spells: `Fire Bolt`, `Sacred Flame`, `Thunderwave`, `Magic Missile`, `Cure Wounds`, `Healing Word`, `Shield`, `Shield of Faith`
- Level-1 feature records currently represented: `Rage`, `Unarmored Defense`, `Weapon Mastery`, `Second Wind`, `Thaumaturge`

## Missing Mechanic Families

The current inventory and runtime inspection show these missing shared primitives or data-model surfaces:

- Player weapon runtime:
  - typed weapon normalization
  - proficiency matching against real `XPHB` weapon groups
  - equipment/handedness state
  - ammunition tracking
  - weapon-property and mastery execution
- Player spellcasting/runtime state:
  - compiled known/prepared spell state
  - spell-slot and pact-slot surfaces
  - player-facing spellbook and slot inspection commands
- Broader spell primitives:
  - multi-target split resolution
  - roll modifiers such as `Bless` / `Bane` / `Guidance`
  - rider/mark systems for smites, `Hex`, `Hunter's Mark`, and similar effects
  - battlefield zones / obscuration / difficult terrain / trigger volumes
  - summon / servant / illusion / disguise / detection payloads
  - richer reaction-timing hooks for spells like `Feather Fall` and `Hellish Rebuke`
- Level-1 class-feature plumbing:
  - class-feature catalog ingestion
  - feature-option selection state in character creation
  - runtime grants for spellcasting, mastery unlocks, invocations, expertise, languages, and passive modifiers
  - richer resource models beyond a flat `remaining_uses`

## Rollout Order

The intended rollout order for the full pack is:

1. Lock the manifest and completeness tests against the local mirror.
2. Extend normalized item and weapon models so all target weapons survive ingestion with runtime metadata.
3. Add player weapon runtime integration, proficiency gating, ammunition, and mastery unlock plumbing.
4. Expand spell primitives by mechanic family, then replace the curated spell mapper with full `XPHB` cantrip and 1st-level coverage.
5. Extend class-feature normalization, character-creation selection, and runtime grants until all level-1 feature records are wired.
6. Keep the manifest current and fail fast on silent omissions.

## Guardrail

This document is descriptive. The machine-enforced completeness contract lives in:

- [xphb-rollout-manifest.json](/d:/DND-newagent/docs/xphb-rollout-manifest.json)
- the `tests/test_xphb_rollout_manifest.py` mirror-diff test
