# Lessons

## 2026-04-01
- Pattern: When the user specifies an upstream D&D rules database, do not preserve a local runtime fixture as the source of truth.
- Rule: Character-creation runtime data must link through the configured mirror base URL and fail explicitly if that mirror cannot satisfy the active 2024 policy.
- Pattern: Do not assume the production 5etools mirror serves the same JSON shape or 2024 coverage as a local fixture.
- Rule: Manual user-test harnesses and verification code must use the production mirror directly, and loader parsing must match the live mirror shape exactly while failing closed when `XPHB` content is absent.
- Pattern: Do not debug around an assumed source problem until the premise has been checked against the real environment.
- Rule: Before changing runtime source strategy, verify that the configured or proposed mirror actually exists, inspect its file layout, and bind the subsystem to the verified source rather than an assumed remote endpoint.

## 2026-04-02
- Pattern: When the user asks for a staged subsystem build, do not collapse multiple layers into one delivery just because the code paths are related.
- Rule: Build and verify the monster data pipeline as a standalone first-class subsystem before presenting the broader encounter runtime as the primary result.
- Pattern: When the user asks for system-owned turn and reaction handling, do not stop at exposing raw reaction windows plus a manual slash command.
- Rule: Keep the rules engine as the authority for triggers and legality, but add a separate control/orchestration layer that routes prompts to DM/player controllers and resolves them without making `/react` the primary interaction path.
- Pattern: If a client UI shows numbered legal choices for a server-owned option set, do not send the display index back as if it were the canonical option id.
- Rule: Client-side prompt handlers must preserve the real option ids from the server and translate numeric user selections to those ids before submission.
- Pattern: When writing PowerShell launcher scripts, do not use reserved automatic variables like `$Host` as parameter names.
- Rule: PowerShell manual-test wrappers must avoid read-only built-in variable names and use explicit names such as `$BindHost` for connection parameters.
- Pattern: Fake-transport tests are not enough for a user-provided LLM endpoint that claims OpenAI compatibility.
- Rule: Before declaring a live LLM integration working, send at least one real request to the configured endpoint, inspect the exact validation error body, and align the client payload and response parsing to the server's actual contract.
- Pattern: Reasoning-capable models may still return semantically correct values using full names or near-synonyms even when prompted with exact schema enums.
- Rule: At the LLM boundary, canonicalize only a small explicit set of safe schema aliases (for example `DEXTERITY` -> `DEX`, `private` -> `dm_only`) before typed validation, rather than letting live play fail on predictable formatting variants.

- Pattern: When a reasoning model repeatedly misses a strict JSON schema, do not retry with a vague "invalid JSON" message and hope it self-corrects.
- Rule: LLM retry prompts must include the exact parse or validation failure plus a concrete JSON template so the model can repair the specific structural error instead of hallucinating a new one.
- Pattern: A generic `/check` prompt is not enough in live play if the player cannot see what to roll against or whether the check is opposed.
- Rule: Every player-facing check prompt must state the check type, DC, and competition/opposed target whenever the check interacts with another actor.

- Pattern: If the rules engine already resolves a storytelling check, do not leave that authority implicit in the DM prompt or the player-facing session view.
- Rule: Storytelling checks must be rolled by the deterministic rules engine first, then the finalized result must be passed to the LLM only for interpretation and shown back to the player with the check type and DC.

- Pattern: A bounded retry loop is still opaque to users if the UI never shows that the system is retrying after a schema failure.
- Rule: When the DM runtime retries an LLM response after a validation error, surface each retry attempt and its error reason through the existing controller feedback channel so live users can distinguish a retry from a hang.

- Pattern: If a mode-switch payload is structurally incomplete, do not let it escape the LLM boundary and fail later during session-state application.
- Rule: `enter_combat` and `exit_combat` decisions must be validated for their required plan objects inside the DM-runtime parser so invalid LLM output is retried instead of surfacing as a session-time runtime error.

- Pattern: Smooth story-to-combat transitions fail if the LLM sees only a top-level schema and does not have authoritative actor ids for initiative participants.
- Rule: Storytelling and check-outcome prompts must include strict nested mode-switch templates plus the full authoritative combatant actor roster whenever the model may need to enter combat.

- Pattern: If DM memory files reuse the same markdown ids as canonical scene files, retrieval can silently overwrite the real scene doc and make the storytelling runtime miss critical scene-transition guidance.
- Rule: DM `scene_state` markdown must use distinct `scene-state-*` ids, and storytelling retrieval must keep the current scene's linked next-scene docs in context so bridge scenes can transition cleanly into combat scenes.
- Pattern: If the story-demo view renderer ignores `available_choices`, combat can be mechanically legal while players and the DM still cannot see what they can do.
- Rule: Any story-mode wrapper around the encounter session must render `available_choices` in combat mode exactly like the encounter presenter, so active controllers always see legal actions and attacks.

- Pattern: A pending-check guard is not enough if the LLM can immediately request another check for the same player after the first one resolves in the same scene.
- Rule: The storytelling runtime must enforce at most one DM-issued story check per actor per scene, pass that constraint into the LLM context, and reject repeated same-scene `check_request` output at the LLM boundary so it retries instead of surfacing duplicate checks.

- Pattern: In storytelling mode, a DM-issued check for a different player than the one who just acted can deadlock the demo and confuse the active controller.
- Rule: Story-turn check requests must target only the acting actor, and any pending-check wait state must be surfaced before the story log so blocked controllers can immediately see who the session is waiting on.

## 2026-04-05
- Pattern: When the user asks for a playable manual demo flow, do not promote demo-specific orchestration into a reusable core `session_server` session type unless they explicitly want productized runtime architecture.
- Rule: Character-creation-first demo flows that exist only to be launched from `user-test/full-story-demo` must live in the manual harness path and reuse core systems, not add a new top-level demo session module under `session_server`.
- Pattern: If a story or DM-issued skill check total looks too low, do not debug the DM runtime first when the rules engine already owns check math.
- Rule: Ability-check resolution must use compiled `skill_bonuses` whenever `skill_name` is present; bare `ability_modifiers` are only correct for non-skill ability checks.

## 2026-04-07


- Pattern: If multiple LLM prompt builders each hand-roll their own JSON-only wording, fence/prose failures keep recurring even when `response_format=json_object` is already set.
- Rule: Centralize one shared bare-JSON contract for all LLM prompt and retry instructions, and explicitly require the first non-whitespace character to be `{`, the last to be `}`, and no ```json / ``` wrappers or surrounding prose.

- Pattern: If class creation only normalizes proficiencies and spellcasting, mandatory level-1 class-feature option groups can disappear even though the mirror exposes them in `classFeature` data.
- Rule: When auditing or extending 2024 character creation, always scan level-1 class features for `options` blocks and normalize them into the same pending-choice system as class spells, feats, and other creation-time selections.
- Pattern: If the web character card shows derived combat stats like AC, do not try to fix the UI projection before checking whether the runtime actually owns explicit equipped state.
- Rule: Character-card combat stats must be derived from authoritative runtime equipment slots, and starter inventory that should count mechanically must be compiled into those slots rather than inferred from backpack contents in the frontend.
- Pattern: A web creation-helper feature is incomplete if it only appears after `/create begin` and the manual demo's initial `not-started` state still projects no creation actions.
- Rule: When improving the browser creation flow, verify the actual `user-test/web_story_demo_server.py` launch path from the initial join state and ensure the first required command, including `/create begin`, is projected into the action panel.
- Pattern: When story-mode exploration procedures are meant to feel like play conversation, do not expose them primarily as player-facing slash commands that bypass the normal declaration and pending-check loop.
- Rule: Social, trap, and puzzle procedures must trigger from natural storytelling declarations first, route through typed backend procedure state, and use the standard story `/check` prompt when a roll is required; only downtime remains primarily slash-driven, and it must provide a help path.

## 2026-04-07
- Pattern: Story-mode spell casts that look like utility cantrips still need deterministic backend validation and a hard separation between the casting act and any DM reaction loop.
- Rule: For off-battle cantrips, bypass witness-reaction planning when the spell is intrinsically private or utility-only (for example Message) and keep the validation path inside the spell-specific story resolver.
- Pattern: Equipment/effect recomputation must never assume every actor has an explicit cached unarmed-strike attack profile.
- Rule: When refreshing actor equipment or active-effect state, use a safe authoritative fallback attack profile instead of indexing ctor.attacks['unarmed-strike'] directly.



- Pattern: When a runtime spell implementation changes execution mode, do not leave item metadata and support manifests on stale defaults.
- Rule: Update the per-item metadata, implementation descriptors, and support matrix together so the repo truth matches the actual runtime support and test coverage.

- Pattern: When auditing content folders from a manifest, implementation paths are often relative to the content root, not the repository root.
- Rule: Resolve cantrip content-folder checks from `content/xphb` when the manifest stores `cantrips/<slug>` paths, and keep the folder audit test aligned with that convention.
- Pattern: A cantrip capability loader test should distinguish deterministic runtime support from story-adjudicated utility cantrips instead of forcing every cantrip through the same capability class.
- Rule: Assert the expected runtime support mode per cantrip family so manifest drift and loader drift fail for the right reason.


## 2026-04-08

- Pattern: A content support matrix can claim a spell family is covered while the repo still lacks one-file-per-item behavioral tests.
- Rule: For XPHB cantrip or spell rollout work, do not treat manifest coverage as sufficient until each item has its own test module with multiple usage cases that run through the authoritative backend.
- Pattern: A cantrip "miss" test can still hit if the attacker bonus is left artificially high from the hit-path setup.
- Rule: For miss-path coverage, explicitly lower the attacker attack bonus or use the appropriate save DC path so the test actually exercises the miss branch.
- Pattern: Frozen runtime sub-objects such as dying state cannot be mutated in place.
- Rule: When a dataclass is frozen, replace the nested object with `dataclasses.replace(...)` rather than assigning to its fields directly.
## 2026-04-08
- Pattern: Some story-mode spells still require runtime actors as targets unless the hostile-escalation detector is explicitly neutralized.
- Rule: When writing story-mode spell tests for control spells like Charm Person, target a real runtime actor or override the hostile-escalation detector in the fixture; do not assume scene NPC ids are always castable targets in the current runtime.



- Pattern: A spell that creates a helper, servant, familiar, or disk is not complete if it only exists as passive effect metadata.
- Rule: Persistent spell-created companions and objects must create linked runtime actors when the rules need positioning, controller ownership, initiative participation, mounted/follow movement, or death/effect cleanup, and those lifecycle edges must be covered by dedicated spell tests.

- Pattern: A helper-spell implementation can look complete in runtime state while still missing the player-visible control and perception path.
- Rule: For spells like Find Familiar, Identify, and Tenser's Floating Disk, do not call the slice done until the user-facing commands, controller projection behavior, and dedicated spell tests verify the runtime feature end to end.

## 2026-04-13
- Pattern: Runtime blocker notes for owned content can go stale when shared primitives land in parallel.
- Rule: Before leaving an owned spell blocked, re-check the current shared capability/runtime code against the exact local XPHB text and narrow the blocker to the remaining concrete mechanic gap instead of trusting older notes.

## 2026-04-17
- Pattern: A live web automation runner for real LLM-backed story turns cannot assume a sub-minute HTTP round-trip just because browser feedback is already streaming.
- Rule: User-test automation clients that inject story commands through the web server must use a configurable long request timeout, and the default must safely exceed normal LLM turn latency instead of failing at 60 seconds while the server is still processing a valid turn.
- Pattern: A live browser combat script is brittle if it hardcodes enemy ids and assumes the same target survival order every run.
- Rule: User-test live-web combat scripts must resolve targets from the current projected combat view and gate commands on live runtime state instead of assuming a fixed damage seed or exact enemy survivorship.
- Pattern: Demo pacing becomes unusable if one global delay also slows character creation and setup.
- Rule: Scripted browser demo delays must be applied explicitly to the relevant combat steps only; setup and character creation should stay immediate unless the user asks otherwise.
