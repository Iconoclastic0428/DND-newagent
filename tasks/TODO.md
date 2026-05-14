## 2026-05-13 - Combined Dataset ID Namespacing

### Scope
- Fix the real readiness blocker found after running the baseline benchmark and collector.
- Namespace combined dataset row IDs so repeated per-batch episode IDs do not collide across seeds or policies.
- Keep readiness focused on combined collection outputs when a collection report is present, while still reading benchmark history from benchmark roots.
- Preserve generated run artifacts and unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this follow-up.

### Steps
- [x] Run baseline benchmark, collect datasets, and inspect readiness/quality failures.
- [x] Add source-batch namespacing to combined transition and preference rows.
- [x] Filter readiness dataset summaries to collection outputs when collection reports are present.
- [x] Add focused regression tests for duplicate IDs and benchmark-root manifest noise.
- [x] Run focused verification and regenerate local readiness artifacts.
- [x] Commit and push to `origin/newdndagents`.

### Verification Plan
- `python -m py_compile training\dataset_collection.py training\readiness_report.py tests\test_dataset_collection.py tests\test_training_readiness.py`
- `python -m unittest tests.test_dataset_collection tests.test_training_readiness tests.test_dataset_quality -v`
- `python user-test\collect_training_datasets.py --input runs\benchmarks --output-dir runs\datasets\latest`
- `python user-test\report_training_readiness.py --input runs\datasets\latest --input runs\benchmarks --output-json runs\datasets\latest\training_readiness.json --output-md runs\datasets\latest\training_readiness.md`
- `git diff --check -- training\dataset_collection.py training\readiness_report.py tests\test_dataset_collection.py tests\test_training_readiness.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Root cause: per-batch episode-local IDs repeat across seeds, so concatenation created duplicate `sample_id` and `pair_id` values.
- Combined dataset rows now get source namespaces from benchmark id and batch id. Transition rows update `sample_id`; preference rows update `pair_id`, `chosen_sample_id`, and `rejected_sample_id`; both dataset types record `source_batch_id`.
- Readiness reports now summarize collection outputs when collection reports are present, so benchmark roots can be included for history without pulling every raw per-batch manifest into the dataset table.
- Verification passed:
  - `python -m py_compile training\dataset_collection.py training\readiness_report.py tests\test_dataset_collection.py tests\test_training_readiness.py`
  - `python -m unittest tests.test_dataset_collection tests.test_training_readiness tests.test_dataset_quality -v` passed 11 tests.
  - `python user-test\collect_training_datasets.py --input runs\benchmarks --output-dir runs\datasets\latest` regenerated combined datasets with transition quality `pass` and preference quality `warn`.
  - `python user-test\report_training_readiness.py --input runs\datasets\latest --input runs\benchmarks --output-json runs\datasets\latest\training_readiness.json --output-md runs\datasets\latest\training_readiness.md` returned status `needs_attention` with 0 blockers and 1 warning.

## 2026-05-13 - Training Readiness Report

### Scope
- Add a lightweight report that summarizes whether collected benchmark datasets are ready for model training.
- Combine dataset manifests, dataset quality reports, collection reports, and benchmark history into one JSON/Markdown status.
- Keep the report deterministic and local-only; do not invoke external APIs or infer training quality beyond the recorded artifacts.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only the files changed for this task.

### Steps
- [x] Review current dataset manifest, collection, quality, and benchmark-history structures.
- [x] Add a `training` module that discovers and summarizes readiness artifacts.
- [x] Add a `user-test` CLI wrapper for JSON and Markdown output.
- [x] Add focused tests for ready, warning, and blocking states.
- [x] Document the command in `README.md`.
- [x] Run focused verification and inspect the git diff.
- [x] Commit and push to `origin/newdndagents`.

### Verification Plan
- `python -m py_compile training\readiness_report.py user-test\report_training_readiness.py tests\test_training_readiness.py`
- `python -m unittest tests.test_training_readiness tests.test_dataset_quality tests.test_dataset_collection -v`
- `git diff --check -- README.md training\readiness_report.py user-test\report_training_readiness.py tests\test_training_readiness.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Added deterministic readiness reporting in `training/readiness_report.py`.
- Added `user-test/report_training_readiness.py` for JSON and Markdown report output.
- Readiness status is `blocked` for failed quality checks, missing dataset files, missing manifests, or empty datasets; `needs_attention` for missing quality reports, quality warnings, or missing benchmark history; and `ready` only when the artifact set is clean.
- Documented the command in `README.md`.
- Verification passed:
  - `python -m py_compile training\readiness_report.py user-test\report_training_readiness.py tests\test_training_readiness.py`
  - `python -m unittest tests.test_training_readiness tests.test_dataset_quality tests.test_dataset_collection -v` passed 10 tests.
  - `git diff --check -- README.md training\readiness_report.py user-test\report_training_readiness.py tests\test_training_readiness.py tasks\TODO.md tasks\SUMMARIES.md`

## 2026-05-08 - Merge GitHub DnD-Agent Branch

### Scope
- Pull the current GitHub branch tracked by this worktree (`elijah/dnd-newagent-migration`) into the local branch.
- Preserve and integrate upstream minor-bug fixes when present:
  - README/web-page operation docs.
  - Ability assignment command hints and attribute order.
  - Multi-select character-creation prompts.
  - `/create confirm` item-finish command hint.
  - Character load/save support.
  - LLM acting as player or monster.
  - Alternate LLM provider/model configuration.
- Preserve local bug fixes already in this worktree, including web UI chat ordering, runtime stabilization, and server-authoritative boundaries.
- Resolve conflicts directly without reverting unrelated user/runtime files.
- Verify the merged branch and push it back to GitHub.

### Steps
- [x] Review lessons and inspect branch/remotes/worktree.
- [x] Fetch the tracked GitHub branch and inspect incoming commits/files.
- [x] Safeguard local uncommitted changes before merging.
- [x] Merge/pull the remote branch and resolve conflicts.
- [x] Review the listed feature areas after conflict resolution.
- [x] Run focused compile/unit/web verification.
- [x] Push the resolved branch to GitHub.
- [x] Record review notes and append a summary to `tasks/SUMMARIES.md`.

### Verification Plan
- `git status --short --branch` before and after merge.
- Focused compile checks for touched Python modules.
- Character-creation, web-server, and LLM/client tests based on changed files.
- Frontend syntax checks for touched JS files.
- `git diff --check`.

### Review
- Fetch found the listed upstream fixes on `elijah/newdndagents` (`180f317`, `a42923d`, `73c31b5`, `cd80c42`), which is based on the local branch tip `326d5d3`.
- Local code/test/frontend fixes were committed first as `c7d3755` so the remote feature branch can be merged with a normal three-way merge. Dirty campaign memory files were left unstaged.
- Merged `elijah/newdndagents` cleanly; no textual conflict markers were produced.
- Reviewed the merged feature areas: README/web usage docs, ability assignment and multi-select command hints, `/create confirm` prompt, party save/load, relative mirror-path support, local deterministic LLM transport for browser verification, and alternate LLM API format docs/tests are present.
- Fixed one real post-merge regression in new tests: three merged test modules pointed at a repo-local `5etools-mirror-2.github.io` directory that does not exist in this workspace. They now use the shared verified `tests.test_encounter_kernel.LOCAL_MIRROR_BASE_URL` test mirror path, while runtime/docs still support explicit relative mirror paths.
- Verification passed:
  - `python -m py_compile character_creation\kernel_v2.py character_creation\service.py monster_runtime\service.py rules_engine\fiveetools_loader.py session_server\web_projection.py shared_types\character_record_io.py user-test\story_demo_system_server.py user-test\web_story_demo_server.py tests\test_character_creation_kernel.py tests\test_character_record_io.py tests\test_fiveetools_loader.py tests\test_full_story_demo_session.py tests\test_web_server.py tests\test_web_frontend_chat.py`
  - `node --check web_frontend\app.js`
  - `node --check web_frontend\chat_state.js`
  - `python -m unittest tests.test_character_creation_kernel tests.test_character_record_io tests.test_fiveetools_loader tests.test_full_story_demo_session tests.test_web_frontend_chat tests.test_web_server tests.test_dm_runtime -v` passed 75 tests.
  - `git diff --check` passed with only line-ending warnings.
- Pushed resolved commits to `elijah/dnd-newagent-migration`. GitHub reported that branch had been renamed to `newdndagents`, so the same resolved HEAD was also fast-forward pushed to `elijah/newdndagents`.

## 2026-05-07 - Web UI Thinking Row Ordering Fix

### Scope
- Fix the browser chat ordering bug where a transient `DM is thinking`/LLM feedback row can remain below the newest authoritative LLM narration.
- Keep the server-authoritative transcript as the source of truth; local browser feedback must not reorder or obscure committed chat entries.
- Do not add fallback behavior. The UI should discard stale transient feedback once a newer authoritative view arrives.

### Steps
- [x] Review lessons and locate the frontend chat render/message path.
- [x] Confirm the root cause in the local-entry merge behavior.
- [x] Patch the frontend to expire stale `thinking` entries when authoritative chat advances.
- [x] Add or update focused regression coverage for the UI behavior.
- [x] Run focused static/server tests and record results.
- [x] Append a concise request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- Frontend syntax/static check for `web_frontend/app.js`.
- Focused test covering that stale thinking feedback is removed after a newer authoritative chat entry appears.
- `python -m unittest tests.test_web_server -v`.

### Review
- Root cause: `web_frontend/app.js` treated websocket `thinking` feedback as a normal local chat entry and always merged local entries after `view.chat_entries`. When the LLM completed, the authoritative transcript contained the latest narration, but the stale local thinking row still rendered below it until refresh cleared browser-local state.
- Fix: moved chat-feed merge logic into `web_frontend/chat_state.js`. Local entries now remember the authoritative chat generation they were created against, and stale `thinking` entries are removed as soon as a newer authoritative transcript arrives. This preserves pending feedback while the LLM is working without letting it sit below committed narration.
- Static/server coverage:
  - `node --check web_frontend\app.js` passed.
  - `node --check web_frontend\chat_state.js` passed.
  - `python -m unittest tests.test_web_frontend_chat -v` passed 2 tests.
  - `python -m unittest tests.test_web_server.SessionWebServerTests.test_config_and_static_assets_do_not_leak_llm_secrets -v` passed.
  - `python -m unittest tests.test_web_server -v` passed 21 tests.
  - `git diff --check -- web_frontend\app.js web_frontend\chat_state.js tests\test_web_frontend_chat.py tests\test_web_server.py tasks\TODO.md` passed with only line-ending warnings.

## 2026-05-07 - Whole-Code Structure Stabilization Loop

### Scope
- Review the repository structure end to end with emphasis on the current web UI demo path.
- Use automated tests, compile checks, command-line smoke checks, and web UI/server verification to find concrete defects.
- Fix root causes directly; do not add fallback logic that hides errors.
- Repeat the find/fix/verify loop until the available checks stop surfacing new bugs.
- Preserve the DM-agent vs rules-engine authority boundary, server-authoritative state, typed intent flow, and visibility separation.

### Steps
- [x] Review local instructions and lessons before changing code.
- [x] Map top-level modules, test suites, web UI entrypoints, and current git state.
- [x] Run broad compile/unit discovery to establish the first failure set.
- [x] Run the web UI demo path or an equivalent local server/browser smoke path and inspect logs/output.
- [x] Classify each failure as a real bug, test drift, environment issue, or acceptable explicit error.
- [x] Fix confirmed bugs with minimal root-cause changes.
- [x] Re-run the relevant tests and web UI checks after each fix batch.
- [x] Repeat the loop until no new confirmed defects appear in the selected verification surface.
- [x] Add a review section with commands, observed results, remaining gaps, and confidence boundary.
- [x] Append a concise request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- `python -m py_compile` over changed Python files and any modules implicated by failures.
- `python -m unittest discover -s tests -v` unless the suite is too slow or blocked, then focused failing suites plus documented blocker.
- Focused user-test/web demo checks for `user-test/web_story_demo_server.py` and `session_server/web_server.py`.
- Frontend static asset sanity checks and browser/web smoke checks where the server can start locally.
- `git diff --check`.

### Review
- Reviewed the top-level module layout, current web UI entrypoint (`user-test/web_story_demo_server.py`), and current git state. The campaign DM memory files under `campaigns/lmop/dm/...` were already dirty and were not reverted.
- Fixed confirmed runtime defects:
  - `rules_engine/monster_loader.py`: True Strike no longer gets a duplicate generic material-component requirement; the selected weapon is validated by the spell capability.
  - `shared_types/capabilities.py` and `encounter_runtime/effect_execution.py`: group save definitions and target-radius save execution now carry the parameters expected by level-1 spell executors.
  - `encounter_runtime/consumers.py`: hazard damage resolution now calls `_damage_preview` with encounter state and applies generated damage-reduction effect events.
  - `session_server/storytelling_session.py`: social consequences and DM-only propagation/projection status are visible in controller/web summaries with public vs DM-only filtering preserved.
  - `session_server/orchestrator.py`: socket prompt replay now serializes string trigger types correctly and treats client resets as disconnects.
  - `session_server/web_server.py`: normal websocket close no longer prints the third-party close-state assertion trace.
- Updated stale tests to match explicit current mechanics instead of adding fallbacks: custom non-wizard records no longer inherit wizard spell selections; item capabilities disappear when consumed inventory reaches zero; recharge and death-save timing queues are continued explicitly; critical-hit damage tests decline the reaction window before asserting damage.
- Verification:
  - `python -m compileall -q campaign_ingestion character_creation dm_agent encounter_runtime monster_runtime player_interface rules_engine session_server shared_types tests user-test` passed; it still reports stale `.tmp` listing notices for missing old temp directories.
  - `python -m unittest discover -s tests\xphb_cantrips -v` passed 102 tests.
  - `python -m unittest discover -s tests\xphb_level1_spells -v` passed 280 tests.
  - `python -m unittest discover -s tests\xphb_level1_class_features -v` passed 100 tests.
  - `python -m unittest tests.test_tier2_level2_spell_suite tests.test_tier2_level2_spell_completeness -v` passed 94 tests.
  - Broad explicit module batch from `tests.test_adjudication_runtime` through `tests.test_xphb_rollout_manifest` passed 530 tests after the fix loop.
  - `python -m unittest tests.test_web_server -v` passed 21 tests with the websocket close trace removed.
  - Actual launcher smoke for `user-test/web_story_demo_server.py` passed: HTTP `/` 200, `/config.json` 200, websocket join returned `joined` then `view`, runtime mode `storytelling`, controller count 5.
  - `git diff --check` passed with only Git line-ending warnings.
- Confidence boundary: I am not claiming mathematically "all bugs" are gone. I am confident across the selected verification surface: compile, XPHB cantrip/level-1/level-2 suites, major top-level module tests, web server tests, and a launcher-level web UI smoke. The single monolithic `python -m unittest discover -s tests -v` run is still impractical in one pass because it previously exceeded a 600 second timeout before completing generated content coverage, so verification used split and explicit broad suites.

## 2026-05-05 - DeepSeek JSON Output Hardening

### Scope
- Harden DeepSeek JSON-only requests so the final assistant content is much less likely to include markdown wrappers, prose, hidden-thinking tags, comments, or non-JSON tokens.
- Keep the change at the LLM boundary and shared JSON contract rather than duplicating wording inside every DM prompt builder.
- Preserve fail-closed behavior: invalid JSON should still retry through the existing deterministic parser/validation loop instead of being silently cleaned up.
- Verify with focused unit tests and at least one live DeepSeek JSON request that does not include repo campaign content.

### Design Direction
- Strengthen `dm_agent/json_contract.py` so runtime/adjudication prompts tell the model to think internally, self-check strict JSON validity, avoid wrapper tokens, and expect parser/GPT-style review.
- Add DeepSeek chat-completions hardening in `dm_agent/client.py` whenever `response_format={"type":"json_object"}` is requested, because not every caller necessarily uses the DM JSON contract helper.
- For DeepSeek V4 models, request `thinking={"type":"enabled"}` and `reasoning_effort="high"` on JSON requests, matching DeepSeek's official chat API shape.

### Steps
- [x] Update shared JSON-only and retry contracts.
- [x] Add DeepSeek chat JSON hardening and reasoning parameters in the client payload.
- [x] Extend focused tests for prompt text and DeepSeek chat-completions payloads.
- [x] Run compile/unit verification.
- [x] Run a live minimal DeepSeek JSON request through the configured `.env`.
- [x] Record review notes and append the request summary.

### Verification Plan
- `python -m py_compile dm_agent\json_contract.py dm_agent\client.py tests\test_dm_runtime.py`
- `python -m unittest tests.test_dm_runtime -v`
- Live DeepSeek request using a minimal synthetic prompt, expecting parseable bare JSON with no wrapper/prose.

### Review
- Strengthened the shared JSON-only contract in `dm_agent/json_contract.py` so every DM runtime/adjudication JSON prompt now explicitly requires internal careful checking, deterministic parser/GPT-verifier review, no wrapper keys, and no non-JSON token classes such as markdown fences, `<think>` blocks, YAML/comments, BOM/zero-width characters, Python literals, NaN/Infinity, single quotes, control characters, or trailing commas.
- Added client-level DeepSeek JSON hardening in `dm_agent/client.py` for chat-completions requests with `response_format={"type":"json_object"}`. This protects callers that request JSON but do not use the shared prompt helper.
- DeepSeek V4 JSON requests now include `thinking={"type":"enabled"}` and `reasoning_effort="high"` while still keeping the final assistant content as bare JSON only.
- Kept invalid-output handling fail-closed: no wrapper stripping or JSON repair was added. Bad JSON still goes through the existing deterministic parser error and bounded retry loop.
- Verification:
  - `python -m py_compile dm_agent\json_contract.py dm_agent\client.py tests\test_dm_runtime.py` passed.
  - `python -m unittest tests.test_dm_runtime -v` passed 26 tests.
  - Live minimal DeepSeek request through `.env` parsed successfully as bare JSON and reported first character `{`, last character `}`, keys `invalid_token_count`, `model`, `ok`, `provider`, `wrapper_free`, `wrapper_free=true`, and `invalid_token_count=0`.

## 2026-05-05 - DeepSeek V4 LLM Config

### Scope
- Update the local `.env` LLM endpoint/model from the old NRP endpoint to DeepSeek V4.
- Preserve the secret key without printing it.
- Align the repo's LLM client with DeepSeek's official Chat Completions API shape.
- Prove the configured LLM works with a real request before declaring done.

### Design Direction
- Official DeepSeek docs list OpenAI-format `base_url` as `https://api.deepseek.com`.
- DeepSeek V4 is selected by model name, with `deepseek-v4-pro` and `deepseek-v4-flash` currently available.
- DeepSeek's OpenAI-compatible invocation uses `/chat/completions`, while the existing repo client defaults to `/responses`; add an explicit `OPENAI_API_FORMAT=chat_completions` mode rather than guessing.

### Steps
- [x] Record DeepSeek V4 config plan.
- [x] Add explicit chat-completions client mode.
- [x] Update `.env` DeepSeek endpoint/model fields.
- [x] Run focused unit tests for config/client behavior.
- [x] Run one live DeepSeek request using the configured `.env`.
- [x] Record verification and append request summary.

### Verification Plan
- `python -m unittest tests.test_dm_runtime -v`
- Live request through `dm_agent` config/client using `.env`, expecting valid JSON response from `deepseek-v4-pro`.

### Review
- `.env` now points at DeepSeek's OpenAI-compatible base URL with `OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_RESPONSES_MODEL=deepseek-v4-pro`, and `OPENAI_API_FORMAT=chat_completions`. The API key was preserved and never printed.
- Added explicit Chat Completions support to the DM LLM client instead of routing DeepSeek through the existing Responses endpoint. The client now posts DeepSeek requests to `/chat/completions`, converts system/input payloads into chat `messages`, maps `max_output_tokens` to `max_tokens`, and supports streamed `reasoning_content` plus output deltas.
- Extended config validation/tests so the default remains `responses`, while DeepSeek can opt into `chat_completions` through `.env`.
- Verification:
  - `python -m py_compile dm_agent\config.py dm_agent\client.py tests\test_dm_runtime.py` passed.
  - `python -m unittest tests.test_dm_runtime -v` passed 25 tests.
  - Live DeepSeek smoke request through the configured `.env` returned valid JSON from `deepseek-v4-pro`: `{"ok":true,"provider":"deepseek","model":"deepseek-v4-pro"}`.
- Note: a broader live DM-runtime request using campaign context was not sent because the escalation policy rejected transmitting repo campaign data to the external DeepSeek API. The local parser/runtime path remains covered by the passing `tests.test_dm_runtime` suite.

## 2026-05-05 - Five-Subagent Character Creation Run

### Scope
- Spawn four player subagents and one DM observer subagent for a character-creation smoke run.
- Use the authoritative full-story demo wrapper in character-creation mode, not the precreated browser default.
- Replay player-created `/create ...` commands through the real session so validation still belongs to the character-creation/rules path.
- Write a durable log summary under `user-test/full-story-demo/logs/` for review.

### Design Direction
- Subagents can propose player/DM behavior, but the main process will execute commands through `FullStoryDemoManualSession` so the session remains authoritative.
- Keep this as a user-test run artifact, not a reusable runtime subsystem.
- If a proposed command sequence fails, record the validation failure and rerun only a corrected exact sequence rather than adding fallback runtime logic.

### Steps
- [x] Record subagent character-creation run plan.
- [x] Spawn four player agents and one DM observer.
- [x] Replay proposed creation commands through authoritative session.
- [x] Write log summary file.
- [x] Verify the log file exists and update the request summary.

### Verification Plan
- Run an authoritative replay script or inline harness against `build_full_story_demo_manual_session(..., precreate_characters=False)`.
- Confirm all four controllers produce confirmed records and the wrapper hands off to `storytelling`.
- Inspect the generated log summary file.

### Review
- Spawned five subagents:
  - Player 1: Banach, `019dfa5f-bf5b-77c2-b4ce-d8402e1491f9`
  - Player 2: Carson, `019dfa5f-d36e-7a52-800e-851713dfaa71`
  - Player 3: Chandrasekhar, `019dfa5f-e77a-76d3-9f33-10cf778e5e63`
  - Player 4: Dewey, `019dfa5f-fbcc-7842-a2f2-ddc977533571`
  - DM observer: Arendt, `019dfa60-0fee-7202-8b51-be79660d3ee3`
- All four player agents chose the proven default Aasimar Wizard Acolyte command sequence rather than inventing unverified choices.
- Replayed all 64 player `/create` commands through `build_full_story_demo_manual_session(..., precreate_characters=False)`.
- Confirmed the DM observer boundary: `/create begin` from `dm` returned the expected permission error instead of mutating player state.
- Result: PASS. Four confirmed records were created with unique ids `level-1-character-p1` through `level-1-character-p4`, and the wrapper transitioned into `storytelling` at `scene-waterdeep-gundren-briefing`.
- Log summary written to `user-test/full-story-demo/logs/2026-05-05-five-subagent-character-creation.md`.

## 2026-05-05 - Precreate Browser Demo Party

### Scope
- Find the existing default character command sequence and reuse it for the browser full-story demo.
- Make the browser launch start with all four player characters already confirmed.
- Preserve the existing manual character-creation wrapper path unless explicitly opted into precreation.
- Keep the change in the user-test/browser demo bootstrap layer, not in the generic rules engine or DM runtime.

### Design Direction
- `session_server/bootstrap.py::build_default_character_record` is the source of the pre-created character command sequence.
- Add an explicit `precreate_characters` option to `FullStoryDemoManualSession` so the browser server can start story mode immediately while tests/manual paths can still exercise character creation.
- Reuse the existing story-session construction from confirmed records so controller ownership, event authority, and DM-vs-rules boundaries stay unchanged.

### Steps
- [x] Review lessons and locate the browser/manual full-story demo bootstrap path.
- [x] Add precreated-party support to the full-story wrapper using the existing default character builder.
- [x] Switch `user-test/web_story_demo_server.py` to start with precreated characters.
- [x] Update tests/docs/scripts that assume the browser server starts in `character-creation`.
- [x] Run focused compile/unit verification and record results here.

### Verification Plan
- `python -m py_compile user-test\story_demo_system_server.py user-test\web_story_demo_server.py tests\test_full_story_demo_session.py tests\test_web_server.py`
- `python -m unittest tests.test_full_story_demo_session -v`
- `python -m unittest tests.test_web_server -v`

### Review
- The command sequence that creates a ready default character is `session_server/bootstrap.py::build_default_character_record`; it runs the deterministic `/create ...` list and returns a confirmed `CharacterRecord`.
- Added `precreate_characters` to `FullStoryDemoManualSession`, reusing `build_default_character_record` and the existing four-record story-session handoff rather than duplicating character creation logic.
- `user-test/web_story_demo_server.py` now defaults to `precreate_characters=True`, so normal browser startup opens in `storytelling` with all four player actors/cards already present. The old browser creation phase remains available with `--start-in-character-creation`.
- Updated browser docs and the legacy live-web script description so the creation-first script is clearly tied to `--start-in-character-creation`.
- Verification:
  - `python -m py_compile user-test\story_demo_system_server.py user-test\web_story_demo_server.py tests\test_full_story_demo_session.py tests\test_web_server.py` passed.
  - `python -m unittest tests.test_full_story_demo_session -v` passed 4 tests.
  - `python -m unittest tests.test_web_server -v` passed 21 tests; the existing websocket shutdown-time assertion trace still appears, but the suite result is OK.
  - `python -c "import json, pathlib; json.loads(pathlib.Path('user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json').read_text(encoding='utf-8')); print('live-web script json ok')"` passed.
  - `git diff --check -- user-test/story_demo_system_server.py user-test/web_story_demo_server.py tests/test_full_story_demo_session.py tests/test_web_server.py docs/web-frontend.md docs/starter-content-pack.md user-test/full-story-demo/README.md user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json tasks/TODO.md` passed with only Git line-ending warnings.

## 2026-05-04 - XPHB Cantrip And Level-1 Spell Command Usage Docs

### Scope
- Update every per-item README under `content/xphb/cantrips` and `content/xphb/spells/level-1` with explicit slash-command usage.
- Preserve current runtime support truth: supported deterministic/story spells get concrete `/cast` or reaction examples; unsupported or blocked command mechanisms must be called out instead of invented.
- Keep this as documentation-only work. Do not add new spell mechanics, command handlers, or runtime fallback behavior.

### Design Direction
- Standardize a `## Command Usage` section in each README so users can quickly see how to try a spell from the command layer.
- Reuse command examples already proven in per-item tests and existing READMEs wherever available.
- For item folders that only have generic support metadata, document the safest known generic command form from the current `/cast` parser.
- Verify coverage mechanically by checking every cantrip and level-1 spell README has exactly one command usage section and either a supported command or an explicit no-command-support note.

### Steps
- [x] Review `tasks/LESSONS.md`, XPHB skill instructions, branch state, and existing README/metadata patterns.
- [x] Build the command usage map from existing READMEs, tests, parser syntax, and implementation metadata.
- [x] Update all cantrip and level-1 spell READMEs with the standardized command usage section.
- [x] Run documentation consistency checks over all target folders.
- [x] Record verification results here and append a request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- README coverage check for every folder under `content/xphb/cantrips` and `content/xphb/spells/level-1`.
- Duplicate-section check for `## Command Usage`.
- Placeholder/no-support consistency check for command usage sections.
- `git diff --check`.

### Review
- Added a standardized `## Command Usage` section to all 104 target README files under `content/xphb/cantrips` and `content/xphb/spells/level-1`.
- Reused existing README/test command examples where available and filled missing level-1 examples from the current `/cast` parser and per-item tests. Reaction spells now call out the trigger-plus-`/react` flow and warn users to use the concrete option id shown by the active reaction prompt.
- Preserved current support truth in docs: deterministic-capability spells describe authoritative typed `/cast` resolution, story-adjudicated spells describe story-mode spell command handling, and metadata blocker notes explicitly warn not to invent unsupported parameters or edge mechanics.
- Verification:
  - README coverage check over all 104 folders: 0 missing `## Command Usage`, 0 duplicate sections, 0 missing examples, 0 UTF-8 BOM files.
  - `git diff --check` passed.
  - `python -m unittest tests.test_xphb_level1_content_pack -v` passed 7 tests.
  - `python -m unittest tests.test_xphb_cantrip_capability_loader -v` passed 6 tests.

## 2026-05-04 - Push Migration Branch To ElijahZY DnD-Agents

### Scope
- Create a new local migration branch from the current pushed `main` snapshot.
- Add `https://github.com/ElijahZY/DnD-Agents` as a separate remote without changing the existing `origin`.
- Push the same project contents to a new branch in `ElijahZY/DnD-Agents`.

### Design Direction
- Keep `origin` pointed at `Iconoclastic0428/DND-newagent`; use a separate remote name for the second repository.
- Use branch `dnd-newagent-migration` unless the remote already has that branch.
- Re-run ignored-file and staged/branch state checks before pushing so local credentials and generated files remain excluded.

### Steps
- [x] Review `tasks/LESSONS.md` and confirm the current source branch is clean.
- [x] Verify Git access to `ElijahZY/DnD-Agents` and whether the target branch name is available.
- [x] Create the local migration branch from the current source snapshot.
- [x] Configure a separate target remote for `ElijahZY/DnD-Agents`.
- [x] Push the migration branch to the target remote.
- [x] Record verification results here and append a request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- `git status --short --branch`
- `git log --oneline --decorate -3`
- `git check-ignore -v .env .tmp-friendly.env .tmp-unfriendly.env`
- `git ls-remote` or push result against `https://github.com/ElijahZY/DnD-Agents`

### Review
- Confirmed current source state was clean at `64fa74c` before creating the migration branch.
- Verified `https://github.com/ElijahZY/DnD-Agents.git` was reachable with `git -c safe.directory=D:/DND-newagent ls-remote --heads`; existing remote branches were `eval`, `junxia`, `main`, `shengqi`, `xijiajun`, and `ziyizeng`, so `dnd-newagent-migration` was available.
- Created local branch `dnd-newagent-migration`, added separate remote `elijah` pointing at `https://github.com/ElijahZY/DnD-Agents.git`, and pushed the branch with `git -c safe.directory=D:/DND-newagent push -u elijah dnd-newagent-migration`.
- The target remote accepted the new branch and reported PR URL `https://github.com/ElijahZY/DnD-Agents/pull/new/dnd-newagent-migration`.
- No code tests were run because this request only migrated the existing repository snapshot to a second remote branch.

## 2026-05-04 - Initial Git Commit And Remote Push

### Scope
- Initialize Git for `D:\DND-newagent` if needed and connect it to `https://github.com/Iconoclastic0428/DND-newagent`.
- Show the current `.gitignore` before committing and prevent credential-bearing files from being staged.
- Commit the intended project files and push them to the remote repository.

### Design Direction
- Treat `.env` and other local/runtime artifacts as private local state.
- Prefer tightening `.gitignore` before the first commit so accidental secrets and generated files never enter history.
- Use `git status`, ignored-file checks, and a targeted credential-pattern scan before staging.

### Steps
- [x] Review `tasks/LESSONS.md`, show `.gitignore`, and inspect whether the directory is already a Git repository.
- [x] Tighten `.gitignore` for common local secret, cache, virtualenv, editor, and generated-log files.
- [x] Initialize Git and configure the GitHub remote if the repository is still uninitialized.
- [x] Scan candidate tracked files for likely credentials before staging.
- [x] Stage, review status, create the initial commit, and push to `origin`.
- [x] Record verification results here and append a request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- `git status --short --branch`
- `git check-ignore -v .env .tmp-friendly.env .tmp-unfriendly.env`
- Targeted credential-pattern scan over candidate tracked files.
- `git log --oneline -1`
- `git remote -v`

### Review
- Initialized Git on `main`, configured `origin` as `https://github.com/Iconoclastic0428/DND-newagent`, and created the initial source commit `0af9722`.
- Tightened `.gitignore` before the first commit so `.env`, `.env.*`, `*.env` except `.env.example`, caches, virtualenvs, frontend dependency/build output, logs, scratch dirs, root `tmp_*.txt` command files, and IDE/OS files are ignored.
- Verified ignored behavior with `git check-ignore -v .env .tmp-friendly.env .tmp-unfriendly.env tmp_dm_commands.txt tmp_player_illegal_commands.txt tmp_dm.log tmp_system.out .idea`.
- Scanned Git-visible and staged files for credential-like paths and high-risk token signatures; no staged env files, private key paths, logs, cache dirs, dependency folders, or high-risk token signatures were found. Broad keyword hits were reviewed as placeholders, config field names, test literals, or non-secret D&D/UI text.
- The first push initially failed because Windows Git was authenticated as `shl142`, which did not have repository write permission. Git Credential Manager was updated through its normal GitHub login flow, confirmed `Iconoclastic0428` was available, and `git -c safe.directory=D:/DND-newagent push -u origin main` then pushed `main` successfully.
- No code tests were run for this request because the only implementation changes were Git repository initialization, ignore-file hardening, and task documentation.

## 2026-04-17 - Live Four-Subagent Test Run And Transcript Logging

### Scope
- Run the relevant user-test verification for the live web party-connector path.
- Add a durable local transcript path so a live browser-session run can record player moves and visible DM/public responses to disk.
- Use four real spawned Codex subagents as the four player voices for a short live run against the user-test web automation API after character creation is complete.

### Design Direction
- Keep the authoritative runtime unchanged: subagents may only propose player turns, and all execution must still go through the existing automation API surface.
- Add the smallest logging seam that records accepted player actions plus newly visible DM/public chat or prompt events to a local file without changing rules ownership or session authority boundaries.
- Reuse the existing user-test web demo server and automation API. The main agent will orchestrate the spawned player subagents one turn at a time so they do not talk over each other.

### Steps
- [x] Add focused transcript logging support in the user-test live party path and cover it with a unit test.
- [x] Run compile and unit-test verification for the touched user-test/web modules.
- [x] Start the live user-test web demo server for a local automation-driven run.
- [x] Spawn four player subagents with fixed personas, collect their moves sequentially, execute them through the automation API, and save the transcript locally.
- [x] Record the verification and live-run results here, then append the request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
- `python -m unittest tests.test_story_demo_party_connector tests.test_web_server -v`

### Review
- Added transcript logging directly to [user-test/web_story_demo_party_connector.py](/d:/DND-newagent/user-test/web_story_demo_party_connector.py) through the new `PartyTranscriptLogger` plus an optional `--transcript-path` / `transcript_path` seam. The connector now records accepted player actions, DM/system auto-passes, newly visible public or DM-only chat entries, and newly surfaced prompts without changing the authoritative automation flow.
- Expanded [tests/test_story_demo_party_connector.py](/d:/DND-newagent/tests/test_story_demo_party_connector.py) so the fake automation client carries a DM snapshot and public follow-up chat, then added a focused transcript-file test. This keeps the new logging path under unit coverage instead of leaving it as a purely manual feature.
- Verification:
  - `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
  - `python -m unittest tests.test_story_demo_party_connector tests.test_web_server -v`
- Observed results:
  - compile passed
  - `tests.test_story_demo_party_connector` passed 4 tests
  - `tests.test_web_server` passed 20 tests
  - the known websocket shutdown-time `AssertionError` trace still appears in one web test, but the suite passed
- Live subagent run:
  - Spawned four real player subagents with the fixed personas from the connector design, plus one temporary helper agent to hold an in-sandbox server open while I diagnosed process-lifetime issues
  - The sandboxed live DM path could not reach the configured LLM endpoint, so I restarted the live web demo server outside the sandbox on `http://127.0.0.1:8018` and later `http://127.0.0.1:8020`
  - Character creation replay succeeded on the escalated live server, and the first subagent-backed story turn completed end-to-end: Player 1 pressed Gundren for the missing danger, the rules engine issued a Persuasion story check, `/check` resolved as `die 1, total 1 vs DC 14 (failure)`, and the DM state hardened Gundren's stance
  - The next live DM turns became unresponsive past the 180-second command timeout in both escalated sessions. I did not resubmit duplicate player inputs after that point. Instead, I saved the partial real transcripts and the unresolved-turn notes locally at [2026-04-17-subagent-live-run.log](/d:/DND-newagent/user-test/full-story-demo/logs/2026-04-17-subagent-live-run.log) and [2026-04-17-subagent-live-run-8020.log](/d:/DND-newagent/user-test/full-story-demo/logs/2026-04-17-subagent-live-run-8020.log).
- Cleanup:
  - closed the five spawned helper/player agents after the run attempt
  - stopped the escalated live demo server processes after capturing the transcript files

## 2026-04-17 - Four-Player Agent Connector For Live Web Demo

### Scope
- Add a user-test connector that can drive the live web story demo as four autonomous player agents after character creation finishes.
- Keep the authoritative session flow unchanged: the connector may only read projected controller state and submit normal player commands or prompt responses through the existing web automation surface.
- Ensure each player has a distinct personality and conversational focus, can read recent history and prior checks, and does not simply repeat the previous player’s point.

### Design Direction
- Keep the change in the `user-test` path plus the existing automation API seam. Do not move demo-specific orchestration into the generic session runtime.
- Reuse the repo’s existing `LLMClient` / Responses-style transport for the four player agents, with a strict JSON decision contract and explicit per-player persona prompts.
- Drive one player at a time. In story mode, use a round-robin speaker order so players can build on the previous player without talking over each other. In prompt-owned situations, immediately route control to the controller that owns the active prompt. In combat, act only for the active player actor and keep DM/monster authority outside the player-agent layer except for optional monster turn pass-through needed to keep the demo moving.
- Preserve public/private visibility by constructing each agent’s context only from that controller’s own automation snapshot, plus connector-owned public coordination notes.
- Enforce distinctness deterministically: track recent party topics and reject near-duplicate story turns instead of silently letting all four agents ask the same thing.

### Steps
- [x] Extend the automation API/client so connectors can submit prompt responses in addition to plain text commands.
- [x] Implement a user-test four-player connector that waits for post-creation play, loads fixed personas, builds controller-local context from projected history/checks, and requests one validated action at a time from each player agent.
- [x] Add focused tests for automation prompt responses and the connector’s distinct-turn / history-aware context behavior.
- [x] Run the affected verification suite and record the outcome here.

### Verification Plan
- `python -m py_compile session_server\web_server.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_web_server.py tests\test_story_demo_party_connector.py`
- `python -m unittest tests.test_web_server -v`
- `python -m unittest tests.test_story_demo_party_connector -v`

### Review
- Extended [session_server/web_server.py](/d:/DND-newagent/session_server/web_server.py) and [user-test/web_story_demo_live_runner.py](/d:/DND-newagent/user-test/web_story_demo_live_runner.py) so the automation API now supports prompt responses through `POST /automation/prompt-response` in addition to plain text command injection. This keeps the connector on the same authoritative web automation seam instead of inventing a second control path.
- Added the new four-player connector [user-test/web_story_demo_party_connector.py](/d:/DND-newagent/user-test/web_story_demo_party_connector.py). It waits until character creation is finished, assigns four fixed personalities, feeds each player only that controller's visible summary/chat/check/card state, rotates freeform story turns in round-robin order, routes active prompts directly to the owning player, auto-passes monster turns if enabled, and rejects duplicate recent story topics so the party does not keep asking the same question.
- Added focused coverage in [tests/test_story_demo_party_connector.py](/d:/DND-newagent/tests/test_story_demo_party_connector.py) for three critical behaviors: player-agent context includes visible history and prior checks, duplicate story topics trigger a retry and revision, and player prompts use the prompt-response path. Added a web-server regression in [tests/test_web_server.py](/d:/DND-newagent/tests/test_web_server.py) to verify the automation prompt-response endpoint normalizes timing-order selections correctly.
- Updated [user-test/full-story-demo/README.md](/d:/DND-newagent/user-test/full-story-demo/README.md) and [docs/web-frontend.md](/d:/DND-newagent/docs/web-frontend.md) with the new connector command and behavior notes.
- Verification:
  - `python -m py_compile session_server\web_server.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_web_server.py tests\test_story_demo_party_connector.py`
  - `python -m unittest tests.test_web_server -v`
  - `python -m unittest tests.test_story_demo_party_connector -v`
- Observed results:
  - compile passed
  - `tests.test_web_server` passed 20 tests, including the new automation prompt-response coverage
  - `tests.test_story_demo_party_connector` passed 3 tests
  - the existing websocket shutdown-time `AssertionError` trace still appears during one web test, but the suite passes and this change did not introduce a failing assertion

## 2026-04-17 - Live Web Story Script Robustness And Pacing

### Scope
- Fix the user-test live web script so the browser demo has a longer Gundren exchange before travel, uses combat-only pacing, and no longer fails when a previously targeted goblin is already dead.
- Keep the change inside the user-test live-web runner/script path; do not add fallback combat logic to the authoritative rules runtime.

### Design Direction
- Treat the dead-target failure as a brittle automation-script problem, not a rules-engine bug. The runner should be able to resolve live command templates from the current projected combat view, and the script should gate combat actions on the active actor/runtime mode instead of assuming a fixed seed outcome.
- Encode pacing where it belongs: on the combat steps in the live script, not globally across character creation or non-combat setup.
- Expand the Gundren briefing into multiple natural-language turns so the live DM has enough real-time conversational back-and-forth before the travel phase starts.

### Steps
- [x] Add or finish runner/test support for view-gated templated commands and per-step post delays.
- [x] Rewrite the live LMOP web script with roughly five Gundren conversation rounds before travel.
- [x] Replace fixed combat targets with dynamic live-view targeting and add `0.2` second post delays only to combat commands.
- [x] Re-run the affected compile/unit verification and record the outcome here.

### Verification Plan
- `python -m py_compile user-test\web_story_demo_live_runner.py tests\test_story_demo_replay_scripts.py`
- `python -m unittest tests.test_story_demo_replay_scripts -v`
- `python -m unittest tests.test_web_server -v`

### Review
- Updated [user-test/web_story_demo_live_runner.py](/d:/DND-newagent/user-test/web_story_demo_live_runner.py) so command templates resolve only the placeholders they actually use. That preserves the new live combat placeholders without breaking prompt-aware non-combat scripts that have no active combat actor in view.
- Expanded [tests/test_story_demo_replay_scripts.py](/d:/DND-newagent/tests/test_story_demo_replay_scripts.py) so the runner coverage now proves three things together: view-gated templated commands execute, dead enemies are skipped when resolving `{first_enemy_actor_id}`, and `post_delay_seconds` sleeps only for the matching combat steps.
- Reworked [lmop-friendly-live-web-run.json](/d:/DND-newagent/user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json) so the Waterdeep briefing now has five conversational turns before departure, and the goblin-ambush combat uses live-view targeting plus `0.2` second post delays only on combat commands. Character creation and setup remain immediate.
- Verification:
  - `python -m py_compile user-test\web_story_demo_live_runner.py tests\test_story_demo_replay_scripts.py`
  - `python -m unittest tests.test_story_demo_replay_scripts -v`
  - `python -m unittest tests.test_web_server -v`
  - `python -c "import json; from pathlib import Path; json.loads(Path(r'user-test\\full-story-demo\\scripts\\lmop-friendly-live-web-run.json').read_text(encoding='utf-8')); print('json-ok')"`
- Observed results:
  - compile passed
  - `tests.test_story_demo_replay_scripts` passed 5 tests
  - `tests.test_web_server` passed 19 tests
  - the existing websocket shutdown-time `AssertionError` trace still appears during one web test, but the suite passes and this change did not introduce a failing assertion

## 2026-04-17 - Live Web Runner Timeout Fix

### Scope
- Fix the live browser automation runner so real DM turns do not fail after 60 seconds while the web server is still processing a valid LLM-backed story action.
- Keep the fix scoped to the user-test live-web runner path; do not alter the authoritative session flow or add fallback behavior in the DM runtime.

### Design Direction
- Treat the timeout as a client-side automation bug: the browser path is already live and authoritative, but the runner should not hardcode a 60-second HTTP request timeout for real story turns.
- Make the request timeout configurable from the runner API and CLI, with a safer default for real LLM-backed turns.
- Add focused test coverage for the timeout plumbing instead of trying to simulate a slow real model in the unit suite.

### Steps
- [x] Update `user-test/web_story_demo_live_runner.py` so request timeout is configurable and defaults to a long-lived value suitable for live story turns.
- [x] Add a focused test that verifies the configured timeout is passed to the HTTP client.
- [x] Re-run the affected runner/web tests and record the outcome.

### Verification Plan
- `python -m py_compile user-test\web_story_demo_live_runner.py tests\test_story_demo_replay_scripts.py`
- `python -m unittest tests.test_web_server tests.test_story_demo_replay_scripts -v`

### Review
- Updated [user-test/web_story_demo_live_runner.py](/d:/DND-newagent/user-test/web_story_demo_live_runner.py) so the automation HTTP client no longer hardcodes a 60-second request timeout. The runner now accepts `request_timeout_seconds`, defaults it to `300`, and supports `--request-timeout-seconds 0` from the CLI to disable the timeout entirely for slow real-model turns.
- Added focused timeout-plumbing coverage in [tests/test_story_demo_replay_scripts.py](/d:/DND-newagent/tests/test_story_demo_replay_scripts.py) to verify both the configured timeout path and the disabled-timeout path.
- Updated [user-test/full-story-demo/README.md](/d:/DND-newagent/user-test/full-story-demo/README.md) and [docs/web-frontend.md](/d:/DND-newagent/docs/web-frontend.md) so the live-web flow documents the new timeout flag.
- Verification:
  - `python -m py_compile user-test\web_story_demo_live_runner.py tests\test_story_demo_replay_scripts.py`
  - `python -m unittest tests.test_story_demo_replay_scripts -v`
  - `python -m unittest tests.test_web_server -v`
- Observed results:
  - compile passed
  - `tests.test_story_demo_replay_scripts` passed 4 tests
  - `tests.test_web_server` passed 19 tests

## 2026-04-13 - Tier-2 Blocked Level-2 Spell Rollout

### Scope
- Implement the currently blocked XPHB level-2 spells that require shared runtime primitives before they can be exact.
- Keep the rules engine authoritative, preserve the one-directory-per-item structure, and add individual per-spell tests in each item directory.
- Use subagents for parallel spell-family work, then merge and verify the combined runtime.

### Repo Inspection Summary
- The blocked spell set started as `Blindness/Deafness`, `Blur`, `Cloud of Daggers`, `Cordon of Arrows`, `Darkvision`, `Dragon''s Breath`, `Enhance Ability`, `Flame Blade`, `Flaming Sphere`, `Heat Metal`, `Hold Person`, `Invisibility`, `Mind Spike`, `Pass without Trace`, `Protection from Poison`, `Ray of Enfeeblement`, `Scorching Ray`, `Shatter`, `Silence`, and `Spiritual Weapon`.
- The real blocker clusters were shared primitives rather than 20 unrelated spell problems:
  - split-target active effects with independent per-target expiry/choice state
  - visibility/audio primitives (darkvision, sight-reliant blur disadvantage, sound suppression, observer-scoped reveal)
  - persistent damage/ward zones and unattended object damage
  - granted independent actions / conjured weapons / floating weapon summons
  - multi-ray spell attack execution
  - item-linked harmful effects and condition-specific save modifiers

### Design Direction
- Implement the missing shared primitives once, then express the blocked spells through the existing per-item executor and registry system.
- Preserve exact local-XPHB semantics where feasible. If a spell still needs a broader primitive after this pass, leave it blocked with a concrete reason instead of approximating it.
- Keep the merge order disciplined: primitives first, spell-family wiring second, regression/completeness verification last.

### Steps
- [x] Add split-target active-effect support and use it for `Blindness/Deafness`, `Enhance Ability`, `Hold Person`, and `Invisibility`.
- [x] Add the visibility primitives needed for `Blur` and `Darkvision`.
- [ ] Add the remaining visibility/audio primitives for `Mind Spike`, `Pass without Trace`, `Protection from Poison`, and `Silence`.
- [ ] Add persistent-zone / ward / unattended-object primitives for `Cloud of Daggers`, `Cordon of Arrows`, `Flaming Sphere`, and `Shatter`.
- [ ] Add conjured-weapon / floating-weapon / granted-action primitives for `Dragon''s Breath`, `Flame Blade`, `Heat Metal`, and `Spiritual Weapon`.
- [ ] Add multi-ray spell-attack support and finish `Scorching Ray` and `Ray of Enfeeblement`.
- [x] Ensure every newly implemented spell item directory has `IMPLEMENTATION.md`, executor wiring, and a 5-8 case individual test file.
- [x] Run focused per-spell suites, Tier-2 completeness tests, and broader runtime regressions for the newly implemented subset.

### Review
- Reused subagents to split the spell families, then implemented the shared split-target active-effect primitive locally and used it to finish `Blindness/Deafness`, `Enhance Ability`, `Hold Person`, and `Invisibility` exactly from the local XPHB text.
- Added the shared visibility hooks for actor-scoped darkvision radius plus sight-reliant incoming-attack disadvantage with blindsight/truesight bypass, then finished `Darkvision` and `Blur` exactly from the local XPHB text.
- Updated the Tier-2 manifests/support matrix so these six spells are no longer misreported as blocked. Current Tier-2 level-2 counts are `13` deterministic-capability, `14` blocked-shared-primitive, and `36` needs-clarification.
- Verification completed with:
  - `python -m unittest content.xphb.spells.level-2.blindness-deafness.tests.test_blindness_deafness content.xphb.spells.level-2.enhance-ability.tests.test_enhance_ability content.xphb.spells.level-2.hold-person.tests.test_hold_person content.xphb.spells.level-2.invisibility.tests.test_invisibility content.xphb.spells.level-2.darkvision.tests.test_darkvision content.xphb.spells.level-2.blur.tests.test_blur -v`
  - `python -m unittest tests.test_tier2_level2_spell_completeness tests.test_tier2_level2_spell_suite -v`
  - `python -m unittest tests.test_visibility_system tests.test_conditions tests.test_effect_execution tests.test_encounter_kernel -v`

## 2026-04-13 - Tier-2 Level-2 Spells Exact Deterministic Slice

### Scope
- Start the Tier-2 content rollout by implementing only the XPHB level-2 spells that can be executed exactly from the local spell text with the current authoritative runtime plus narrowly justified shared primitives.
- Use subagents for parallel spell-family review, keep the backend authoritative, and leave questionable spells explicitly blocked instead of guessing behavior.
- Require per-item directories, `IMPLEMENTATION.md`, executor wiring, and 5-8 focused item tests for every implemented spell.

### Repo Inspection Summary
- The Tier-2 spell folder structure, manifests, registry loader, and aggregate completeness tests already existed in scaffold form, but the deterministic slice was only partially wired and still had stale optimistic runtime labels.
- The active shared runtime can already handle ranged spell attacks, slot-scaled bonuses, persistent effects, persistent areas, and teleportation, but exact multi-target concentration handling is still limited by one active-effect instance carrying a shared target set.
- The earlier blocker notes were partly stale. After re-checking the actual local XPHB text against the live runtime, `Aid`, `Arcane Vigor`, `Barkskin`, `Lesser Restoration`, `Magic Weapon`, `Melf's Acid Arrow`, and `Misty Step` are exact with current or narrowly-added shared primitives; `Blindness/Deafness`, `Enhance Ability`, `Hold Person`, and `Invisibility` still need a new split-target active-effect primitive for exact upcast/per-target behavior.
- The item test harness initially had a structural bug: several spell tests started the encounter twice because they reused the level-1 cantrip helper's `advance_to_actor(...)` boot path.

### Design Direction
- Keep the current shared capability/runtime stack as the only execution engine. Add only the minimum shared primitives needed for exact text execution, then express each spell through its per-item executor and registry metadata.
- Treat provisional `planned-deterministic` manifest labels as hypotheses, not truth. Re-check the exact local spell text before implementation and downgrade anything that still needs a broader primitive or a clarification.
- Prefer exact runtime semantics over optimistic progress. If a spell needs per-target independent expiration, sight-reliance semantics, movable summoned weapons/zones, or other missing primitives, leave it blocked and record the concrete reason.

### Steps
- [x] Create Tier-2 repo skills and Tier-2 spell manifests/support-matrix scaffolding.
- [x] Re-check the candidate exact level-2 spells against the live runtime and implement the exact subset only.
- [x] Add the needed shared primitives for exact execution: slot-scaled max-HP / hit-die spending, touch-weapon scaling, bonus-action spell aliasing, and a true AC-floor effect primitive.
- [x] Wire per-item executors, definitions, README/IMPLEMENTATION docs, and 5-8 per-item tests for the exact subset.
- [x] Fix the item test harness so per-item tests exercise real mechanics rather than double-starting the encounter.
- [x] Run focused item suites, completeness tests, and broader encounter/effect regressions.
- [ ] Re-audit the remaining provisional `planned-deterministic` level-2 spells and either implement them or downgrade them with concrete blockers.

### Audit Update
- [x] Re-audited the remaining provisional Tier-2 level-2 spell bucket.
- Result: no additional `exact-now` spells remained. `Blur`, `Cloud of Daggers`, `Cordon of Arrows`, `Darkvision`, `Dragon''s Breath`, `Flame Blade`, `Flaming Sphere`, `Heat Metal`, `Mind Spike`, `Pass without Trace`, `Protection from Poison`, `Ray of Enfeeblement`, `Scorching Ray`, `Shatter`, `Silence`, and `Spiritual Weapon` were downgraded to `blocked-shared-primitive` in the manifests/support matrix with concrete blocker notes.
### Verification Plan
- `python -m py_compile tests\xphb_level2_spells\support.py shared_types\capabilities.py shared_types\encounter_models.py encounter_runtime\effect_execution.py encounter_runtime\kernel.py content\xphb\spells\level-2\aid\executor.py content\xphb\spells\level-2\arcane-vigor\executor.py content\xphb\spells\level-2\barkskin\executor.py content\xphb\spells\level-2\lesser-restoration\executor.py content\xphb\spells\level-2\magic-weapon\executor.py content\xphb\spells\level-2\melf-s-acid-arrow\executor.py content\xphb\spells\level-2\misty-step\executor.py`
- `python -m unittest content.xphb.spells.level-2.aid.tests.test_aid content.xphb.spells.level-2.arcane-vigor.tests.test_arcane_vigor content.xphb.spells.level-2.barkskin.tests.test_barkskin content.xphb.spells.level-2.lesser-restoration.tests.test_lesser_restoration content.xphb.spells.level-2.magic-weapon.tests.test_magic_weapon content.xphb.spells.level-2.melf-s-acid-arrow.tests.test_melf_s_acid_arrow content.xphb.spells.level-2.misty-step.tests.test_misty_step -v`
- `python -m unittest tests.test_tier2_level2_spell_completeness tests.test_tier2_level2_spell_suite -v`
- `python -m unittest tests.test_effect_execution tests.test_encounter_kernel -v`

### Review
- Added exact deterministic support for `Aid`, `Arcane Vigor`, `Barkskin`, `Lesser Restoration`, `Magic Weapon`, `Melf's Acid Arrow`, and `Misty Step`, with per-item executors, metadata, `IMPLEMENTATION.md`, and individual 5-8 case test files under each spell directory.
- Added narrowly-scoped shared primitives instead of spell-specific hacks: `armor_class_minimum` on active effects/actors for `Barkskin`, slot-scaled hit-die spending and max-HP bonuses, per-target ability-advantage metadata, target-owned weapon selection/scaling for `Magic Weapon`, and `bonus-action` spell action-cost aliasing in the encounter runtime.
- Fixed the deterministic item tests to use a stable encounter harness, explicit touch-range placement, immutable item replacement, and realistic hit-die pools instead of brittle assumptions.
- Kept `Blindness/Deafness`, `Enhance Ability`, `Hold Person`, and `Invisibility` blocked because the current active-effect model still cannot represent exact upcast multi-target concentration with independent per-target expiry/choice behavior.
- Verification completed with:
  - `python -m unittest content.xphb.spells.level-2.aid.tests.test_aid content.xphb.spells.level-2.arcane-vigor.tests.test_arcane_vigor content.xphb.spells.level-2.barkskin.tests.test_barkskin content.xphb.spells.level-2.lesser-restoration.tests.test_lesser_restoration content.xphb.spells.level-2.magic-weapon.tests.test_magic_weapon content.xphb.spells.level-2.melf-s-acid-arrow.tests.test_melf_s_acid_arrow content.xphb.spells.level-2.misty-step.tests.test_misty_step -v`
  - `python -m unittest tests.test_tier2_level2_spell_completeness tests.test_tier2_level2_spell_suite -v`
  - `python -m unittest tests.test_effect_execution tests.test_encounter_kernel -v`

## 2026-04-13 - Character Advancement And Level-Up Engine

### Scope
- Build the authoritative level-up engine that consumes existing pending level-up records from the progression ledger instead of rebuilding progression bookkeeping.
- Support transactional application of queued level-ups, class-level selection, HP / Hit Dice / proficiency updates, feature unlocks, spellcasting progression, and upgrade-time pending choices.
- Block finalization until mandatory upgrade choices are resolved, keep partial advancement state separate from the committed sheet, and avoid uncontrolled mid-resolution mutations.

### Repo Inspection Summary
- The progression ledger already exists and is authoritative in `shared_types/progression.py`, `rules_engine/progression.py`, and `StoryRuntimeState.progression_state`. It correctly queues `PendingLevelUpRecord` entries for XP and milestone progression, but it never applies them.
- `CharacterRecord` in `shared_types/models.py` is still level-1-centric: it only stores `level`, `class_id`, and level-1-derived selections/features. There is no multiclass structure, advancement transaction state, or upgrade-time pending-choice state.
- The runtime compiler in `monster_runtime/compiler.py` and passive-feature wiring in `rules_engine/starter_content.py` assume single-class progression driven by `record.class_id` and `record.level`. Those assumptions are workable if the advancement engine rebuilds a new authoritative `CharacterRecord` and recompiles the runtime actor atomically.
- The existing pending-choice framework in `shared_types/models.py` and `character_creation/kernel_v2.py` is strong, but it is creation-specific. It should be extended or mirrored for upgrade-time choices rather than inventing ad hoc level-up UI logic.
- The local mirror contains full higher-level XPHB class and subclass source data in `D:\5etools-mirror-2.github.io\data\class\class-*.json`, including multiclass prerequisites, class feature lists by level, spell slot progression, and subclass references. The current normalized loader only exposes level-1 class feature choice groups, so higher-level unlocks need a catalog extension.
- Story/web projection already has reusable summary and prompt/action-group surfaces in `session_server/storytelling_session.py` and `session_server/web_projection.py`. Advancement can project through those channels without inventing a second UI stack, as long as partial advancement state remains separate from the committed character sheet.
- Current session/bootstrap helpers build encounter actors directly from `CharacterRecord` via `CharacterPlacement(..., record=...)`. That makes the correct commit seam explicit: generate a validated upgraded record, replace the authoritative character record, then recompile and sync the runtime actor from the new record.

### Proposed Schema
- Add a typed advancement module, likely `shared_types/advancement.py`, with:
  - `AdvancementCommitStatus`
  - `AdvancementValidationStatus`
  - `AdvancementChoiceCategory`
  - `AdvancementChoiceSource`
  - `PendingAdvancementChoice`
  - `ResolvedAdvancementChoice`
  - `ClassLevelAllocation`
  - `AdvancementTransaction`
  - `AdvancementRuntimeState`
- Extend `CharacterRecord` with durable level-tracking fields needed for safe upgrades:
  - total level (preserve compatibility through `level`)
  - class-level allocations
  - hit-die ownership by class
  - subclass / class-selection metadata as required
  - committed advancement-resolved choices separate from level-1 creation choices
- Extend normalized class content so the catalog can answer, at minimum:
  - class feature refs by level
  - multiclass prerequisites
  - HP / hit-die data per class
  - spellcasting progression data beyond level 1
  - higher-level choice groups or feature-option refs where the mirror provides them
- Add advancement events to `shared_types/encounter_events.py`:
  - `LevelUpAvailable`
  - `AdvancementTransactionStarted`
  - `AdvancementClassChosen`
  - `AdvancementValidated`
  - `AdvancementChoiceGenerated`
  - `AdvancementChoiceResolved`
  - `AdvancementCommitSucceeded`
  - `AdvancementCommitFailed`
  - `CharacterLevelIncreased`
  - `ClassLevelIncreased`
  - `HitPointsIncreased`
  - `ProficiencyBonusUpdated`
  - `FeatureUnlocked`

### Design Direction
- Reuse the progression ledger as the only source of pending level-up eligibility. The advancement engine consumes queued `PendingLevelUpRecord`s and marks them applied only after a successful atomic advancement commit.
- Keep advancement transactional. Build a draft upgraded character state, validate class/multiclass legality and generated choices, and commit the new record only when all mandatory upgrade choices are resolved. If validation or choice resolution fails, leave the committed sheet unchanged.
- Prefer extending the existing creation-choice model into a generalized “character choice” system over hardcoding separate UI logic for level-up. Upgrade-time cantrip/spell/feature/style/expertise/subclass selections should flow through the same typed option-pool structure.
- Apply level-up by regenerating the authoritative `CharacterRecord` from prior committed state plus the chosen advancement delta, then recompile the runtime actor from that record. Do not patch HP, slots, or features directly in multiple systems.
- Preserve current runtime policy boundaries:
  - progression remains authoritative for eligibility and pending queueing
  - advancement remains authoritative for applying queued levels
  - encounter/story state stays authoritative for when application is legal
- Keep immediate scope honest. The engine should support current-class level-up cleanly first, with multiclass validation hooks and typed state present from the start. If normalized higher-level choice content is missing for some classes/features, the engine must reject illegal/incomplete advancement rather than guessing.

### Steps
- [x] Add typed advancement schemas, events, and authoritative story/session state for pending transactions and upgrade-time choices.
- [x] Extend normalized class/content loading so higher-level class feature refs, multiclass prerequisites, subclass entry points, and spellcasting progression are queryable from the catalog.
- [x] Implement the advancement engine: start transaction from pending level-up, choose class allocation, validate multiclass prerequisites, compute HP / Hit Dice / proficiency changes, and generate unlocks/choices.
- [x] Implement upgrade-time pending-choice resolution and blocking, reusing the existing typed choice framework where practical.
- [x] Add session commands and policy guards to start/apply/finalize level-ups only in legal states, and mark consumed pending level-up records applied on successful commit.
- [x] Recompile and replace authoritative runtime actors from the committed upgraded `CharacterRecord`, keeping partial transaction state separate from live actor state.
- [x] Project pending level-up availability, transaction state, and unresolved choices through existing story/web summary/prompt surfaces without leaking partial uncommitted sheet changes.
- [x] Add focused tests for XP/milestone-driven consumption, current-class upgrades, multiclass validation, HP/Hit Dice/proficiency changes, feature/spell unlock generation, pending-choice blocking, atomic failure rollback, and projection updates.

### Verification Plan
- `python -m py_compile shared_types\\advancement.py shared_types\\models.py shared_types\\storytelling.py shared_types\\encounter_events.py rules_engine\\fiveetools_loader.py rules_engine\\advancement.py character_creation\\kernel_v2.py monster_runtime\\compiler.py session_server\\storytelling_session.py session_server\\web_projection.py tests\\test_advancement_engine.py tests\\test_storytelling_session.py tests\\test_web_server.py`
- `python -m unittest tests.test_advancement_engine -v`
- `python -m unittest tests.test_advancement_engine tests.test_progression_ledger tests.test_storytelling_session tests.test_web_server tests.test_character_creation_kernel tests.test_encounter_kernel -v`

### Review
- Implemented `shared_types/advancement.py` and `rules_engine/advancement.py` as the authoritative transactional level-up engine, with typed transactions, class allocations, upgrade-time pending choices, deterministic HP gain handling, and atomic commit semantics.
- Extended normalized class loading in `rules_engine/fiveetools_loader.py` so higher-level class feature grants, subclass entry points, spellcasting progression, and multiclass metadata are queryable without breaking level-1 creation compatibility.
- Integrated advancement into `StoryRuntimeState` and `session_server/storytelling_session.py`, including `/levelup` commands, pending-level-up block syncing back into progression, runtime actor recompilation from committed `CharacterRecord`s, and story/web projection for unresolved advancement choices.
- Preserved compatibility in the creation loader/kernel by keeping level-1 class feature choice ids stable, preferring structured `toolProficiencies` over mojibake text where available, merging compatible tool-choice groups, and excluding magical items from mundane tool catalogs.
- Verification completed with:
  - `python -m py_compile shared_types\advancement.py shared_types\models.py shared_types\storytelling.py shared_types\encounter_events.py rules_engine\fiveetools_loader.py rules_engine\advancement.py character_creation\kernel_v2.py session_server\storytelling_session.py session_server\web_projection.py tests\test_advancement_engine.py`
  - `python -m unittest tests.test_advancement_engine -v`
  - `python -m unittest tests.test_progression_ledger tests.test_character_creation_kernel -v`
  - `python -m unittest tests.test_advancement_engine tests.test_progression_ledger tests.test_storytelling_session tests.test_web_server tests.test_character_creation_kernel -v`
  - `python -m unittest tests.test_xphb_level1_content_pack tests.test_xphb_rollout_manifest -v`



## 2026-04-12 - Campaign Progression And Reward Ledger

### Scope
- Build an authoritative campaign progression subsystem that supports both XP-based and milestone-based advancement without performing the full character-upgrade flow yet.
- Centralize progression bookkeeping so XP and milestone reasons are typed, deduped, auditable, and queryable from session state.
- Compute eligibility and queue pending level-up records instead of mutating character levels immediately.
- Reuse the existing story session, writeback, and projection systems instead of inventing a parallel persistence path.

### Repo Inspection Summary
- There is currently no progression subsystem. Searches across `shared_types`, `rules_engine`, `session_server`, `dm_agent`, `campaigns`, and `tests` found no authoritative XP ledger, milestone ledger, or advancement queue.
- The stable durable story-side container is `shared_types/storytelling.py::StoryRuntimeState`. It already carries travel, exploration, social, transcript, and scene/session metadata, so progression state belongs here rather than in encounter-only state or DM memory files.
- Character level currently exists in two authoritative places only: `shared_types/models.py::CharacterRecord.level` and `shared_types/encounter_models.py::RuntimeActorState.level`. There is no XP field today, which means the progression subsystem must track XP totals separately and avoid mutating levels in this task.
- The existing writeback seam is `session_server/storytelling_session.py::_sync_memory_files()`, which already derives compact campaign/session/NPC markdown summaries through `dm_agent/memory.py`. Progression should project into those summaries instead of creating a disconnected note system.
- Player/DM projection already flows through `session_server/web_projection.py` and `shared_types/web_ui.py` / `shared_types/web_session.py`. Those types currently expose goals, loops, travel, chat, and character cards, but no progression block.
- Existing event-driven persistent subsystems already provide the model to copy: `shared_types/social.py` + `rules_engine/social.py` for typed durable state, dedupe, projection, and writeback; `StorytellingSession._commit_exploration_result()` for integrating subsystem events into story state.
- Encounter/hazard/exploration hooks exist, but there is no authored reward table or quest/objective subsystem yet. Current useful attachment points are: combat completion state in `encounter_runtime/kernel.py` / `session_server/encounter_session.py`, exploration result events in `rules_engine/exploration.py`, social incident hooks in `rules_engine/social.py`, and hostile scene transitions in `rules_engine/hostile_escalation.py`.
- Test style is integration-heavy around `build_lmop_story_demo_session(...)` plus focused unit suites (`tests/test_social_consequences.py`, `tests/test_storytelling_session.py`, `tests/test_web_server.py`). The clean path is one dedicated progression suite plus small projection/session regressions.

### Proposed Schema
- Add `shared_types/progression.py` with:
  - `ProgressionMode`: `xp | milestone`
  - `ProgressionPolicy`: explicit XP distribution / milestone policy
  - `XPRewardSourceType`
  - `MilestoneSourceType`
  - `XPRewardRecord`
  - `MilestoneRecord`
  - `PendingLevelUpRecord`
  - `ProgressionEligibilityState` or equivalent per-actor progress snapshot
  - `CampaignProgressionState`
- Extend `StoryRuntimeState` with a typed `progression_state` field.
- Add progression events to `shared_types/encounter_events.py`:
  - `XPRewardLoggedEvent`
  - `XPRewardAppliedEvent`
  - `MilestoneCompletedEvent`
  - `MilestoneAdvancementGrantedEvent`
  - `ProgressionEligibilityUpdatedEvent`
  - `LevelUpQueuedEvent`
  - `ProgressionProjectionUpdatedEvent`
- Add a `rules_engine/progression.py` engine that owns:
  - reward logging and dedupe
  - milestone completion and dedupe
  - official 2024 XP-threshold lookup
  - eligibility calculation
  - pending level-up queue creation
  - DM/player projection lines for the session layer

### Design Direction
- Keep progression authoritative on the story/session side, not inside encounter resolution. Encounter, exploration, social, and future quest systems should feed typed reward/milestone records into the progression engine instead of storing their own advancement math.
- Do not invent arbitrary automatic XP values from combat, traps, or discoveries in this task. Provide explicit typed ledger APIs and DM/system command hooks so future authored content can award XP or milestones cleanly without fallback heuristics.
- Seed the subsystem through `bootstrap.py` with an explicit campaign progression mode and policy so the active rule is visible and testable from the first session frame.
- Queue level-up eligibility in typed pending records and leave `CharacterRecord.level` / `RuntimeActorState.level` unchanged until a later upgrade subsystem applies the result.
- Surface player-safe progression summaries in story views and web projections, while keeping DM-only milestone planning or hidden notes out of player payloads.

### Steps
- [x] Add typed progression schemas, official XP thresholds, and encounter/story progression events.
- [x] Extend `StoryRuntimeState` and bootstrap/session builders with authoritative progression mode, policy, and initial progression state.
- [x] Implement `rules_engine/progression.py` for XP reward logging, milestone logging, dedupe/idempotency, eligibility calculation, and pending level-up queueing.
- [x] Integrate the progression engine into `StorytellingSession`, including DM/system award hooks, summary lines, and memory writeback.
- [x] Extend DM/player projections so current XP or milestone progress and pending level-up state are visible to the correct users without leaking hidden planning.
- [x] Add tests for XP and milestone dedupe, official threshold eligibility, party-wide vs individual policy, pending queue behavior, no immediate level mutation, projection/writeback, and deterministic replay behavior.

### Verification Plan
- `python -m py_compile shared_types\progression.py shared_types\storytelling.py shared_types\encounter_events.py rules_engine\progression.py session_server\bootstrap.py session_server\storytelling_session.py session_server\web_projection.py dm_agent\memory.py tests\test_progression_ledger.py tests\test_storytelling_session.py tests\test_web_server.py`
- `python -m unittest tests.test_progression_ledger -v`
- `python -m unittest tests.test_progression_ledger tests.test_storytelling_session tests.test_web_server tests.test_dm_memory -v`

### Review
- Added `shared_types/progression.py` for authoritative progression mode, policy, XP reward records, milestone records, actor progress snapshots, pending level-up records, and the official 2024 XP threshold table.
- Implemented `rules_engine/progression.py` so XP and milestone awards are deduped, auditable, policy-aware, and converted into pending level-up records instead of immediate level mutations.
- Extended `StoryRuntimeState` with durable `progression_state`, integrated `/progression ...` commands into `StorytellingSession`, and projected progression summaries into both player-safe story views and DM-only ledger lines.
- Extended `dm_agent/memory.py` and `StorytellingSession._sync_memory_files()` so campaign/session writeback now includes compact progression summaries with recent reward and milestone reasons.
- Added `tests/test_progression_ledger.py` with engine and session coverage for XP logging, milestone logging, dedupe, official threshold eligibility, policy behavior, pending queue semantics, player/DM projection, writeback integration, and deterministic replay.

### Verification
- `python -m py_compile shared_types\progression.py rules_engine\progression.py shared_types\storytelling.py shared_types\encounter_events.py dm_agent\memory.py session_server\storytelling_session.py tests\test_progression_ledger.py` -> passed.
- `python -m unittest tests.test_progression_ledger -v` -> 9 tests passed.
- `python -m unittest tests.test_dm_memory -v` -> 6 tests passed.
- `python -m unittest tests.test_progression_ledger tests.test_dm_memory tests.test_storytelling_session tests.test_web_server -v` -> 46 tests passed.

## 2026-04-11 - Full Story Demo Replay Scripts And LLM Reaction Harness

### Scope
- Add replayable end-to-end script files for the current LMOP full-story demo so the whole authored path can be exercised from deterministic character creation in Waterdeep through the goblin ambush battle resolution.
- Cover both a friendly/socially cooperative run and an unfriendly/escalatory run, including queued DM/LLM JSON responses for story turns and spell/social reaction handling.
- Reuse the existing authoritative full-story demo session and controller flow rather than inventing a parallel transcript-only harness.

### Repo Inspection Summary
- The existing end-to-end entrypoint is the manual wrapper in `user-test/story_demo_system_server.py`, built by `build_full_story_demo_manual_session(...)`, which starts in deterministic character creation and then hands off to the LMOP story session in Waterdeep.
- The current scripted-input surface already exists for controllers via `user-test/encounter_controller_client.py`, which supports `--command` and `--commands-file`, but there is no authored whole-campaign replay file format or offline runner that feeds both controller commands and queued LLM outputs together.
- The story/bootstrap path already includes the needed authored scenes and travel bridge: `scene-waterdeep-gundren-briefing`, `scene-00-high-road-journey`, and `scene-triboar-goblin-ambush`, plus the travel hex map in `campaigns/lmop/maps/high-road-region-hex.json`.
- Test infrastructure already uses `QueueTransport` payload queues to simulate LLM outputs for story turns, spellcasting reactions, hostile escalation, and social consequences, so the new script runner should reuse that contract instead of re-implementing the DM runtime boundary.
- The relevant current command surface spans deterministic `/create ...`, story `/say`/`/story`/plain text/`/check`, travel `/travel ...`, exploration `/march` `/watch` `/role` `/camp` `/downtime`, story-mode `/cast`, and combat commands such as `/move`, `/attack`, `/cast`, `/feature`, `/use`, `/dash`, and `/endturn`.

### Design Direction
- Introduce a reusable authored replay-script format that contains both queued LLM response objects and ordered controller interaction steps.
- Build one runner around `build_full_story_demo_manual_session(...)` so the scripts execute entirely against the existing authoritative session flow.
- Keep the script format explicit about expectations: controller id, input text, optional prompt handling, and view/assertion checkpoints so the files are test artifacts rather than passive transcripts.
- Cover the current starter-slice mechanics end to end across two scripts instead of pretending one run can literally exercise every isolated mechanic family in the repository. The target coverage for this slice is: character creation, story turns, story checks, social-friendly and social-hostile outcomes, story spell reactions, travel state changes, exploration role setup, hostile escalation, combat actions, reactions/prompts, and demo completion.

### Steps
- [x] Define the replay-script schema and choose repo-aligned locations for the runner and authored script files.
- [x] Implement the replay runner on top of `build_full_story_demo_manual_session(...)` and the existing `QueueTransport`-style fake LLM transport.
- [x] Author at least two end-to-end scripts: one friendly/cooperative Waterdeep-to-ambush path and one unfriendly/escalatory path with visible social fallout and hostile escalation.
- [x] Add automated tests that execute both scripts, validate major state transitions, and assert that queued LLM reaction payloads are consumed through the real DM runtime boundary.
- [x] Document how to run the scripts manually, then verify with focused test runs and record the results in `tasks/SUMMARIES.md`.

### Review
- Added `user-test/story_demo_replay.py` as a reusable replay runner that executes authored JSON scripts against the existing `build_full_story_demo_manual_session(...)` path using queued fake LLM payloads shaped like the real DM runtime transport boundary.
- Authored two end-to-end scenario files under `user-test/full-story-demo/scripts/`: `lmop-friendly-full-run.json` and `lmop-unfriendly-full-run.json`. Each script contains explicit controller interactions from deterministic character creation through Waterdeep story play, travel, DM hook engagement, and combat resolution.
- The friendly script covers: polite tavern interaction, an LLM-issued story check plus `/check`, helpful public magic with a benign witness reaction, downtime help/start/work, marching order, watch order, exploration roles, travel planning, travel interruption, DM hook engagement, and a deterministic successful ambush combat.
- The unfriendly script covers: threatening social tone that remains in story mode, suspicious public magic with hidden authority fallout, DM-vs-player projection separation for delayed consequences, camp start/stop, faster travel pacing, and a deterministic successful ambush combat.
- Added `tests/test_story_demo_replay_scripts.py` so both replay files run as integration tests instead of sitting as unchecked artifacts, and updated `user-test/full-story-demo/README.md` with runner usage.

### Verification
- `python -m py_compile user-test\story_demo_replay.py tests\test_story_demo_replay_scripts.py` -> passed.
- `python -m unittest tests.test_story_demo_replay_scripts -v` -> passed.
- `python -m unittest tests.test_story_demo_replay_scripts tests.test_full_story_demo_session tests.test_storytelling_session -v` -> 19 tests passed.

## 2026-04-11 - Hostile Escalation And Ad Hoc Encounter Synthesis

### Scope
- Harden and complete the story-to-combat hostile-escalation path without rebuilding the existing story/combat/social runtimes.
- Ensure overt hostile acts and harmful story-mode spell declarations escalate into combat before final hostile resolution.
- Synthesize combatants for story NPCs, synthesize fallback tactical scenes when no authored map exists, preserve story/social context across the transition, and support delayed reinforcements.

### Repo Inspection Summary
- The repository already contained a partial hostile-escalation subsystem in `shared_types/hostile_escalation.py`, `rules_engine/hostile_escalation.py`, and `session_server/storytelling_session.py`.
- Existing typed models already covered escalation outcomes, synthesized combatants, reinforcement plans, ad hoc scene plans, and combat transition state, but the story session was not using the engine hydration path.
- The local LMOP references required for a campaign-bound proof slice were present and usable:
  - `campaigns/lmop/chapters/chapter-01/scene-00-waterdeep-briefing.md`
  - `campaigns/lmop/chapters/chapter-01/scene-01-goblin-ambush.md`
  - `campaigns/lmop/chapters/chapter-01/scene-02-trail-aftermath.md`
  - `campaigns/lmop/npcs/gundren-rockseeker.md`
  - `campaigns/lmop/npcs/sildar-hallwinter.md`
  - `campaigns/lmop/npcs/combat-profiles.json`
  - `campaigns/lmop/locations/waterdeep.md`
  - `campaigns/lmop/locations/high-road.md`
  - `campaigns/lmop/locations/triboar-trail.md`
- The main real gaps were:
  - hostile decisions were not being hydrated into full combat plans before transition
  - story NPC synthesis ignored the local LMOP combat-profile data already in the repo
  - reinforcements were only scheduled, not inserted into live initiative later
  - the fallback tavern synthesis/tests were stale and out of sync with the runtime
  - encounter start was reconciling all canonical actors, including off-scene goblins, instead of just actual participants

### Design Direction
- Reuse the existing hostile-escalation engine as the single planner for escalation decisions, synthesized combatants, fallback scene plans, and reinforcement schedules.
- Keep the rules engine authoritative for encounter start, surprise, initiative order, and later reinforcement insertion.
- Promote the local LMOP combat profiles into the synthesis path so the priority order is explicit:
  1. existing encounter actor
  2. local campaign NPC combat profile / explicit monster record
  3. archetype fallback
- Preserve story context on synthesized actors via `story_context` plus the existing flat story fields, so combat intent can express flee/protect/arrest/delay rather than only attack.
- Add a small authoritative reinforcement-entry processor tied to the existing combat round flow instead of building a second scheduler.
- Keep the fallback tactical scene explicit and intelligible: tavern/common-room geometry first when the scene metadata supports it, otherwise typed open-area fallback with bounds, exits, and entry edges.

### Steps
- [x] Normalize the hostile-escalation planning path so `StorytellingSession` uses a hydrated combat-transition plan instead of partially duplicating synthesis logic.
- [x] Extend hostile-escalation synthesis to load LMOP combat profiles, fill missing fallback archetypes, preserve richer story/social context, and select active participants vs bystanders more cleanly.
- [x] Implement reinforcement entry resolution using the existing encounter initiative insertion path and emit the typed reinforcement-entry event when they actually arrive.
- [x] Align the tavern/common-room and open-area fallback scene synthesis contracts, including stable map ids, spawn zones, exits, bystander zones, and watch-entry handling.
- [x] Update hostile-escalation, story-session, and projection tests to cover hostile-boundary decisions, surprise, synthesized combatants, fallback scene geometry, reinforcement scheduling/entry, and DM/player-visible transition behavior using the local LMOP fixtures.
- [x] Run focused verification, document results, and record remaining gaps only if they are real and bounded.

### Review
- Reworked the hostile-escalation transition so the story session now hydrates minimal escalation decisions through the engine before combat start, rather than expecting scene plans and synthesized participants to already be present.
- Extended synthesized combatants with authority tags and full `story_context`, and taught the engine to load LMOP combat-profile data from `campaigns/lmop/npcs/combat-profiles.json` for Gundren, Sildar, and the Waterdeep Watch.
- Added a reusable public fallback tavern/common-room scene builder contract with stable geometry, exits, bystander zones, and watch-entry positions, plus a structured open-area fallback.
- Implemented delayed reinforcement entry using the existing kernel initiative-insertion helper and surfaced the resulting `ReinforcementEnteredEvent` through the story/web projection path.
- Fixed an adjacent kernel bug exposed by this work: `EncounterStartedEvent` now reconciles only actual encounter participants, not every actor in canonical state, which prevents off-scene future monsters from breaking synthesized story combat starts.
- Replaced the stale hostile-escalation regression file with coverage that matches the current runtime behavior and local LMOP fixtures.

### Verification
- `python -m py_compile shared_types\hostile_escalation.py shared_types\encounter_events.py rules_engine\hostile_escalation.py session_server\storytelling_session.py session_server\web_projection.py encounter_runtime\kernel.py tests\test_hostile_escalation.py` -> passed.
- `python -m unittest tests.test_hostile_escalation -v` -> 9 tests passed.
- `python -m unittest tests.test_hostile_escalation tests.test_storytelling_session tests.test_web_server tests.test_encounter_kernel -v` -> 60 tests passed.
- `python -m unittest tests.test_rest_recovery -v` still contains an unrelated pre-existing failure in `test_damage_interrupts_long_rest` caused by a stale direct call signature for `_damage_preview`; this hostile-escalation slice did not change that path.

## 2026-04-10 - Starter Pack Docs Refresh

### Scope
- Refresh `docs/starter-content-pack.md` so it reflects the current web UI, slash-command surfaces, story/travel/combat flow, XPHB level-1 content coverage, and notable runtime systems now present in the repo.
- Keep the guide accurate to the live parsers and manifests instead of the old starter-slice state.

### Repo Inspection Summary
- `docs/starter-content-pack.md` is stale: it still describes a small starter slice and under-documents storytelling/travel procedure flow.
- The live command surfaces are split across `player_interface/slash_commands.py`, `player_interface/encounter_commands.py`, and `session_server/storytelling_session.py`.
- The browser flow and action-panel helpers are described in `docs/web-frontend.md` and implemented in `web_frontend/app.js`.
- Current content coverage comes from `content/xphb/manifests/xphb-cantrips.json`, `content/xphb/manifests/xphb-level1-spells.json`, and `content/xphb/manifests/xphb-level1-class-features.json`.

### Steps
- [x] Inspect the current starter guide, live command parsers, web UI docs, and XPHB manifests.
- [x] Rewrite `docs/starter-content-pack.md` so it documents the actual current features, commands, flows, and coverage.
- [x] Review the rewritten guide against the inspected source files and record the result in `tasks/SUMMARIES.md`.

### Review
- Replaced the old starter-slice quick reference in `docs/starter-content-pack.md` with a current runtime-oriented guide covering the web demo, mode flow, creation, storytelling, travel, combat, spell/feature command patterns, XPHB level-1 coverage, and social-consequence behavior.
- Aligned the guide with the live parser surfaces in `player_interface/slash_commands.py`, `player_interface/encounter_commands.py`, and `session_server/storytelling_session.py`, instead of older hand-written assumptions.
- Updated the coverage section to reflect the current manifests: 34 XPHB cantrips, 64 XPHB level-1 spells, and 33 XPHB level-1 class features, with the remaining story-adjudicated subsets called out explicitly.
- Documented the current browser UX helpers and mode-specific flow, including the creation `Insert command` helper, travel hex-map usage, storytelling declaration flow, and combat-only deterministic command surface.

### Verification
- `Get-Content docs\starter-content-pack.md` -> reviewed the rewritten guide after the replacement.
- `Get-Content player_interface\slash_commands.py` -> verified the `/create` command set documented in the guide.
- `Get-Content player_interface\encounter_commands.py` -> verified the combat, spell, feature, equipment, object-interaction, familiar, and rest command surface documented in the guide.
- `Get-Content session_server\storytelling_session.py | Select-Object -Skip 1028 -First 130` -> verified storytelling, travel, exploration, and downtime command handling plus the declaration-driven `/social` / `/trap` / `/puzzle` rule.
- `Get-Content docs\web-frontend.md` and `rg -n "Insert command|travel|hex|route|Begin character creation" web_frontend\app.js docs\web-frontend.md session_server\web_projection.py shared_types\web_ui.py` -> verified the browser-flow claims, action-panel helpers, and travel-map behavior.
- `Get-Content content\xphb\manifests\xphb-cantrips.json`, `Get-Content content\xphb\manifests\xphb-level1-spells.json`, and `Get-Content content\xphb\manifests\xphb-level1-class-features.json` -> verified the published XPHB coverage counts and story-adjudicated subsets used in the guide.

## 2026-04-08 - XPHB Level-1 Class Feature Completion

### Scope
- Implement all XPHB level-1 class abilities through the authoritative backend.
- Give Rogue `Sneak Attack` a prompted post-hit application path that does not spend a reaction and still works once per turn on off-turn hits.
- Add one dedicated test module per XPHB level-1 class feature, with at least 3 meaningful cases or full branch coverage when the feature has fewer distinct branches.

### Repo Inspection Summary
- The repository already had one-folder-per-feature content metadata and manifests for all 33 XPHB level-1 class features.
- Runtime support was uneven: several passive features compiled correctly, but `Lay on Hands`, `Arcane Recovery`, and `Sneak Attack` were still missing full authoritative execution.
- The reaction/timing engine already supported non-reaction prompt windows, which was the cleanest existing mechanism for `Sneak Attack` without violating the once-per-turn rule.

### Design Direction
- Reuse the existing typed pending-attack and timing-window infrastructure instead of inventing a second class-feature engine.
- Implement the missing active features as real capability resolutions, not manifest-only support.
- Cover passive features with explicit compile/runtime assertions in per-feature test modules.

### Steps
- [x] Extend the runtime state and post-hit prompt pipeline to support Rogue `Sneak Attack` once per turn, including off-turn use without spending a reaction.
- [x] Implement the missing executable level-1 feature mechanics still absent from the runtime, starting with `Lay on Hands` and `Arcane Recovery`, and tighten shallow capability shells that needed authoritative behavior.
- [x] Add the dedicated `tests/xphb_level1_class_features/<feature>/test_<feature>.py` tree so every XPHB level-1 class feature has its own test module with at least 3 meaningful cases.
- [x] Update touched metadata/test fixtures where runtime truth changed.
- [x] Run focused feature suites plus broader regressions before closing the slice.

### Review
- Added typed parameter support for `/feature` and `/use`, then wired real runtime handlers for `Lay on Hands` and `Arcane Recovery` instead of leaving them as compile-only pools.
- Extended the post-hit reaction window so `Sneak Attack` appears as a prompted feature option that does not spend a reaction, can trigger off-turn, and is enforced once per turn through authoritative event/state markers.
- Tightened passive feature execution by carrying finesse data, spell-attack advantage, spell save DC bonuses, and one-shot d20 effect consumption through the shared runtime so `Bardic Inspiration`, `Innate Sorcery`, and weapon-driven Sneak Attack qualifiers behave correctly.
- Added a dedicated `tests/xphb_level1_class_features/` tree with 33 individual feature modules and 100 passing cases.
- Corrected a stale creation regression in `tests/test_character_creation_kernel.py` so it now checks the current local selectable-skill background `Investigator [VRGR]` instead of the removed `Haunted One [VRGR]`.

### Verification
- `python -m unittest tests.xphb_level1_class_features.rogue__sneak_attack.test_rogue__sneak_attack -v` -> 4 tests passed.
- `python -m unittest discover -s tests\xphb_level1_class_features -t . -p "test_*.py" -v` -> 100 tests passed.
- `python -m unittest tests.test_xphb_level1_content_pack tests.test_character_creation_kernel tests.test_encounter_kernel tests.test_web_server -v` -> 59 tests passed.

## 2026-04-09 - Social Consequences / Reputation / Magical Norms

### Scope
- Build a typed persistent social-consequence layer under story-mode spellcasting, social influence, NPC memory, faction/location consequences, and delayed rumor/authority propagation.
- Keep the backend authoritative for incident logging, social-state mutation, hidden witness knowledge, and propagation scheduling.
- Reuse the current story spellcasting, exploration/social, DM runtime, memory writeback, and projection systems instead of creating a parallel narrative engine.

### Repo Inspection Summary
- Story spellcasting already has a typed witness/reaction seam in `shared_types/storytelling.py` and `session_server/storytelling_session.py`: story casts build `WitnessObservationPacket`, optionally call the DM runtime for a validated `SpellcastingSocialReactionPlan`, and then fold reactions into NPC stance via `rules_engine/exploration.py`.
- Current social state is scene-local only: `NpcInfluenceState` in `shared_types/exploration.py` stores attitude/trust/hostility/leverage/obligation/fear/interest, and `ExplorationState.npc_states` is the live store used by `attempt_social_influence()` and spellcasting reaction fallout.
- There is no first-class typed incident ledger, faction/location reputation state, magical norms model, or delayed propagation queue. Current fallout is spread across event-log entries, transcript lines, and `scene_state_notes` metadata.
- DM memory writeback already exists in `session_server/storytelling_session.py::_sync_memory_files()` and `dm_agent/memory.py`, and those files are already re-ingested into retrieval context.
- The web/session layer already supports DM/player visibility separation for story chat, prompts, and NPC stance summaries in `session_server/web_projection.py`.

### Proposed Schema
- Add a new typed `shared_types/social.py` module for:
  - `SocialRelationshipState`
  - `ReputationState`
  - `FactionRelationshipState`
  - `KnownReputationProjection`
  - `SocialIncident`
  - `SocialIncidentCategory`
  - `SocialIncidentSeverity`
  - `SocialPublicityScope`
  - `NormProfile`
  - `MagicalNormTag`
  - `WitnessReactionCategory`
  - `SocialPropagationTask`
  - `InfluenceRetryCooldown`
  - `SocialRuntimeState`
- Extend `StoryRuntimeState` with a typed `social_state` ledger instead of relying on `metadata` strings for durable social consequences.
- Extend `WitnessObservation` / witness packets with norm and social-context fields so the DM runtime sees typed witness context without mutating state itself.
- Add typed encounter events for incidents, consequence application, norm consultation, propagation scheduling/execution, and reputation/faction changes.

### Design Direction
- Keep `ExplorationState.npc_states` as the scene-local projection for active NPCs, but back it with a wider `StoryRuntimeState.social_state` ledger that also tracks faction/location/authority memory and propagation tasks.
- Centralize consequence application in a new `rules_engine/social.py` engine that logs incidents, applies validated reaction plans, updates relationship/reputation state, schedules propagation, and syncs visible NPC stance back into `ExplorationState`.
- Integrate influence checks by consulting persistent social state before and after `attempt_social_influence()`: relationship metrics adjust willingness/hesitation/refusal, failed repeated requests create retry cooldowns, and results update the persistent ledger.
- Keep DM memory markdown as a derived projection of the authoritative social ledger rather than the source of truth.

### Steps
- [x] Add the typed social-state / incident / norms / propagation schemas and extend story runtime state plus witness context/events.
- [x] Implement a social consequence engine for relationship updates, magical-norm consultation, incident logging, propagation scheduling/execution, and scene-local NPC-state sync.
- [x] Wire story-mode spellcasting through the new incident pipeline so witnessed spellcasts create incidents, consult norms, update persistent social state, and schedule delayed authority/rumor effects where appropriate.
- [x] Integrate social influence with the persistent ledger, including willingness/refusal state, retry cooldowns, and future-influence modifiers.
- [x] Extend DM memory/writeback and story/web projections so DM sees full incident/social state while players only see character-known/public consequences.
- [x] Add proof fixtures/tests for helpful public magic, suspicious magic in tense negotiation, unwitnessed acts, propagation, retry cooldowns, and DM/player visibility separation.

### Verification Plan
- `python -m py_compile shared_types\social.py shared_types\storytelling.py shared_types\encounter_events.py shared_types\exploration.py rules_engine\social.py rules_engine\exploration.py session_server\storytelling_session.py session_server\bootstrap.py session_server\web_projection.py dm_agent\runtime.py dm_agent\memory.py tests\test_social_consequences.py tests\test_storytelling_session.py tests\test_exploration_procedures.py tests\test_web_server.py tests\test_dm_memory.py`
- `python -m unittest tests.test_social_consequences -v`
- `python -m unittest tests.test_storytelling_session tests.test_exploration_procedures tests.test_web_server tests.test_dm_memory -v`
- Re-run any directly affected hostile-escalation or story spellcasting regressions if the social integration changes those paths.


### Review
- Added a first-class `shared_types/social.py` ledger plus social-specific events so incidents, norms, relationship state, reputation, and propagation schedules are authoritative typed state instead of scattered transcript metadata.
- Wired `rules_engine/social.py` into `StorytellingSession` so story spellcasts and exploration social checks now update the persistent ledger, schedule delayed authority or rumor fallout, and sync scene-local NPC stance back into `ExplorationState`.
- Closed a real integration gap by enriching story spell witness packets with applicable norm ids/tags and current relationship metrics before they go to the DM runtime.
- Extended story views and DM memory writeback so players only see known/public consequences while DM summaries, scene-state files, and NPC playbooks receive the hidden social state.
- Added `tests/test_social_consequences.py` to cover bootstrap state, witnessed and unwitnessed spell incidents, helpful-magic rumor spread, suspicious authority reporting, retry cooldowns, and DM-only writeback paths.

### Verification
- `python -m py_compile shared_types\social.py shared_types\storytelling.py shared_types\encounter_events.py rules_engine\social.py rules_engine\exploration.py session_server\storytelling_session.py session_server\bootstrap.py session_server\web_projection.py dm_agent\runtime.py dm_agent\memory.py tests\test_social_consequences.py tests\test_storytelling_session.py tests\test_exploration_procedures.py tests\test_web_server.py tests\test_dm_memory.py` -> passed.
- `python -m unittest tests.test_social_consequences -v` -> 7 tests passed.
- `python -m unittest tests.test_social_consequences tests.test_storytelling_session tests.test_exploration_procedures tests.test_dm_memory tests.test_web_server -v` -> 54 tests passed.

## 2026-04-09 - Social Consequences / Reputation / Magical Norms Hardening

### Scope
- Tighten the existing social-consequence subsystem to match the stricter specification: separate actual events from witness perception, witness interpretation, immediate consequence, and delayed propagation.
- Add typed norm precedence, incident dedupe/idempotency, broader reusable incident support, and stronger DM/player hidden-information separation.
- Preserve the current backend-authoritative story spellcasting and influence integrations while refactoring them onto a more general incident pipeline.

### Repo Inspection Summary
- The current subsystem already persists relationship, faction, location, and authority state in `shared_types/social.py` and `rules_engine/social.py`, then integrates that ledger into `StorytellingSession`, DM memory writeback, and story/web projections.
- Current strongest path: witnessed story-mode spellcasting. The runtime builds witness packets, asks the DM runtime for typed social reaction plans, applies relationship/reputation updates, and schedules simple rumor or authority tasks.
- Current weaker areas: there is no explicit incident-dedupe mechanism, no separate typed witness/interpretation/propagation records inside incidents, no explicit norm precedence model, and no reusable generic incident logger for non-spell social incidents such as threat or violence.
- Existing tests cover helpful public magic, suspicious spellcasting, retry cooldowns, propagation execution, and DM/player projection separation, but they do not yet prove dedupe, norm precedence, or duplicate-spread suppression.

### Design Direction
- Extend the existing `shared_types/social.py` ledger rather than replacing it, so current story spellcasting and influence flows keep working.
- Add explicit typed layers for witness perception, witness interpretation, and propagation records, then make `SocialIncident` link to those records plus a dedupe key.
- Make norm resolution precedence-aware with a documented merge order: scene override > NPC-specific > institution > faction > location > settlement default.
- Refactor `rules_engine/social.py` around a reusable incident-registration path with dedupe and propagation duplicate suppression, then route spellcasting and influence through it.
- Keep DM memory/writeback and player projections derived from the authoritative social ledger, with hidden witness knowledge remaining DM-only.

### Steps
- [x] Extend the social schema with incident witness/interpretation/propagation record types, norm scope/precedence, incident dedupe keys, and richer relationship metadata.
- [x] Refactor the social engine to support precedence-aware norm evaluation, generic incident registration, idempotent incident logging, and duplicate-safe propagation scheduling/execution.
- [x] Rewire story spellcasting and influence integration through the new incident pipeline, and add at least one reusable non-spell hostile/threat incident hook.
- [x] Tighten DM/player projections and DM memory writeback so hidden witnesses, delayed authority reports, and compact durable summaries behave correctly.
- [x] Add tests for incident dedupe, norm precedence/merging, duplicate propagation suppression, hidden-information projection separation, and the strengthened integration paths.

### Verification Plan
- `python -m py_compile shared_types\social.py shared_types\storytelling.py shared_types\encounter_events.py rules_engine\social.py rules_engine\exploration.py rules_engine\hostile_escalation.py session_server\storytelling_session.py session_server\bootstrap.py session_server\web_projection.py dm_agent\runtime.py dm_agent\memory.py tests\test_social_consequences.py tests\test_storytelling_session.py tests\test_exploration_procedures.py tests\test_web_server.py tests\test_dm_memory.py`
- `python -m unittest tests.test_social_consequences -v`
- `python -m unittest tests.test_social_consequences tests.test_storytelling_session tests.test_exploration_procedures tests.test_dm_memory tests.test_web_server -v`


### Review
- Hardened `shared_types/social.py` with explicit norm scope/merge policy, durable incident witness records, interpretation records, propagation records, location-authority state, incident dedupe keys, and richer relationship linkage back to incident history.
- Refactored `rules_engine/social.py` so story spellcasting and influence now register idempotent incidents, persist witness/interpretation records, emit trust/suspicion/interpretation events, consult precedence-aware norms, and suppress duplicate propagation tasks.
- Extended delayed propagation to update faction and location-authority memory, not just location or authority reputation, while keeping the queue duplicate-safe through linked propagation records.
- Fixed a hidden-info projection leak by filtering `PRIVATE_CONTROLLERS` transcript entries in `session_server/web_projection.py`, and updated `session_server/storytelling_session.py` to call the new state-aware norm resolver.
- Expanded `tests/test_social_consequences.py` with dedupe, norm precedence, faction propagation execution, location-authority updates, and private-controller projection coverage.

### Verification
- `python -m py_compile shared_types\social.py shared_types\encounter_events.py rules_engine\social.py session_server\storytelling_session.py session_server\web_projection.py` -> passed.
- `python -m unittest tests.test_social_consequences -v` -> 11 tests passed.
- `python -m unittest tests.test_social_consequences tests.test_storytelling_session tests.test_exploration_procedures tests.test_dm_memory tests.test_web_server -v` -> 58 tests passed.

## 2026-04-10 - Campaign-Specific Social Content Rollout

### Scope
- Implement authored social content packs on top of the existing generic social-consequence runtime.
- Add reusable witness archetypes, scene/location norm profiles, faction and authority templates, NPC social templates, incident-to-consequence mappings, delayed propagation chains, and LMOP-specific bindings.
- Reuse the existing backend-authoritative incident, witness, norm, consequence, propagation, writeback, and projection systems instead of rebuilding them.

### Repo Inspection Summary
- The generic runtime already exists in `shared_types/social.py` and `rules_engine/social.py`; it handles typed relationship/reputation state, witness records, norm evaluation, incident logging, immediate consequence application, propagation queues, and DM/player projection separation.
- The current gap is authored content, not runtime mechanics. `SocialConsequenceEngine.__init__` still seeds Waterdeep/Watch/LMOP social content inline through hardcoded `location_labels`, `faction_labels`, `npc_factions`, `authority_by_location`, and a small `norm_profiles` set.
- `session_server/storytelling_session.py` already integrates the social engine into story spellcasting, exploration/influence updates, DM summaries, scene-state writeback, and NPC playbook writeback. `session_server/web_projection.py` already filters DM-only and private-controller social fallout correctly.
- Local campaign references exist and are usable: `campaigns/lmop/chapters/chapter-01/scene-00-waterdeep-briefing.md`, `campaigns/lmop/npcs/gundren-rockseeker.md`, `campaigns/lmop/npcs/sildar-hallwinter.md`, `campaigns/lmop/locations/waterdeep.md`, `campaigns/lmop/locations/high-road.md`, `campaigns/lmop/locations/triboar-trail.md`, and related DM scene-state / playbook files.
- There is no existing authored social-content pack layer for witness archetypes, faction templates, consequence mappings, or propagation chains, so this rollout needs to add one cleanly and then route the engine through it.

### Proposed Authored Template Structure
- Add `shared_types/social_content.py` for strongly typed authored-template schemas:
  - `WitnessArchetypeTemplate`
  - `WitnessTendencyProfile`
  - `FactionAuthorityTemplate`
  - `NpcSocialTemplate`
  - `IncidentConsequenceTemplate`
  - `PropagationChainTemplate`
  - `CampaignSocialContentPack`
  - `LocationSocialBinding`
  - `SceneSocialBinding`
- Add `rules_engine/social_content.py` for the authored content library and LMOP bundle loader/builder.
- Keep `rules_engine/social.py` as the authoritative consequence engine, but replace inline seed content with pack-driven labels, norms, faction bindings, witness archetype lookup, consequence template selection, and propagation-chain selection.
- Keep projections/writeback in the existing story/web memory path; only enrich what the engine emits and what the story session derives from it.

### Local Campaign Discovery Summary
- Confirmed canonical Waterdeep opening scene id: `scene-waterdeep-gundren-briefing`.
- Confirmed NPC ids: `gundren-rockseeker`, `sildar-hallwinter`.
- Confirmed location ids present locally: `waterdeep`, `high-road`, `triboar-trail`, `cragmaw-hideout`.
- `phandalin` is referenced heavily in travel/map content and summaries, but there is no standalone `campaigns/lmop/locations/phandalin.md` file in the current repo. Use the existing `phandalin` location id from map/travel content and keep the binding explicit rather than assuming a markdown location file exists.

### Design Direction
- Move authored LMOP/Waterdeep/Watch/Lords' Alliance defaults out of `SocialConsequenceEngine.__init__` and into an authored content pack that the engine consumes.
- Preserve the existing layered model: actual incident -> witness perception -> interpretation -> immediate consequence -> delayed propagation.
- Keep consequence selection content-driven: witness archetype + local/scene norms + faction/authority template + incident category/severity should produce authored consequence candidates, while the generic engine still applies the resulting typed state changes and scheduling.
- Preserve duplicate suppression by keeping incident dedupe and propagation dedupe in the engine and only letting content packs nominate candidates/chains.
- Keep DM/player separation strict: authored templates can raise hidden authority/rumor chains, but only DM-visible summaries should reveal them until they become party-known or public.

### Steps
- [x] Add typed authored social-content schemas and a campaign social-content pack module.
- [x] Author reusable witness archetypes, scene/location norms, faction/authority templates, NPC social templates, incident-consequence mappings, and propagation chains for the first LMOP/Waterdeep slice.
- [x] Integrate `SocialConsequenceEngine` with the authored content pack while preserving the generic runtime, dedupe, and precedence behavior.
- [x] Bind local campaign ids and scenes for Waterdeep, Gundren, Sildar, High Road, Triboar Trail, and Phandalin-facing references where local content exists.
- [x] Extend DM memory/writeback and DM/player projections only where needed to surface the authored consequence layer without leaking hidden state.
- [x] Add focused tests and LMOP fixtures for witness archetype resolution, norm precedence, incident-to-consequence mapping, rumor/authority chain suppression, helpful-vs-suspicious public magic, Gundren/Sildar/public-threat scenarios, and DM/player separation.
- [x] Run focused social suites plus impacted story/web/memory regressions, then document review and remaining gaps.

### Verification Plan
- `python -m py_compile shared_types\social.py shared_types\social_content.py rules_engine\social.py rules_engine\social_content.py session_server\storytelling_session.py session_server\web_projection.py tests\test_social_consequences.py`
- `python -m unittest tests.test_social_consequences -v`
- `python -m unittest tests.test_social_consequences tests.test_storytelling_session tests.test_dm_memory tests.test_web_server -v`


### Review
- Added typed authored content schemas in `shared_types/social_content.py` and the first LMOP/Waterdeep authored social pack in `rules_engine/social_content.py` instead of growing the hardcoded seed tables inside `SocialConsequenceEngine`.
- Rewired `rules_engine/social.py` so the existing authoritative runtime now resolves witness archetypes, scene/location/NPC norms, consequence templates, and propagation chains from the authored content pack while preserving incident dedupe, norm precedence, and propagation suppression.
- Bound the authored layer to the real local campaign ids for `scene-waterdeep-gundren-briefing`, `scene-00-high-road-journey`, `waterdeep`, `high-road`, `triboar-trail`, `phandalin`, `gundren-rockseeker`, and `sildar-hallwinter`.
- Extended the event surface so authored-template resolution and propagation-chain milestones are visible in the append-only log without moving authority out of the backend.
- Expanded `tests/test_social_consequences.py` from 11 to 18 cases, adding authored witness archetype resolution, scene-bound norm precedence, helpful-magic authored chain selection, guarded-enchantment template selection, Gundren employer-memory/public-threat behavior, duplicate chain suppression, and DM-only authored consequence projection checks.
- Verified the authored layer against focused social tests plus broader story/web/memory regressions.

### Verification
- `python -m py_compile shared_types\social.py shared_types\social_content.py shared_types\encounter_events.py rules_engine\social_content.py rules_engine\social.py session_server\storytelling_session.py tests\test_social_consequences.py` -> passed.
- `python -m unittest tests.test_social_consequences -v` -> 18 tests passed.
- `python -m unittest tests.test_social_consequences tests.test_storytelling_session tests.test_dm_memory tests.test_web_server -v` -> 55 tests passed.

### Remaining Gaps
- The authored social content currently lives in typed Python pack data under `rules_engine/social_content.py`; it is campaign-specific and reusable, but it is not yet externalized into campaign-authored JSON/markdown assets under `campaigns/lmop/`.
- This rollout covers the first LMOP/Waterdeep/High Road social slice with Gundren/Sildar and the main public-magic/threat/authority patterns. It does not yet attempt a full settlement-law or every-scene authored catalog for Phandalin and later chapters.






## 2026-04-13 - Tier-2 Advancement Content Rollout (Level-2 Spell Slice)

### Scope
- Start the Tier-2 rollout with the XPHB level-2 spell slice only, per the current user direction, without claiming the full Tier-2 milestone complete.
- Create the required Tier-2 repo skills and manifest/support-matrix scaffolding first, then implement only the level-2 spells that are clearly deterministic from the exact local XPHB text.
- Leave spells that depend on broader object, divination, illusion, summons, social-adjudication, or unresolved wording interpretation explicitly marked as clarification-needed instead of guessing.
- Require a dedicated directory, `IMPLEMENTATION.md`, executor wiring, and an individual 5-8 case test file for each implemented spell.
- Use multiple subagents for the spell families and wait for all of them before merging the final result.

### Repo Inspection Summary
- The current XPHB runtime is level-1-centric. Runtime support manifests exist only under `content/xphb/manifests/`, and `rules_engine/xphb_level1_registry.py` only exposes cantrip + level-1 spell/class-feature support.
- `rules_engine/capability_loader.py` is still the live spell capability builder. It contains the deterministic spell wiring, but it is currently a large centralized function rather than a per-item directory/executor system.
- `rules_engine/monster_loader.py` consumes `build_spell_capability_definition(...)` plus `spell_runtime_support_for(...)` to compile `SpellRecord`s. Tier-2 spell support therefore needs both runtime capability wiring and manifest-backed support lookup.
- Existing item content folders use `metadata.json`, `implementation.json`, and `README.md`, while tests currently live under `tests/xphb_level1_spells/<slug>/`. The user?s Tier-2 requirement is stricter: every item also needs its own `IMPLEMENTATION.md` and an individual test under the item directory.
- The local mirror currently exposes 63 XPHB level-2 spells. This spell-slice will classify each of them as either clearly deterministic in the current authoritative runtime or blocked pending clarification / broader subsystem work.

### Proposed Spell-Slice Schema
- Add Tier-2 spell manifests under `content/manifests/`:
  - `tier2_level2_spells_manifest.json`
  - `tier2_support_matrix.json`
- Each level-2 spell manifest entry must include:
  - `source_id`
  - `display_name`
  - `category`
  - `level`
  - `owning_directory`
  - `implementation_family`
  - `runtime_status`
  - `test_path`
  - `blocker_status`
  - `notes`
- Add a new Tier-2 spell registry/loader layer so per-item spell directories can own their own executor modules without pushing more hardcoded spell behavior into command handlers or UI code.

### Implementable Spell Classification (Initial)
- Planned deterministic in this slice:
  - `Aid`
  - `Arcane Vigor`
  - `Barkskin`
  - `Blindness/Deafness`
  - `Blur`
  - `Cloud of Daggers`
  - `Cordon of Arrows`
  - `Darkvision`
  - `Dragon's Breath`
  - `Enhance Ability`
  - `Flame Blade`
  - `Flaming Sphere`
  - `Heat Metal`
  - `Hold Person`
  - `Invisibility`
  - `Lesser Restoration`
  - `Magic Weapon`
  - `Melf's Acid Arrow`
  - `Mind Spike`
  - `Misty Step`
  - `Pass without Trace`
  - `Protection from Poison`
  - `Ray of Enfeeblement`
  - `Scorching Ray`
  - `Shatter`
  - `Silence`
  - `Spiritual Weapon`
- Explicit clarification / broader-system blockers for now:
  - `Alter Self`
  - `Animal Messenger`
  - `Arcane Lock`
  - `Augury`
  - `Beast Sense`
  - `Calm Emotions`
  - `Continual Flame`
  - `Crown of Madness`
  - `Darkness`
  - `Detect Thoughts`
  - `Enlarge/Reduce`
  - `Enthrall`
  - `Find Steed`
  - `Find Traps`
  - `Gentle Repose`
  - `Gust of Wind`
  - `Knock`
  - `Levitate`
  - `Locate Animals or Plants`
  - `Locate Object`
  - `Magic Mouth`
  - `Mirror Image`
  - `Moonbeam`
  - `Nystul's Magic Aura`
  - `Phantasmal Force`
  - `Prayer of Healing`
  - `Rope Trick`
  - `See Invisibility`
  - `Shining Smite`
  - `Spider Climb`
  - `Spike Growth`
  - `Suggestion`
  - `Summon Beast`
  - `Warding Bond`
  - `Web`
  - `Zone of Truth`

### Steps
- [ ] Create the required Tier-2 skills under `.agents/skills/` and scaffold Tier-2 manifests/support-matrix files under `content/manifests/`.
- [ ] Add the Tier-2 level-2 spell registry/loading layer so per-item spell executors can be wired through the shared runtime cleanly.
- [ ] Spawn multiple spell-family subagents, hand them disjoint level-2 spell sets plus the per-item directory/test requirements, and wait for all of them to finish.
- [ ] Merge the implemented spell directories, executor wiring, manifest updates, and per-item tests for the deterministic spell set.
- [ ] Add aggregate completeness checks for the level-2 spell slice: directory presence, `IMPLEMENTATION.md` presence, required sections, test-file presence, manifest/support-matrix registration, and no omitted in-scope targets.
- [ ] Run focused level-2 spell tests plus impacted runtime regressions, then update `tasks/SUMMARIES.md` with implemented counts and explicit remaining blockers.

### Verification Plan
- `python -m py_compile shared_types\xphb_content.py rules_engine\capability_loader.py rules_engine\monster_loader.py rules_engine\tier2_spell_registry.py tests\test_tier2_level2_spell_completeness.py`
- `python -m unittest discover -s content\xphb\spells\level-2 -p "test_*.py" -v`
- `python -m unittest tests.test_tier2_level2_spell_completeness -v`
- `python -m unittest tests.test_encounter_kernel tests.test_storytelling_session tests.test_web_server -v`

### Review
- Verified with `python -m py_compile shared_types\capabilities.py encounter_runtime\effect_execution.py tests\xphb_level2_spells\support.py content\xphb\spells\level-2\barkskin\executor.py content\xphb\spells\level-2\enhance-ability\executor.py content\xphb\spells\level-2\lesser-restoration\executor.py content\xphb\spells\level-2\barkskin\tests\test_barkskin.py content\xphb\spells\level-2\enhance-ability\tests\test_enhance_ability.py content\xphb\spells\level-2\lesser-restoration\tests\test_lesser_restoration.py`, plus direct runs of the three item test files with `PYTHONPATH=D:\DND-newagent`.
- Result: Barkskin passed 5 tests, Enhance Ability passed 5 tests, and Lesser Restoration passed 5 tests.
- Remaining gap: Aid is now closer because the shared runtime has a max-HP bonus primitive, but it stays out of scope for this request.

---

## 2026-04-13 Tier-2 Level-2 Spell Slice: Offensive/Control Pack

### Scope
- [x] Create per-spell folders for `blindness-deafness`, `cloud-of-daggers`, `cordon-of-arrows`, `hold-person`, `melf-s-acid-arrow`, `ray-of-enfeeblement`, `scorching-ray`, and `shatter`.
- [x] Add `definition.json`, `executor.py`, `registry.json`, `README.md`, `IMPLEMENTATION.md`, and `tests/test_<slug>.py` for each assigned spell.
- [x] Implement only the spells that can be expressed exactly with the current local mirror text and shared runtime primitives, without guessing unsupported mechanics.
- [x] Document any exact-blockers in each spell?s `IMPLEMENTATION.md` using the required sections.
- [x] Keep shared manifests and shared registry files untouched, per user instruction.

### Implementation Steps
- [x] Classify each assigned spell against the local XPHB mirror text and current runtime primitives.
- [x] Write local per-spell executor modules and capability-definition builders for the exact-implementable spells.
- [x] Write local registry/definition metadata files for every assigned spell directory.
- [x] Add one test module per spell directory that exercises the spell-specific cast shape and core behavior or the blocker contract.
- [x] Record any shared-runtime activation gaps explicitly in the spell implementation notes instead of silently omitting them.

### Verification Plan
- [x] `python -m py_compile shared_types\capabilities.py encounter_runtime\effect_execution.py content\xphb\spells\level-2\blindness-deafness\executor.py content\xphb\spells\level-2\hold-person\executor.py content\xphb\spells\level-2\melf-s-acid-arrow\executor.py content\xphb\spells\level-2\blindness-deafness\tests\test_blindness_deafness.py content\xphb\spells\level-2\hold-person\tests\test_hold_person.py content\xphb\spells\level-2\melf-s-acid-arrow\tests\test_melf_s_acid_arrow.py`
- [ ] `python -m unittest tests.test_effect_execution -v` (blocked by an unrelated syntax error in `rules_engine/capability_loader.py`)
- [ ] Direct per-item test execution via the standalone modules is blocked by the same unrelated loader import syntax error.

### Review
- Completed the exact-fit subset only: `Blindness/Deafness`, `Hold Person`, and `Melf's Acid Arrow`.
- `Blindness/Deafness` now builds from the local XPHB text, supports blinded/deafened selection, slot-based extra targets, and the repeat-save active effect flow.
- `Hold Person` now mirrors the existing deterministic loader behavior in a per-item executor and keeps the slot-based extra humanoid target gate.
- `Melf's Acid Arrow` now uses a spell-attack gate, full on-hit acid damage, a delayed end-of-next-turn acid burn, and half damage on miss, all slot-scaled.
- Verification was limited by an unrelated `rules_engine/capability_loader.py` syntax error (`if name == ''Invisibility''`) that prevents the broader repo test harness from importing the shared loader.

## 2026-04-13 - Tier-2 Split-Target Active-Effect Primitive

### Scope
- [ ] Implement split-target active-effect handling for `Blindness/Deafness`, `Enhance Ability`, `Hold Person`, and `Invisibility`.
- [ ] Preserve one concentration source while allowing independent per-target expiry and choice semantics.
- [ ] Add or update each owned spell directory's `IMPLEMENTATION.md` and per-item test file under the spell directory.
- [ ] Keep shared manifests and shared registries untouched.

### Implementation Steps
- [ ] Add the minimum shared runtime primitive to model one source concentration effect with multiple child target effects.
- [ ] Update the four owned spell executors to use the shared primitive exactly from local XPHB text.
- [ ] Write 5-8 focused cases per owned spell directory, including multi-target upcast and independent expiry behavior where applicable.
- [ ] Reconcile the existing item notes/readmes so they describe the exact local-text cast syntax and edge cases.

### Verification Plan
- [ ] `python -m py_compile shared_types\capabilities.py shared_types\encounter_models.py encounter_runtime\effect_execution.py encounter_runtime\kernel.py content\xphb\spells\level-2\blindness-deafness\executor.py content\xphb\spells\level-2\enhance-ability\executor.py content\xphb\spells\level-2\hold-person\executor.py content\xphb\spells\level-2\invisibility\executor.py`
- [ ] Direct execution of the four owned spell test files with `PYTHONPATH=d:\DND-newagent`
- [ ] Focused regression checks for existing level-2 spell suites impacted by the shared active-effect primitive

### Review
- Pending implementation.


## 2026-04-13 - XPHB Tier-2 Spells: Aid And Arcane Vigor

### Scope
- Own and update only `content/xphb/spells/level-2/aid` and `content/xphb/spells/level-2/arcane-vigor`.
- Use the current local XPHB mirror text only; do not guess beyond the local source.
- Avoid shared Tier-2 manifest or registry edits.
- Allow only the minimal shared capability/runtime changes needed for these two spells to be exact.

### Repo Inspection Summary
- Both owned spell folders already exist with the required per-item files, but both are still marked blocked from stale pre-primitive notes.
- `ActiveEffectDefinition.max_hit_points_bonus` plus `HitPointMaximumAdjustedEvent` now support Aid's core max/current HP lifecycle with symmetric rollback.
- `SpendHitDiceHealingEffectDef` exists and the encounter kernel compiles with it, but exact local-text support still needs higher-slot scaling and spell-text healing semantics rather than rest-style assumptions.
- The local XPHB mirror confirms Aid lasts 8 hours, targets up to three creatures within 30 feet, grants +5 current/max HP, and increases that HP bonus by 5 per slot level above 2.
- The local XPHB mirror confirms Arcane Vigor is a bonus-action self spell, spends one or two unused Hit Dice, heals by the dice total plus the caster's spellcasting ability modifier, and adds one more die per slot level above 2.

### Steps
- [x] Record the correction in `tasks/LESSONS.md` and track this slice here.
- [x] Add the minimal shared capability/runtime scaling needed for exact Aid and Arcane Vigor slot-level behavior.
- [x] Implement `content/xphb/spells/level-2/aid` exactly from the local mirror and replace the blocked tests/docs.
- [x] Implement `content/xphb/spells/level-2/arcane-vigor` exactly from the local mirror and replace the blocked tests/docs.
- [x] Run focused compile and unit-test verification for the touched runtime and owned spell folders.
- [x] Append review notes here and summarize the task in `tasks/SUMMARIES.md`.

### Verification Plan
- `python -m py_compile shared_types\capabilities.py encounter_runtime\effect_execution.py content\xphb\spells\level-2\aid\executor.py content\xphb\spells\level-2\arcane-vigor\executor.py content\xphb\spells\level-2\aid\tests\test_aid.py content\xphb\spells\level-2\arcane-vigor\tests\test_arcane_vigor.py`
- `python -m unittest discover -s content\xphb\spells\level-2\aid\tests -p "test_aid.py" -v`
- `python -m unittest discover -s content\xphb\spells\level-2\arcane-vigor\tests -p "test_arcane_vigor.py" -v`
- `python -m unittest discover -s content\xphb\spells\level-2\melf-s-acid-arrow\tests -p "test_melf_s_acid_arrow.py" -v`

### Review
- Implemented both owned spell folders exactly from the local XPHB mirror text and replaced the stale blocked metadata, docs, executors, and tests.
- Added the minimum shared runtime support needed for exact slot-level behavior: `ParameterizedActiveEffectDef` can now scale `max_hit_points_bonus`, and `SpendHitDiceHealingEffectDef` now supports slot-scaled die-count limits plus spell-text dice spending semantics.
- Tightened the shared Hit Die spell effect so Arcane Vigor spends the exact requested unused dice, applies the spellcasting modifier once, does not add Constitution per die, and still spends all chosen dice even if healing caps before the rolled total matters.
- Verified with:
  - `python -m py_compile shared_types\capabilities.py encounter_runtime\effect_execution.py content\xphb\spells\level-2\aid\executor.py content\xphb\spells\level-2\arcane-vigor\executor.py content\xphb\spells\level-2\aid\tests\test_aid.py content\xphb\spells\level-2\arcane-vigor\tests\test_arcane_vigor.py`
  - `python -m unittest discover -s content\xphb\spells\level-2\aid\tests -p "test_aid.py" -v`
  - `python -m unittest discover -s content\xphb\spells\level-2\arcane-vigor\tests -p "test_arcane_vigor.py" -v`
  - `python -m unittest discover -s content\xphb\spells\level-2\melf-s-acid-arrow\tests -p "test_melf_s_acid_arrow.py" -v`
## 2026-04-17 - Live Web UI Story Script Injection

### Scope
- Integrate the full-story user-test script flow with the actual browser demo instead of the in-memory replay harness.
- Keep the browser portals connected as the visible controller clients while a separate local automation path injects the scripted controller inputs.
- Use the live DM runtime from the running web demo server so LLM narration and thinking feedback come from the real model, not queued script payloads.
- Keep the change scoped to the user-test and web-demo path; do not introduce a second authoritative runtime or bypass the existing typed session flow.

### Design Direction
- Add a local automation API to the user-test web demo server that can submit authoritative controller input and fetch projected controller state without taking over the controller websocket.
- Reuse the existing session `handle_input(...)` path so every scripted input is processed exactly like a browser-entered command or declaration.
- Let the browser remain the only websocket client for each controller. The automation runner should drive the session through HTTP, while the browser receives the same echo, thinking, prompt, and view updates in real time.
- Keep the current deterministic fake-LLM replay harness intact for tests that need scripted DM output. Add a separate live-web runner and live-web script files for the browser-integrated path.

### Steps
- [x] Add a local automation HTTP surface to `SessionWebServer` for controller-state snapshots and injected controller input, with broadcast behavior that mirrors browser-originated commands.
- [x] Enable the automation API in `user-test/web_story_demo_server.py` and expose the live-web user-test path in the full-story-demo docs.
- [x] Add a live-web runner under `user-test/` that reads a scripted controller-input file and drives a running web demo server without supplying scripted LLM output.
- [x] Add at least one live-web full-story script file that uses player declarations/commands and explicit prompt-aware steps instead of queued DM payloads.
- [x] Add focused tests for the automation API and the live-web runner path against the browser web server.
- [x] Run the affected verification suite, then record results here and summarize the request in `tasks/SUMMARIES.md`.

### Verification Plan
- `python -m py_compile session_server\web_server.py user-test\web_story_demo_server.py user-test\web_story_demo_live_runner.py tests\test_web_server.py tests\test_story_demo_replay_scripts.py`
- `python -m unittest tests.test_web_server -v`
- `python -m unittest tests.test_story_demo_replay_scripts -v`

### Review
- Added a local automation API to [session_server/web_server.py](/d:/DND-newagent/session_server/web_server.py) with `GET /automation/state?controller_id=...` and `POST /automation/input`, plus authoritative injected-input handling that reuses the normal session command path and still pushes browser `echo`, `thinking`, `prompt`, and `view` updates to the connected controller portal.
- Enabled that API by default in [user-test/web_story_demo_server.py](/d:/DND-newagent/user-test/web_story_demo_server.py), then added the new live-web driver [user-test/web_story_demo_live_runner.py](/d:/DND-newagent/user-test/web_story_demo_live_runner.py) and the prompt-aware browser script [user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json](/d:/DND-newagent/user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json).
- Updated the user-test docs in [user-test/full-story-demo/README.md](/d:/DND-newagent/user-test/full-story-demo/README.md) and [docs/web-frontend.md](/d:/DND-newagent/docs/web-frontend.md) so the browser-integrated flow is explicit.
- Kept the older fake-LLM replay path intact and refreshed a few stale wording assertions in the legacy replay JSON so its existing regression tests still pass against the current summary text.
- Verification:
  - `python -m py_compile session_server\web_server.py user-test\web_story_demo_server.py user-test\web_story_demo_live_runner.py tests\test_web_server.py tests\test_story_demo_replay_scripts.py`
  - `python -m unittest tests.test_web_server -v`
  - `python -m unittest tests.test_story_demo_replay_scripts -v`
- Observed results:
  - all compile targets passed
  - `tests.test_web_server` passed 19 tests, including the new automation API and live-web runner integration cases
  - `tests.test_story_demo_replay_scripts` passed 2 tests after updating stale summary assertions
  - the websocket library still emits a noisy shutdown-time `AssertionError` trace during one existing prompt test, but the test suite itself passes and this change did not introduce a failing assertion

## 2026-05-01 - Point Cursor And Local Codex To 0.128.0

### Scope
- Make the local shell `codex` command resolve to the installed Codex CLI `0.128.0`.
- Make Cursor's OpenAI/ChatGPT plugin use the same `0.128.0` Codex executable if the extension exposes no safer path override.
- Preserve the `goals` feature flag that was already enabled.
- Avoid changing PowerShell execution policy or deleting extension files.

### Steps
- [x] Inspect the current PATH, npm shim, and Cursor extension bundled executable.
- [x] Add or refresh a user-level `codex.exe` shim that points to the npm-installed native CLI.
- [x] Update the user PATH order so new terminals prefer the npm shim over Cursor's bundled binary.
- [x] Inspect Cursor extension metadata for a configurable Codex path before patching bundled files.
- [x] Use Cursor's `chatgpt.cliExecutable` override instead of replacing the bundled `codex.exe`.
- [x] Verify `codex --version`, the npm shim, and Cursor's configured executable all report `0.128.0`.
- [x] Record review notes and append a summary.

### Verification Plan
- `where.exe codex`
- `codex --version`
- `C:\Users\Shengqi Li\AppData\Roaming\npm\codex.cmd --version`
- configured Cursor `chatgpt.cliExecutable --version`
- `codex features list`

### Review
- Cursor's extension exposes `chatgpt.cliExecutable`, so no bundled extension executable was replaced. `C:\Users\Shengqi Li\AppData\Roaming\Cursor\User\settings.json` now points that setting to the npm-installed native Codex `0.128.0` executable.
- Added `C:\Users\Shengqi Li\AppData\Roaming\npm\codex.exe` as a hardlink to the installed native executable and moved the blocked npm `codex.ps1` shim to `codex.ps1.disabled-by-codex-setup`, so PowerShell resolves `codex` without changing execution policy.
- Updated the persisted user PATH outside the sandbox so `C:\Users\Shengqi Li\AppData\Roaming\npm` comes before Cursor's bundled extension path in new terminals.
- Verification:
  - elevated `where.exe codex` listed the npm Codex entries before the Cursor-bundled `0.125.0` executable
  - elevated `codex --version` returned `codex-cli 0.128.0`
  - Cursor's configured `chatgpt.cliExecutable` path returned `codex-cli 0.128.0`
  - elevated `codex features list` showed `goals` as `true`
