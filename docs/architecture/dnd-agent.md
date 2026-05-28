# Character Creation Kernel

## Purpose
This repository now includes the first deterministic subsystem for the D&D 2024 agent platform: a level-1 character-creation kernel driven by typed intents, DM-governed source policy, and 5etools-backed mirror content.

## Boundary
- The subsystem does not perform DM narration.
- The subsystem does not accept freeform natural-language character creation.
- The subsystem does not mutate combat or campaign state.
- The subsystem produces a canonical `CharacterRecord` that later systems can consume.

## Module Layout
- `shared_types`: canonical schemas for source policy, content records, intents, events, state snapshots, and `CharacterRecord`.
- `rules_engine`: deterministic RNG, 27-point-buy validation, 4d6 keep-highest-3 rolling, and mirror-backed 5etools normalization/filtering.
- `character_creation`: guided creation state machine and final record compilation.
- `player_interface`: deterministic slash-command parser and presentation helpers.

## Mirror Source
- Runtime content is loaded from `FIVEETOOLS_MIRROR_BASE_URL` in `.env`.
- The default base URL is `https://5e.kiwee.top/`.
- Loader requests are built relative to that base URL, so the kernel links to the configured 5etools mirror instead of copying a repo fixture.
- The loader supports remote HTTP(S) mirrors and local `file://` URLs for explicit overrides.
- Manual user-path testing uses the configured mirror directly, with no embedded fallback dataset.

## 2024 Enforcement
- The active default policy allows only `XPHB` records.
- Mirror records are normalized and filtered before they are shown to the player.
- If the configured mirror cannot supply official 2024 species, classes, and backgrounds, the loader raises a `ContentLoadError` instead of falling back to 2014 content.
- Homebrew remains rejected by default.

## Authority Model
All state changes follow the same path:
1. Slash command or direct caller builds a typed intent.
2. The kernel validates the intent against the DM policy, current phase, and allowed content.
3. The kernel emits typed events.
4. Events are applied to the creation state.
5. `CharacterRecord` is compiled only from committed state.

This preserves the project invariant that mechanics/state mutation happen in deterministic code rather than freeform text.

## Policy Model
The DM policy governs:
- allowed rules sources
- 2024-only enforcement
- homebrew allowance, default `false`
- ability-generation mode
- class wealth-buy allowance
- allowed item purchasing sources

Player-visible options are always filtered through that policy first.

## Guided Flow
The implemented guided flow is:
1. Begin creation.
2. Choose species.
3. Choose class.
4. Choose class skills from an explicit option list.
5. Choose background.
6. Generate ability scores by the policy-approved method.
7. Assign the generated scores to `STR/DEX/CON/INT/WIS/CHA`.
8. Apply 2024 background ASI from explicit legal options.
9. Choose background package or gold.
10. Choose class package or wealth, if the policy allows wealth.
11. Buy allowed items from the remaining budget.
12. Confirm and compile a level-1 `CharacterRecord`.

## Determinism
- Randomness comes only from the rules engine helpers.
- Rolls are seeded from `DND_DETERMINISTIC_SEED` in `.env`.
- Roll events record the consumed random counter and full 4d6 breakdowns.
- Class wealth uses the same deterministic seed path when the DM policy allows wealth-buy.

## Verification
Current verification covers:
- production-mirror loading from `https://5e.kiwee.top/` with no embedded fallback dataset
- production-data tests that build the kernel from the configured mirror and complete a real slash-command creation flow
- compile verification across `shared_types`, `rules_engine`, `character_creation`, `player_interface`, `tests`, and `user-test`
- a real user-path manual harness run through `/create confirm` against the configured mirror

## Encounter Runtime

### Purpose
The repository now also includes a deterministic single-encounter runtime slice that consumes canonical player `CharacterRecord` output from the character-creation subsystem and monster/spell content from the configured 5etools mirror.

### Boundary
- The encounter runtime does not perform DM narration or NPC dialogue.
- The encounter runtime does not ingest campaign text or manage multiplayer synchronization yet.
- The encounter runtime is authoritative for the implemented mechanical slice only: initiative, turn order, movement, dash, dodge, attacks, one supported spell flow, HP changes, and encounter completion.

### Module Layout
- `shared_types/encounter_models.py`: encounter content records, runtime actor state, snapshots, and policy.
- `shared_types/encounter_intents.py`: typed encounter intents.
- `shared_types/encounter_events.py`: typed encounter events.
- `rules_engine/encounter_loader.py`: mirror-backed monster and spell normalization.
- `encounter_runtime/compiler.py`: compiles player characters and monsters into runtime actor state.
- `encounter_runtime/kernel.py`: deterministic intent validation, event generation, and event application.
- `player_interface/encounter_commands.py`: slash-command surface for user-facing interaction.

### Source Policy
- Encounter content is loaded from `FIVEETOOLS_MIRROR_BASE_URL` and currently defaults to `https://5e.kiwee.top/`.
- Legacy `PHB` content is excluded.
- Homebrew and third-party content are rejected.
- Official first-party extension monster and spell sources are allowed.

### Supported Mechanical Slice
1. Load a `CharacterRecord` and compile it into a player runtime actor.
2. Load normalized monsters from the configured bestiary mirror and compile them into monster runtime actors.
3. Start an encounter with deterministic initiative rolls from the shared seed.
4. Resolve movement using grid distance and remaining speed.
5. Resolve `Dash` and `Dodge` as deterministic basic actions.
6. Resolve attacks with deterministic d20 and damage rolls, AC checks, HP updates, and encounter completion checks.
7. Resolve one explicit simple spell flow: `Misty Step` teleport with bonus-action usage and remaining-use tracking.
8. Advance turn order and round count deterministically.

### Verification
The encounter runtime is verified with production-data tests against the configured mirror and a direct user-style manual harness in `user-test/encounter_manual_test.py`.

## Monster Runtime

### Purpose
The repository now includes a standalone monster data pipeline and monster runtime service that loads official monster and supported spell data from the configured 5etools mirror and compiles monsters or player records into shared runtime actor state.

### Boundary
- The monster runtime does not start encounters by itself.
- The monster runtime does not perform narration or freeform interpretation.
- The monster runtime is responsible for content loading, policy filtering, inspection, and deterministic actor compilation only.

### Module Layout
- `rules_engine/monster_loader.py`: mirror-backed monster and supported-spell normalization.
- `monster_runtime/compiler.py`: runtime actor compilation for monsters and players.
- `monster_runtime/service.py`: direct list, inspect, and compile APIs used by both manual tests and the encounter runtime.
- `player_interface/monster_commands.py`: deterministic command surface for monster inspection and compilation.

### Source Policy
- Content is loaded from `FIVEETOOLS_MIRROR_BASE_URL`, which defaults to `https://5e.kiwee.top/`.
- Legacy `PHB`, homebrew, and third-party monster content are excluded.
- Official first-party extension sources remain allowed.

### Downstream Use
The encounter runtime now depends on this monster runtime service instead of loading monsters directly. This keeps the monster pipeline independently testable while preserving a single shared runtime actor model for state-based encounter flow.
