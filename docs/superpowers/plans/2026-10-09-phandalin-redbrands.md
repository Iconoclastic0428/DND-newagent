# Phandalin and Redbrands Implementation Plan

> Execute inline with the executing-plans and test-driven-development workflows. The user approved implementation on 2026-10-09. Keep work in the primary agent.

**Goal:** A connected, persistent Phandalin arrival, town investigation, and Redbrand Hideout arc through Glasstaff on the official player maps.

**Architecture:** Authored campaign-site definitions live under campaigns/lmop; shared typed site intents/events and a generic rules-engine site resolver own site state. A small session adapter coordinates existing encounter mechanics and story presentation. The browser consumes redacted town/site views and the existing tactical-map projection. No model response directly commits site or combat state.

**Tech stack:** Existing Python dataclasses/unittest, JSON campaign assets, deterministic EncounterKernel, vanilla JS/CSS frontend. No added dependencies.

## Approved design and boundaries
- LMoP chapter 2 story/map art, matching Cragmaw; existing 2024 catalog/mechanics remain the mechanical authority. Imported monster record IDs are explicit, with missing content errors rather than replacement creatures.
- Phandalin is a POI map, not a tactical grid. Barthen, Stonehill, Townmaster, Alderleaf, Sleeping Giant, and Tresendar provide independent leads. Dialogue reveals knowledge, never moves the party implicitly.
- Public arrival requires regional arrival; the explicit phandalin direct-start fixture is for manual testing. Initial arrival preserves HP/resources/conditions and existing Sildar outcomes.
- Site actions use typed intents, validation, deterministic event construction, append-only logging, then state reduction. Invalid actions leave state and random counter unchanged.
- Hideout entry is an explicit choice. Front entrance requires the manor; concealed entrance requires the Alderleaf lead. Exit requires reaching an entrance. Revisit restores doors, enemy HP, completed encounters, prisoner state, and discoveries.
- Tactical exploration reuses movement/vision legality with a fresh six-second movement budget per declared exploration step; it advances rules time instead of assigning artificial movement speeds. Combat uses normal turn economy.
- The twelve authored rooms include cellar, barracks, trapped hall, crypt, slave pens, armory, storeroom, crevasse/nothic, bugbear barracks, common room, laboratory, and Glasstaff quarters. Every encounter uses explicit participants; hidden enemies never leak into player views.
- Secret doors, traps, keys, prisoners, and evidence have explicit discovery/use conditions. Nothic interaction offers negotiation or explicit combat. Completion comes from authoritative outcomes, not narration keywords.
- Town interaction commands are /visit and /talk; dungeon interactions are explicit /site verbs and existing /move. The UI shows exact server-projected choices. Freeform story remains supported; ambiguous campaign actions return clarification rather than keyword mutation.
- Hidden map cells are opaque; no hidden feature or room IDs in player inspection. DM views retain authoring information.

## Task 1 — Authored assets and typed site contract
Files: shared_types/campaign_site.py, campaign_ingestion/site_loader.py, campaigns/lmop/sites/phandalin-redbrands.json, data/maps/redbrand_hideout_map.json, web_frontend/assets/maps/*, tests/test_campaign_sites.py.
- [x] Write failing loader/content tests for six town POIs, twelve rooms, two entrances and exact image/grid metadata.
- [x] Run `python -m unittest tests.test_campaign_sites -v`; confirm missing module failure.
- [x] Implement strict dataclass loader and image-first map geometry, validate all referenced positions/features/encounters.
- [x] Re-run tests; inspect coordinate overlay against source map.

## Task 2 — Deterministic site transitions and exploration
Files: rules_engine/campaign_sites.py, shared_types/campaign_site.py, encounter_runtime/kernel.py, shared_types/encounter_intents.py, tests/test_campaign_sites.py.
- [x] Add failing tests for arrival, visits, NPC knowledge, hidden entrance denial, preserved HP, movement blockers, interaction range, check failure, and event replay.
- [x] Implement typed resolver with transactional working state and replayable site/mechanical events.
- [x] Add generic out-of-combat movement intent that reuses movement legality and advances six seconds.
- [x] Verify failed actions do not mutate canonical state; no unlimited speed, no substitute stat blocks.

## Task 3 — Session wiring and full encounter progression
Files: session_server/campaign_site_session.py, session_server/storytelling_session.py, session_server/bootstrap.py, campaigns/lmop/maps/high-road-region-hex.json, chapter-02 documents, tests/test_phandalin_session.py.
- [x] Add failing integration tests for regional arrival, direct start, clue-driven entry, combat participants, defeated enemy persistence, and returning to town.
- [x] Remove obsolete Phandalin blocking and connect the arrival hook; retain Cragmaw rescue outcomes.
- [x] Wire room exploration, doors, secrets/trap, nothic choice, prisoners, guards and Glasstaff to deterministic site and encounter transitions.
- [x] Verify player ownership, no DM model requirement for deterministic site choices, and no reset of party resources or event history.

## Task 4 — Browser and privacy
Files: shared_types/web_ui.py, session_server/web_projection.py, web_frontend/app.js, web_frontend/styles.css, user-test/web_story_demo_server.py, tests/test_phandalin_session.py.
- [x] Add failing projection tests for town actions, hidden entrances/features/enemies and exploration tactical map.
- [x] Render town image/POI selection, site actions and exploration map with existing movement UI.
- [x] Add --story-start phandalin; inspect both player and DM views in browser.
- [x] Capture raw interactions, API projections and screenshots without provider calls.

## Task 5 — Regression and delivery
- [x] Run campaign-site and session tests, existing travel/Cragmaw/story/web tests, Python compile and JS syntax checks.
- [x] Inspect `git diff --check` and review authority/privacy boundaries.
- [x] Record actual passing results and remaining limits in tasks/TODO.md and tasks/SUMMARIES.md.
- [x] Preserve original dirty checkout; deliver verified worktree paths and launch instructions. No push unless requested.

## Review checkpoint
Baseline: 33 Cragmaw/travel tests pass. Plan self-reviewed for the complete requested arc, image-first geometry, transactional failure behavior, privacy and party-resource preservation. The existing session has legacy mutable transitions; new site transitions remain isolated behind their typed resolver rather than adding more campaign-specific kernel branches.

### Implementation review — 2026-10-09
- Implemented in `C:/Users/Shengqi Li/.codex/worktrees/workflow-naacl-review/DND-newagent`, branch `codex/phandalin-redbrands`, based on 80c4150 plus preserved local Cragmaw work. Original application-source hashes remain unchanged. No commit/push/merge.
- Added authored six-POI town navigation, regional arrival, both discoverable approaches, twelve-room map geometry, seventeen doors, seven scoped encounters, nothic negotiation, Droop/key information, prisoner rescue, Glasstaff/evidence and in-session revisits.
- Mechanics use typed transactional site actions and existing kernel movement/attacks/saves/falls/slots/initiative. Explicit object-interaction costs reuse the kernel. Fixed scoped completion/opportunity participation, main-entrance under-landing access, old source attack parsing, and actual full-demo map API routing.
- Verification: 186 tests passed in 216.034 seconds across site/session, Cragmaw, travel, story, full manual wrapper, web, monster pipeline, battlefield, visibility, frontend chat and encounter kernel. Python compile: 18 files. JavaScript syntax and git diff whitespace checks pass; line-ending warnings only.
- Full-arc fixture passes 627-event replay with complete site/encounter state equality. It uses a boosted test-only actor and passive enemy turns; separate tests execute source monster attacks, Multiattack, Magic Missile, Hold Person and Misty Step. No balance or live-model claim.
- Browser proof: town markers have no overlaps in the checked viewport; both entrances and movement work; player/DM views differ; Nothic token loads at 280 px from the full mirror. Raw inputs/outputs, screenshots, and replay artifacts are saved under worktree/tasks.
- Live local fixture: HTTP 8020 / WS 8780, PID 39932, isolated campaign-release copy and explicit full-mirror base URL. Returned the party to Phandalin after the smoke route.
- Preserved original dirty checkout and restored existing regression tests' DM-memory writes in the worktree from baseline. Continued solo as requested; no subagents.
- Scope limits are explicit in docs/PHANDALIN-REDBRANDS.md: optional Chapter 2 quests, scripted retreat/reinforcements, numeric reward/loot transfer, narrow-ledge trap bypass, teleport/forced-relocation trap entry, full elapsed-time effect lifecycle, and restart/save-game persistence remain outside this delivered slice.
