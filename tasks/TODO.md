## 2026-05-14 - Legal Attack Probe Dataset

### Scope
- Add a focused scenario that produces valid `/attack` transition rows without changing the existing random-legal benchmark.
- Keep the attack command snapshot-backed and executable through the normal session/trajectory pipeline.
- Add campaign-root support so tests and probe runs can use sanitized campaign copies while local campaign notes are dirty.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/tests/task notes for this move.

### Steps
- [x] Try a live `legal-attack` policy and reject it after movement/pathfinding proved too slow and brittle.
- [x] Add `campaign_root` plumbing to the batch runner and CLI.
- [x] Add `lmop_legal_attack_probe` as a controlled attack-data scenario.
- [x] Add a regression test proving the probe emits valid attack rows with no baseline errors.
- [x] Re-run random-legal regression tests.
- [x] Run a direct probe batch and inspect attack/error counts.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile user-test\run_training_batch.py tests\test_training_batch.py`
- [x] `python -m unittest tests.test_training_batch.TrainingBatchTests.test_legal_attack_probe_batch_adds_valid_attack_rows tests.test_training_batch.TrainingBatchTests.test_random_legal_combat_commands_use_available_attack_choices tests.test_training_batch.TrainingBatchTests.test_random_legal_first_combat_batch_uses_baseline_actions -v`
- [x] direct `run_batch(... scenario_id='lmop_legal_attack_probe', campaign_root=<sanitized copy>)` probe
- [x] `git diff --check -- user-test/run_training_batch.py tests/test_training_batch.py tasks/TODO.md tasks/SUMMARIES.md`

### Review
- Result: the legal-attack probe produced 81 transition rows, 0 errors, and 1 valid `/attack player-1 dagger-melee-dex monster-goblin-1` row in `C:\tmp\legal-attack-probe-final\batch\lmop_legal_attack_probe-batch-20260514T221637Z-04149502\training_transitions.jsonl`.
- Note: tests use a sanitized temp campaign copy because local dirty campaign summaries currently include Markdown without front matter.
- Next: collect this probe into the combined training dataset and rerun supervised/command-head preflights to confirm `/attack` labels appear before MosaicML training.

## 2026-05-14 - Snapshot-Constrained Random-Legal Attacks

### Scope
- Constrain random-legal weapon attacks to the runtime snapshot's available attack choices.
- Avoid reintroducing the movement-aware attack approach experiment into this small fix.
- Add focused coverage for unavailable known attacks such as stowed or unheld weapons.
- Verify the random-legal batch still completes with zero baseline errors.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/tests/task notes for this move.

### Steps
- [x] Inspect the random-legal generator and runtime attack choice source.
- [x] Remove the movement-aware approach experiment from the current working tree.
- [x] Pass snapshot `available_choices` into random-legal combat command generation.
- [x] Filter attack profiles through snapshot attack option ids.
- [x] Add a focused regression test for snapshot-constrained attacks.
- [x] Run compile checks, focused tests, integration, and a direct batch probe.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile user-test\run_training_batch.py tests\test_training_batch.py`
- [x] `python -m unittest tests.test_training_batch.TrainingBatchTests.test_random_legal_combat_commands_use_available_attack_choices -v`
- [x] `python -m unittest tests.test_training_batch.TrainingBatchTests.test_random_legal_first_combat_batch_uses_baseline_actions -v`
- [x] direct `run_batch(... policy='random-legal', baseline_seed=123, max_combat_turns=120)` probe
- [x] `git diff --check -- user-test/run_training_batch.py tests/test_training_batch.py`

### Review
- Result: random-legal attack generation now uses runtime `available_choices['attacks']`, so unavailable known attacks are not emitted as baseline actions.
- Probe: `C:\tmp\random-legal-check-final\lmop_first_combat-batch-20260514T175902Z-3a3ab57b\training_transitions.jsonl` had 147 rows, 0 errors, and 0 `/attack` rows.
- Next: create a dedicated legal-attack data pass, scenario, or movement-aware benchmark to generate positive valid `/attack` examples for MosaicML training.

## 2026-05-14 - Filter Invalid Supervised Actions

### Scope
- Exclude errored transitions from supervised imitation loaders.
- Keep errored transitions available to reward/preference workflows.
- Add regression fixtures for baseline, trainable policy, and command-head preflights.
- Rerun the real baseline and command-head preflight against the filtered supervised corpus.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Trace why combat `arg_2` candidate coverage was zero.
- [x] Confirm all current `/attack` labels are errored invalid actions.
- [x] Filter errored rows from supervised baseline and trainable-policy loaders.
- [x] Add focused regression coverage across supervised preflights.
- [x] Rerun the real filtered supervised baseline.
- [x] Rerun the real command-head preflight against the filtered baseline.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\supervised_baseline.py training\trainable_policy.py training\command_head_policy.py tests\test_supervised_baseline.py tests\test_trainable_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_supervised_baseline tests.test_trainable_policy tests.test_command_head_policy -v`
- [x] `python user-test\run_supervised_baseline.py --recipe <latest training_recipe.json> --output-dir runs\training-runs`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <filtered supervised_baseline_report.json> --output-dir runs\training-runs`
- [ ] `git diff --check -- README.md training\supervised_baseline.py training\trainable_policy.py tests\test_supervised_baseline.py tests\test_trainable_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: filtered supervised rows are 726 instead of 931, removing 205 errored actions from imitation. The filtered baseline eval accuracy is 0.8069; the command-head preflight is 0.8207, a +0.0138 delta.
- Finding: after filtering, the current supervised corpus has 0 valid `/attack` labels, so the former weapon mismatch was not a canonicalization issue inside the model. It was invalid attack data entering supervised imitation.
- Reports: `runs\training-runs\supervised-baseline-20260514T170448Z-60af5763\supervised_baseline_report.json`; `runs\training-runs\mosaicml-command-head-policy-20260514T170505Z-1ed87611\command_head_policy_report.json`

## 2026-05-14 - Candidate-Aware Argument Diagnostics

### Scope
- Add explicit argument candidate sets for literal commands, actors, targets, and attack option ids.
- Use conservative candidate-aware decoding for actor/target slots.
- Report per-argument candidate coverage during evaluation.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect current argument feature and evaluation helpers.
- [x] Add argument candidate extraction helpers.
- [x] Use candidate-aware decoding for command arguments.
- [x] Add candidate coverage metrics to reports.
- [x] Add focused tests for candidate extraction and report coverage.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_command_head_policy -v`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: exact eval stayed at 0.6935 vs. the 0.6828 frequency baseline. Candidate coverage explained the remaining split: combat `arg_1` and `arg_3` coverage were 1.0000, but combat `arg_2` coverage was 0.0000 over 30 rows, meaning target candidates exist but weapon candidates do not match the supervised command vocabulary.
- Report: `runs\training-runs\mosaicml-command-head-policy-20260514T164514Z-965a568e\command_head_policy_report.json`

## 2026-05-14 - Combat Argument Choice Features

### Scope
- Add non-leaky command-argument features from attack option ids and labels.
- Add literal slash-command candidate argument features when full commands are available.
- Add visible combat actor and target-candidate features from observation summaries.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect current command feature helpers and combat row shape.
- [x] Add attack-option argument features.
- [x] Add literal command candidate argument features.
- [x] Add visible combat actor target features.
- [x] Add focused tests for argument choice features.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_command_head_policy -v`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: argument choice features kept overall exact eval at 0.6935 vs. the 0.6828 frequency baseline. `command_arg_2` stayed at 0.0714, while target-slot `command_arg_3` improved from 0.0400 to 0.0800 overall and in `lmop_first_combat`.
- Report: `runs\training-runs\mosaicml-command-head-policy-20260514T162824Z-01c73d15\command_head_policy_report.json`

## 2026-05-14 - Combat Choice Family Features

### Scope
- Add non-leaky combat command-family features from available action option groups and ids.
- Infer command-family availability from UI option ids such as `attack`, `dodge`, and attack choice groups.
- Keep the trainer dependency-free and MosaicML-shaped.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect combat dataset available-action shape.
- [x] Add command-specific feature augmentation.
- [x] Add option-id to command-family inference.
- [x] Add focused tests for inferred available-family features.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_command_head_policy -v`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: available-choice family features improved overall exact eval from 0.6882 to 0.6935, doubling the margin over the frequency baseline to +0.0108. `lmop_first_combat` exact accuracy improved from 0.3012 to 0.3133, while the broader combat runtime bucket stayed at 0.3478.
- Report: `runs\training-runs\mosaicml-command-head-policy-20260514T161705Z-1f699892\command_head_policy_report.json`

## 2026-05-14 - Combat Command Family Constraints

### Scope
- Constrain combat command-family decoding to locally available slash-command families when possible.
- Keep natural-action family behavior for non-combat rows.
- Document the command-family constraint in the training workflow.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect command-family and available-command prediction helpers.
- [x] Add available command-family candidate extraction.
- [x] Constrain combat command-family decoding before argument decoding.
- [x] Add focused tests for combat family constraints.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_command_head_policy -v`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: combat command-family constraints kept the aggregate result unchanged at 0.6882 exact eval vs. the 0.6828 frequency baseline. Combat runtime exact accuracy remained 0.3478, so the constraint is a legality guardrail rather than the missing combat signal.
- Report: `runs\training-runs\mosaicml-command-head-policy-20260514T160720Z-459207b6\command_head_policy_report.json`

## 2026-05-14 - Candidate-Constrained Command Arguments

### Scope
- Constrain slash-command argument decoding to locally available commands when possible.
- Keep fallback behavior for rows without available command candidates.
- Document the new decoding shape.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect command-head prediction and available-action feature helpers.
- [x] Add available-command candidate extraction.
- [x] Constrain argument head decoding by predicted command family.
- [x] Add focused tests for candidate-constrained decoding.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_command_head_policy -v`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: candidate-constrained argument decoding kept the same aggregate result as the previous multi-head run: 0.6882 exact eval vs. the 0.6828 frequency baseline, with family accuracy 0.7097 and combat runtime exact accuracy 0.3478. The change still matters because slash arguments now stay inside locally available commands whenever the row supplies command candidates; the unchanged score means the next improvement should target combat command-family choice.
- Report: `runs\training-runs\mosaicml-command-head-policy-20260514T155625Z-0c3cb0c6\command_head_policy_report.json`

## 2026-05-14 - Multi-Head Command Policy

### Scope
- Add the first local multi-head command policy trainer.
- Train separate family, natural-action, and slash-command argument heads.
- Compare multi-head output with the supervised baseline.
- Keep the trainer dependency-free and MosaicML-shaped.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect reusable trainable policy helpers.
- [x] Add multi-head command policy module.
- [x] Add CLI wrapper under `user-test`.
- [x] Add focused tests for generated heads and metrics.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py`
- [x] `python -m unittest tests.test_command_head_policy -v`
- [x] `python user-test\train_command_head_policy.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\command_head_policy.py user-test\train_command_head_policy.py tests\test_command_head_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: after adding an argument-count head so slash commands only compose the predicted number of arguments, the multi-head preflight beat the frequency baseline overall at 0.6882 vs. 0.6828. Family accuracy was 0.7097 and combat runtime exact accuracy matched the baseline at 0.3478. Argument heads remain uneven: `command_arg_1` was strong at 0.9250, while `command_arg_2` was 0.0536 and `command_arg_3` was 0.0400, so target/weapon-style slots need the next improvement.
- Report: `runs\training-runs\mosaicml-command-head-policy-20260514T154351Z-0ac9324e\command_head_policy_report.json`

## 2026-05-14 - Command Head Recommendations

### Scope
- Add an explicit multi-head command policy recommendation to trainable policy reports.
- Use component accuracy to choose family and weak argument heads.
- Render the recommendation in Markdown.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect component metric output.
- [x] Add command-head recommendation JSON.
- [x] Render command-head recommendations in Markdown.
- [x] Add focused tests for recommendation output.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\trainable_policy.py user-test\train_policy_mosaicml.py tests\test_trainable_policy.py`
- [x] `python -m unittest tests.test_trainable_policy -v`
- [x] `python user-test\train_policy_mosaicml.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\trainable_policy.py tests\test_trainable_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: the preflight recommended `multi_head_command_policy`: required `command_family` head at 0.6989 family accuracy, plus `command_arg_2` at 0.0714 and `command_arg_3` at 0.0400 because both weak argument components were below the 0.50 threshold with at least 10 eval examples.

## 2026-05-14 - Command Component Diagnostics

### Scope
- Add command-component accuracy to trainable policy reports.
- Break slash commands into family plus argument-position diagnostics.
- Keep the trainer local-runnable and dependency-free.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect current trainable policy metric shape.
- [x] Add component-level accuracy metrics.
- [x] Render eval component accuracy in Markdown.
- [x] Add focused tests for component metrics.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\trainable_policy.py user-test\train_policy_mosaicml.py tests\test_trainable_policy.py`
- [x] `python -m unittest tests.test_trainable_policy -v`
- [x] `python user-test\train_policy_mosaicml.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\trainable_policy.py tests\test_trainable_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: component diagnostics passed against the latest recipe and baseline. Overall exact eval stayed 0.6935, family eval was 0.6989, slash arg_1 accuracy was 0.9250, arg_2 accuracy was 0.0714, and arg_3 accuracy was 0.0400, indicating weapon/target-style argument prediction is the main weak point.

## 2026-05-14 - Combat Policy Metrics

### Scope
- Add action-family accuracy to trainable policy reports.
- Add non-leaky combat state and available-choice features.
- Keep the MosaicML-shaped entrypoint dependency-free and local-runnable.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect actual combat transition rows.
- [x] Add action-family accuracy to metrics and Markdown.
- [x] Add combat state and available-choice features.
- [x] Add focused tests for family accuracy and feature growth.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\trainable_policy.py user-test\train_policy_mosaicml.py tests\test_trainable_policy.py`
- [x] `python -m unittest tests.test_trainable_policy -v`
- [x] `python user-test\train_policy_mosaicml.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\trainable_policy.py tests\test_trainable_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: v2 sparse features passed against the latest recipe and baseline. Overall exact eval stayed 0.6935, family eval was 0.6989, combat exact matched the baseline at 0.3478, `lmop_first_combat` exact stayed 0.3133, and `lmop_first_combat` family accuracy was 0.3253.

## 2026-05-14 - Trainable Policy Preflight

### Scope
- Add the first trainable policy entrypoint shaped for MosaicML.
- Keep the first implementation dependency-free and runnable locally.
- Consume `training_recipe.json` plus the supervised baseline report.
- Emit model, JSON report, Markdown report, and baseline comparisons.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect transition row shape and MosaicML plan expectations.
- [x] Add a sparse linear trainable policy module.
- [x] Add the `user-test/train_policy_mosaicml.py` CLI wrapper.
- [x] Add focused tests for model/report output and baseline schema validation.
- [x] Run the preflight against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\trainable_policy.py user-test\train_policy_mosaicml.py tests\test_trainable_policy.py`
- [x] `python -m unittest tests.test_trainable_policy -v`
- [x] `python user-test\train_policy_mosaicml.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\training-runs`
- [x] `git diff --check -- README.md training\trainable_policy.py user-test\train_policy_mosaicml.py tests\test_trainable_policy.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: sparse linear preflight passed against the latest recipe and baseline. Overall eval improved from 0.6828 to 0.6935, `lmop_first_combat` improved from 0.2892 to 0.3133, storytelling improved from 0.8803 to 0.9060, and combat runtime dipped from 0.3478 to 0.3333.

## 2026-05-14 - MosaicML Training Plan

### Scope
- Add a deterministic MosaicML GPU training handoff plan.
- Consume the existing `training_recipe.json` and supervised baseline report.
- Record objectives, datasets, local preflight status, baseline targets, and weak eval slices.
- Keep generated plan outputs out of git.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect recipe, no-op, and supervised baseline report shapes.
- [x] Add a MosaicML training plan module.
- [x] Add a CLI wrapper under `user-test`.
- [x] Add focused tests for plan output and invalid baseline handling.
- [x] Run the MosaicML plan generator against the latest local recipe and baseline report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\mosaicml_plan.py user-test\plan_mosaicml_training.py tests\test_mosaicml_plan.py`
- [x] `python -m unittest tests.test_mosaicml_plan -v`
- [x] `python user-test\plan_mosaicml_training.py --recipe <latest training_recipe.json> --baseline-report <latest supervised_baseline_report.json> --output-dir runs\mosaicml-plans`
- [x] `git diff --check -- README.md training\mosaicml_plan.py user-test\plan_mosaicml_training.py tests\test_mosaicml_plan.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: MosaicML handoff plan passed against the latest local recipe and baseline report. It recorded supervised and preference objectives, transition and preference datasets, aggregate eval target 0.6828 -> 0.7328, `lmop_first_combat` target 0.2892 -> 0.3892, and combat runtime target 0.3478 -> 0.4478.

## 2026-05-14 - Scenario-Aware Baseline Evaluation

### Scope
- Add scenario-aware metric breakdowns to the supervised baseline report.
- Keep the report deterministic and local-only for MosaicML preflight.
- Document that real GPU training will run on MosaicML.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect current supervised baseline report shape.
- [x] Add grouped metrics by scenario and runtime mode.
- [x] Render held-out grouped metrics in Markdown.
- [x] Add focused tests for grouped metric output.
- [x] Document MosaicML as the intended GPU training target.
- [x] Run the scenario-aware baseline against the latest local recipe.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\supervised_baseline.py user-test\run_supervised_baseline.py tests\test_supervised_baseline.py`
- [x] `python -m unittest tests.test_supervised_baseline -v`
- [x] `python user-test\run_supervised_baseline.py --recipe <latest training_recipe.json> --output-dir runs\training-runs --split-strategy hash`
- [x] `git diff --check -- README.md training\supervised_baseline.py tests\test_supervised_baseline.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: scenario-aware baseline passed against the latest recipe with 745 train rows and 186 eval rows. Overall eval accuracy was 0.6828. Runtime-mode eval accuracy split was combat 0.3478 over 69 rows and storytelling 0.8803 over 117 rows. Scenario eval accuracy split was `lmop_first_combat` 0.2892 over 83 rows and `lmop_story_opening_choices` 1.0000 over 103 rows.

## 2026-05-14 - Hash Split Baseline Evaluation

### Scope
- Add a deterministic hash split to the supervised action baseline.
- Keep the old tail split available for comparison.
- Report train/eval coverage counts by scenario, runtime mode, source, and agent.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect current supervised baseline split and report shape.
- [x] Add hash/tail split strategy support.
- [x] Add split coverage counts to JSON/Markdown reports.
- [x] Add focused tests for hash split behavior and invalid strategy handling.
- [x] Run the hash-split baseline against the latest local recipe.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- [x] `python -m py_compile training\supervised_baseline.py user-test\run_supervised_baseline.py tests\test_supervised_baseline.py`
- [x] `python -m unittest tests.test_supervised_baseline -v`
- [x] `python user-test\run_supervised_baseline.py --recipe <latest training_recipe.json> --output-dir runs\training-runs --split-strategy hash`
- [ ] `git diff --check -- README.md training\supervised_baseline.py user-test\run_supervised_baseline.py tests\test_supervised_baseline.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Result: hash-split baseline passed against the latest recipe with 745 train rows, 186 eval rows, eval accuracy 0.6828, eval negative log loss 1.2376, and train/eval coverage across both scenarios and runtime modes.

## 2026-05-14 - Supervised Action Baseline

### Scope
- Add a lightweight supervised baseline trainer for the `supervised_action_prediction` objective.
- Use the recipe's transition dataset and avoid external ML dependencies.
- Emit model, JSON report, Markdown report, accuracy, and smoothed loss artifacts.
- Keep generated baseline run outputs out of git.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect the no-op trainer and recipe objective shape.
- [x] Add a supervised action-frequency baseline module.
- [x] Add a CLI wrapper under `user-test`.
- [x] Add focused tests for metric generation and missing-objective handling.
- [x] Run the baseline against the latest local recipe.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- `python -m py_compile training\supervised_baseline.py user-test\run_supervised_baseline.py tests\test_supervised_baseline.py`
- `python -m unittest tests.test_supervised_baseline -v`
- `python user-test\run_supervised_baseline.py --recipe <latest training_recipe.json> --output-dir runs\training-runs`
- `git diff --check -- README.md training\supervised_baseline.py user-test\run_supervised_baseline.py tests\test_supervised_baseline.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Pending implementation.

## 2026-05-14 - No-Op Trainer Accounting Pass

### Scope
- Add a no-op trainer backend shim that consumes `training_recipe.json`.
- Count observed dataset rows per objective and compare them with planned recipe counts.
- Write JSON/Markdown run reports without updating model weights.
- Keep generated training run outputs out of git.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect the recipe schema and latest generated recipe output.
- [x] Add a no-op trainer accounting module.
- [x] Add a CLI wrapper under `user-test`.
- [x] Add focused tests for accounting success and mismatch handling.
- [x] Run the no-op trainer against the latest local recipe.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- `python -m py_compile training\training_noop.py user-test\run_training_noop.py tests\test_training_noop.py`
- `python -m unittest tests.test_training_noop -v`
- `python user-test\run_training_noop.py --recipe <latest training_recipe.json> --output-dir runs\training-runs`
- `git diff --check -- README.md training\training_noop.py user-test\run_training_noop.py tests\test_training_noop.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Pending implementation.

## 2026-05-13 - Training Recipe Planner

### Scope
- Add a trainer-facing dry-run recipe generated from `training_smoke_report.json`.
- Include objective selection for supervised action prediction and preference ranking.
- Record dataset paths, counts, readiness status, smoke checks, and planned next commands.
- Keep generated recipe outputs out of git.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect the smoke report shape and existing training helpers.
- [x] Add a training recipe planner module.
- [x] Add a CLI wrapper under `user-test`.
- [x] Add focused tests for pass/fail smoke report handling.
- [x] Run the recipe planner against the latest local smoke report.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- `python -m py_compile training\training_recipe.py user-test\plan_training_recipe.py tests\test_training_recipe.py`
- `python -m unittest tests.test_training_recipe -v`
- `python user-test\plan_training_recipe.py --smoke-report <latest training_smoke_report.json> --output-dir runs\training-recipes`
- `git diff --check -- README.md training\training_recipe.py user-test\plan_training_recipe.py tests\test_training_recipe.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Pending implementation.

## 2026-05-13 - Training Smoke Dry Run

### Scope
- Add a lightweight dry-run report that consumes ready combined datasets before real training.
- Reuse the existing readiness report as the gate.
- Record input dataset paths, manifests, quality status, counts, and small sample previews.
- Keep generated smoke reports out of git.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/task notes for this move.

### Steps
- [x] Inspect readiness, collection, and dataset helper APIs.
- [x] Add a training smoke report module.
- [x] Add a CLI wrapper under `user-test`.
- [x] Add focused tests for ready and blocked readiness behavior.
- [x] Run the smoke report against current local generated datasets.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- `python -m py_compile training\training_smoke.py user-test\run_training_smoke.py tests\test_training_smoke.py`
- `python -m unittest tests.test_training_smoke -v`
- `python user-test\run_training_smoke.py --input runs\datasets\latest --input runs\benchmarks --output-dir runs\training-smoke`
- `git diff --check -- README.md training\training_smoke.py user-test\run_training_smoke.py tests\test_training_smoke.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Pending implementation.

## 2026-05-13 - Story Opening Preference Benchmark

### Scope
- Add a deterministic non-combat benchmark/data path to address the readiness recommendation.
- Keep the scenario lightweight and local: no external LLM calls, no combat loop, no generated dataset files committed.
- Generate story-mode preference pairs from the opening Waterdeep/Gundren scene.
- Preserve unrelated dirty campaign/runtime files.
- Commit and push only code/docs/tests/manifest/task notes for this move.

### Steps
- [x] Inspect the current training-batch scenario and preference-pair generation flow.
- [x] Add `lmop_story_opening_choices` scenario support.
- [x] Add a committed policy benchmark manifest for the story-opening benchmark.
- [x] Add focused tests for non-combat transition/preference generation.
- [x] Run focused verification and regenerate local benchmark/dataset/readiness artifacts.
- [x] Commit and push to `origin/newdndagents`.

### Verification
- `python -m py_compile user-test\run_training_batch.py user-test\run_policy_benchmark.py tests\test_training_batch.py`
- `python -m unittest tests.test_training_batch tests.test_policy_benchmark_manifests -v`
- `python user-test\run_policy_benchmark.py --manifest user-test\full-story-demo\scripts\policy-benchmark-story-opening.json`
- `python user-test\collect_training_datasets.py --input runs\benchmarks --output-dir runs\datasets\latest`
- `python user-test\report_training_readiness.py --input runs\datasets\latest --input runs\benchmarks --output-json runs\datasets\latest\training_readiness.json --output-md runs\datasets\latest\training_readiness.md`
- `git diff --check -- user-test\run_training_batch.py user-test\run_policy_benchmark.py user-test\full-story-demo\scripts\policy-benchmark-story-opening.json tests\test_training_batch.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Remaining readiness recommendation before this move: add more non-combat preference examples because combat covers 98.3% of preference records.
- Pending implementation.

## 2026-05-13 - Readiness Coverage Recommendations

### Scope
- Make the readiness report explain the remaining `needs_attention` state clearly.
- Surface dataset coverage/count breakdowns from quality reports.
- Generate recommendations from readiness and quality issue details.
- Preserve unrelated dirty campaign/runtime files and generated run artifacts.
- Commit and push only code/tests/task notes for this move.

### Steps
- [x] Inspect the current readiness report and quality report shapes.
- [x] Add quality count/issue summaries to readiness datasets.
- [x] Add top-level recommendations and Markdown coverage sections.
- [x] Add focused tests for runtime-mode imbalance recommendations.
- [x] Run focused verification and regenerate the readiness report.
- [x] Commit and push to `origin/newdndagents`.

### Verification Plan
- `python -m py_compile training\readiness_report.py tests\test_training_readiness.py`
- `python -m unittest tests.test_training_readiness tests.test_dataset_quality -v`
- `python user-test\report_training_readiness.py --input runs\datasets\latest --input runs\benchmarks --output-json runs\datasets\latest\training_readiness.json --output-md runs\datasets\latest\training_readiness.md`
- `git diff --check -- training\readiness_report.py tests\test_training_readiness.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Remaining live readiness status after ID namespacing is `needs_attention` because preference pairs are heavily combat-skewed.
- Readiness dataset summaries now include `quality_counts` and `quality_issues` from the sidecar quality reports.
- The JSON report now includes top-level `recommendations`; Markdown now renders `## Coverage` and `## Recommendations`.
- The regenerated real readiness report recommends: add more non-combat preference examples for `combined_preference_pairs.jsonl`; combat currently covers 98.3% of records.
- Verification passed:
  - `python -m py_compile training\readiness_report.py tests\test_training_readiness.py`
  - `python -m unittest tests.test_training_readiness tests.test_dataset_quality -v` passed 9 tests.
  - `python user-test\report_training_readiness.py --input runs\datasets\latest --input runs\benchmarks --output-json runs\datasets\latest\training_readiness.json --output-md runs\datasets\latest\training_readiness.md`

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

## 2026-05-21 - DeepSeek 100 Conversation RL Dataset

### Scope
- Generate a 100-conversation DeepSeek DM plus DeepSeek player dataset for RL training.
- Run each conversation until `demo-complete`, timeout, connector failure, or the configured action cap makes further processing impossible.
- Enforce a 50 positive / 50 negative label split by player prompt profile, with pilot-batch monitoring before the full run.
- Preserve raw request/response I/O, transcripts, server/connector logs, trajectories, rewards, manifests, and quality reports as repo-local artifacts.
- Keep orchestration isolated on the `newdndagents` branch worktree and do not disturb unrelated dirty files in the main checkout.
- While a dataset runner is active, do not commit or push, and do not contact GitHub; keep generated dataset artifacts on local disk.

### Steps
- [x] Add focused tests for dataset split planning, pilot control, manifest writing, and episode summarization.
- [x] Implement a resumable multi-worker DeepSeek conversation dataset runner.
- [x] Extend the party connector with explicit positive/negative behavior profiles and raw LLM interaction logging.
- [x] Add scene-goal completion rewards plus penalties for repeated wording and stalled same-scene turns.
- [x] Add quality gates for 100 conversations, 50/50 label counts, raw artifact existence, terminal reason coverage, reward summary, and transition/preference dataset validation.
- [x] Run dry-run/unit verification, then a small pilot batch against real DeepSeek if local runtime inputs are available.
- [x] Re-verify reward shaping after the explicit user reminder: goal/subgoal completion rewards, repetitive wording/action penalties, and same-scene stalling penalties when no goal or hidden subgoal finishes.
- [x] Restart the full 100-conversation local run only after reward verification passes, with no commit/push while it is active.
- [x] Stop and root-cause the local-rewardshape run after it revealed memory writes escaping the episode override.
- [x] Fix campaign-memory writes so an explicit campaign root is both the read root and write root.
- [x] Stop `full-100-20260521-memoryfix2-local-w2-timeout180` after pilot transcript inspection found quoted dialogue followed by third-person self narration.
- [x] Add a regression test proving mixed quoted dialogue plus third-person self narration is rejected and retried.
- [x] Tighten story-speech validation and prompt wording so player speech stays in the acting character's own words.
- [x] Add a trajectory-fixture guard so verification tests cannot dirty shared `campaigns/lmop/dm/**` memory files.
- [x] Add a short trajectory episode id for dataset-launched web servers to avoid Windows path-length failures.
- [x] Restart the full local-only 100-conversation run after focused tests pass and record the fresh run id.
- [x] Stop `f100-gdf-w2` after transcript inspection found rejected natural-language declarations leaking into public chat.
- [x] Add a regression test proving invalid story declarations do not append public `StoryActionDeclaredEvent` entries.
- [x] Fix story action commit ordering so validation/clarification failures leave the authoritative event log unchanged.
- [x] Re-run focused tests and restart the full local-only 100-conversation run only after the regression passes.
- [x] Stop `f100-eventfix-w2` after transcript inspection found short-name third-person self narration (`Iri flicks...`) missed by the validator.
- [x] Add a regression test for quoted dialogue followed by short persona-name action narration.
- [x] Extend the self-narration action verb validator and rerun the focused suite.
- [x] Stop `f100-actionverb-w2` after transcript inspection found third-person scouting narration with an embedded `/check Perception` accepted as public player chat before fallback.
- [x] Add a regression test for third-person self narration plus an embedded slash command inside a natural-language story action.
- [x] Reject embedded slash commands in natural story declarations and rerun the focused suite.
- [ ] Run or start the full 100-conversation generation and record the resulting artifact paths, counts, reward metrics, and quality status.

### Verification Plan
- `python -m py_compile dm_agent\client.py training\preferences.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_llm_client.py tests\test_deepseek_100_dataset_runner.py tests\test_preferences.py`
- `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_preferences tests.test_rewards tests.test_trajectory -v`
- `python user-test\run_deepseek_100_conversation_dataset.py --dry-run --episodes 4 --positive-count 2 --pilot-size 2 --workers 2 --run-id dry-run-verify --output-root runs\deepseek-100-conversation-dataset`
- `python user-test\run_deepseek_100_conversation_dataset.py --episodes 2 --positive-count 1 --pilot-size 2 --workers 2 --env-path D:\DND-newagent\.env --base-url file:///D:/5etools-mirror-2.github.io/ --max-actions 6 --connector-timeout-seconds 2400 --server-start-timeout-seconds 120 --pre-connector-delay-seconds 0.5 --output-root runs\deepseek-100-conversation-dataset --run-id live-smoke-2c`

### Review
- Added reward components for `scene_goal_completed`, `hidden_subgoal_completed`, `party_goal_resolved`, `open_loop_resolved`, `discovery_made`, and `social_topic_revealed`.
- Added penalties for `repetitive_words`, `repetitive_action`, and `stalled_scene_turn`.
- Exposed scene-goal, hidden-subgoal, discovery, social-topic, and recent player input counters in trajectory state snapshots.
- Added DeepSeek player behavior profiles: positive players are prompted to finish scene goals and hidden subgoals; negative players are prompted to generate legal, processable stalling/repetition examples.
- Added raw DeepSeek request/response JSONL logging without Authorization headers.
- Increased DeepSeek JSON completion budgets and made HTTP read timeouts configurable/long enough for reasoning-heavy DeepSeek calls.
- Added scene-level combined preference pair generation so short cross-conversation runs can still produce preference data when exact transcript contexts differ.
- Tightened quality gates so missing raw artifacts, missing trajectory/transcript data, failed unprocessed episodes, and failed combined transition/preference quality reports fail the run.
- Live smoke `runs\deepseek-100-conversation-dataset\live-smoke-2c` completed 2/2 conversations with a 1/1 positive-negative split, 12 combined transitions, 1 combined preference pair, and quality status `pass`.
- Live smoke reward totals: progress `0.99`, penalty `-0.82`, validity `0.12`, average total reward `0.145`.
- Pilot control increased negative intensity from `0.5` to `0.7` because the negative pilot reward was not lower than the positive pilot reward.
- First full 100-conversation generation attempt was launched, then intentionally stopped after monitoring found shared campaign-state writes:
  - Run ID: `full-100-20260521`
  - Runner PID: `26004`
  - Run directory: `runs\deepseek-100-conversation-dataset\full-100-20260521`
  - Command record: `runs\deepseek-100-conversation-dataset\full-100-20260521\launcher-command.txt`
  - Process record: `runs\deepseek-100-conversation-dataset\full-100-20260521\runner-process.json`
  - Early monitor result at `2026-05-20T22:45:28-07:00`: runner active, 4 pilot episode dirs active, raw records increasing, transcript lines increasing, 0 connector stderr bytes, and 0 completed episode results so far.
- Root cause: each episode server used the shared worktree campaign root by default, so parallel DeepSeek conversations wrote generated DM memory into the same `campaigns/lmop/dm/**` files.
- Fix: the dataset runner now copies the LMOP campaign root into each episode directory and passes that isolated copy to `web_story_demo_server.py --campaign-root`.
- Second full-run attempt `full-100-20260521-isolated` was stopped because the first isolation fix copied the parent `campaigns` directory instead of the actual LMOP root, causing `maps/high-road-region-hex.json` lookup failures.
- Current full-run attempt:
  - Run ID: `full-100-20260521-isolated-2`
  - Runner PID: `1304`
  - Run directory: `runs\deepseek-100-conversation-dataset\full-100-20260521-isolated-2`
  - Early monitor result at `2026-05-20T23:11:39-07:00`: runner active, 4 pilot episode dirs active, all episode-local campaign copies include `maps/high-road-region-hex.json` and DM memory files, worktree `git status` clean, 0 connector/server stderr bytes, and the first DeepSeek calls still pending with 0 raw interaction records.
- Provider finding: the 4-worker run later returned DeepSeek provider payloads saying the request could not start processing within the 900-second timeout. It was stopped to avoid low-quality failed episodes.
- Mitigation: added `--llm-timeout-seconds` to the party connector and dataset runner so player-agent DeepSeek requests can be bounded independently from local automation requests.
- Live provider probe `live-provider-probe-1w-timeout180` completed 1/1 positive conversation with `--workers 1`, `--max-actions 1`, and `--llm-timeout-seconds 180`; it wrote 5 raw DeepSeek rows, 1 transition, and 0 stderr. Its top-level quality status was `fail` only because a single short conversation cannot produce combined preference pairs.
- Current active full-run attempt:
  - Run ID: `full-100-20260521-w2-timeout180`
  - Runner PID: `47292`
  - Run directory: `runs\deepseek-100-conversation-dataset\full-100-20260521-w2-timeout180`
  - Command record: `runs\deepseek-100-conversation-dataset\full-100-20260521-w2-timeout180\launcher-command.txt`
  - Early monitor result at `2026-05-20T23:47:37-07:00`: runner active, 2 pilot episode dirs active, `conversation-001-positive` had 18 raw rows, `conversation-002-negative` had 17 raw rows, worktree `git status` clean, and 0 connector/server stderr bytes.
- User reminder: keep full-run artifacts local and avoid commits/GitHub while the dataset runner is active.
- The `full-100-20260521-w2-timeout180` runner was stopped before restarting because the user explicitly asked to ensure reward shaping and avoid branch/GitHub activity while running.
- Fresh local full-run attempt:
  - Run ID: `full-100-20260521-local-rewardshape-w2-timeout180`
  - Runner PID: `60120`
  - Run directory: `runs\deepseek-100-conversation-dataset\full-100-20260521-local-rewardshape-w2-timeout180`
  - Command record: `runs\deepseek-100-conversation-dataset\full-100-20260521-local-rewardshape-w2-timeout180\launcher-command.txt`
  - Process record: `runs\deepseek-100-conversation-dataset\full-100-20260521-local-rewardshape-w2-timeout180\runner-process.json`
  - Launch policy: local disk artifacts only; no commit/push/GitHub operations while this runner is active.
  - Status: stopped after the initial health check found shared campaign markdown dirtied by memory-sync behavior.
- Root cause: `StorytellingSession` read from the episode `--campaign-root`, but `DmMemoryWriter(campaign_path.parent, campaign_id='lmop')` wrote to `campaign_path.parent\lmop`, which is incorrect for override roots not literally named `lmop`.
- Fix: `DmMemoryWriter` now accepts an explicit `campaign_root`; LMOP bootstrap passes the resolved campaign path so memory writes stay inside the same root used for retrieval and maps.
- Current active local full-run attempt:
  - Run ID: `full-100-20260521-memoryfix2-local-w2-timeout180`
  - Runner PID: `58808`
  - Run directory: `runs\deepseek-100-conversation-dataset\full-100-20260521-memoryfix2-local-w2-timeout180`
  - Initial health check: 2 pilot episode dirs active, no final report, 0 connector/server stderr bytes, no shared `campaigns/lmop/dm/**` git changes.
  - Monitor at `2026-05-21T00:12:47-07:00`: runner active, no final report, no pilot decision yet, 2 pilot episode dirs active, `conversation-001-positive` had 13 raw rows and 4 connector output lines, `conversation-002-negative` had 16 raw rows and 6 connector output lines, 0 connector/server stderr bytes, and no shared `campaigns/lmop/dm/**` git changes.
  - Monitor at `2026-05-21T00:24:42-07:00`: runner active, no final report, no pilot decision yet, 2 pilot episode dirs active, no completed episode results, `conversation-001-positive` had 26 raw rows, 9 connector output lines, and 5 trajectory turn records; `conversation-002-negative` had 25 raw rows, 9 connector output lines, and 5 trajectory turn records; 0 connector/server stderr bytes; no shared `campaigns/lmop/dm/**` git changes.
  - Launch policy: local disk artifacts only; no commit/push/GitHub operations while this runner is active.
- The `full-100-20260521-memoryfix2-local-w2-timeout180` runner was stopped after transcript inspection found a player action that mixed quoted direct dialogue with third-person self narration.
- Fix: story-speech validation now rejects direct-dialogue turns that append the acting persona in third person, and the prompt explicitly forbids third-person self narration after quoted dialogue.
- Verification fixture finding: `tests.test_trajectory` itself wrote shared campaign DM memory when it built full story sessions without a campaign-root override; the tests now use temp LMOP campaign copies and guard against shared DM file mutation.
- The `full-100-20260521-guarded-dialoguefix-local-w2-timeout180` runner was stopped after early results failed before LLM calls due Windows path-length failures in nested trajectory paths.
- Fix: dataset-launched web servers now pass `--trajectory-episode-id web`, keeping trajectory paths short and deterministic under each episode directory.
- Current active local full-run attempt:
  - Run ID: `f100-gdf-w2`
  - Runner PID: `41152`
  - Run directory: `runs\deepseek-100-conversation-dataset\f100-gdf-w2`
  - Initial health check: 2 pilot episode dirs active, both web servers and connectors running, trajectory records present, 0 connector/server stderr bytes, and shared `campaigns/lmop/dm/**` clean.
  - Monitor at `2026-05-21T00:41:15-07:00`: runner active, no final report, no pilot decision yet, `conversation-001-positive` had 2 raw DeepSeek rows and `conversation-002-negative` had 1 raw DeepSeek row; both had 0 stderr bytes and shared campaign DM files remained clean.
  - Monitor at `2026-05-21T00:46:30-07:00`: runner active, no completed results yet, `conversation-001-positive` had 11 raw rows, 18 transcript lines, 5 trajectory records, and clean direct-dialogue player actions; `conversation-002-negative` had 10 raw rows, 8 transcript lines, and 3 trajectory records; both had 0 stderr bytes and shared campaign DM files remained clean.
  - Monitor at `2026-05-21T01:03:00-07:00`: runner active, no completed results yet, `conversation-001-positive` had 24 raw rows, 23 transcript lines, 7 trajectory records, and 0 stderr bytes; `conversation-002-negative` had 25 raw rows, 22 transcript lines, 7 trajectory records, and 0 stderr bytes; shared campaign DM files remained clean.
  - Launch policy: local disk artifacts only; no commit/push/GitHub operations while this runner is active.
- `f100-gdf-w2` was intentionally stopped before pilot expansion:
  - Stop reason: `conversation-002-negative` showed an invalid player declaration in the public chat transcript even though the connector retried and accepted a later corrected action.
  - Root cause: `StorytellingSession.submit_story_action()` appended `StoryActionDeclaredEvent` before exploration declaration validation, so rejected declarations could remain in the authoritative event log.
  - Runner PID `41152` and its children were stopped successfully with no remaining child processes.
- Fix: invalid story declarations now validate exploration interpretation and hostile-clarification decisions before appending public `StoryActionDeclaredEvent` entries. Accepted exploration-prompt declarations still append the public action before opening the pending check.
- Fixture guard: `tests.test_storytelling_session` now uses a temp LMOP campaign root and fails if it writes shared `campaigns/lmop/dm/**` files.
- Current active local full-run attempt:
  - Run ID: `f100-eventfix-w2`
  - Runner PID: `26792`
  - Run directory: `runs\deepseek-100-conversation-dataset\f100-eventfix-w2`
  - Command record: `runs\deepseek-100-conversation-dataset\f100-eventfix-w2\launcher-command.txt`
  - Process record: `runs\deepseek-100-conversation-dataset\f100-eventfix-w2\runner-process.json`
  - Launch policy: local disk artifacts only; no commit/push/GitHub operations while this runner is active.
  - Initial health check: runner active with 2 pilot episode dirs, both episodes have raw DeepSeek rows and trajectory rows, 0 connector/server stderr bytes, and shared `campaigns/lmop/dm/**` clean.
  - Monitor after first player actions: `conversation-001-positive` had 6 raw rows, 7 transcript lines, 3 trajectory records, and direct player dialogue; `conversation-002-negative` had 7 raw rows, 8 transcript lines, 3 trajectory records, and direct negative-profile stalling dialogue. Both had 0 stderr bytes and shared campaign DM files remained clean.
- `f100-eventfix-w2` was intentionally stopped before pilot expansion:
  - Stop reason: `conversation-001-positive` included `"Trust?..." Iri flicks her fingers...`, a mixed direct-dialogue plus third-person self-narration action.
  - Root cause: the existing connector validator recognized fixed self-narration verbs such as `produces`, but did not include short-name action verbs such as `flicks`, so the player-4 action passed validation.
  - Runner PID `26792` and its children were stopped successfully with no remaining child processes, and shared campaign DM files stayed clean.
- Fix: the connector validator now treats additional common short action verbs (`flicks`, `lifts`, `sets`, `slides`, `smiles`, `waves`, etc.) as third-person self narration when they follow quoted dialogue and a player persona name.
- Current active local full-run attempt:
  - Run ID: `f100-actionverb-w2`
  - Runner PID: `13384`
  - Run directory: `runs\deepseek-100-conversation-dataset\f100-actionverb-w2`
  - Command record: `runs\deepseek-100-conversation-dataset\f100-actionverb-w2\launcher-command.txt`
  - Process record: `runs\deepseek-100-conversation-dataset\f100-actionverb-w2\runner-process.json`
  - Launch policy: local disk artifacts only; no commit/push/GitHub operations while this runner is active.
  - Initial health check at `2026-05-21T02:02:54-07:00`: runner active with 2 pilot episode dirs, raw DeepSeek rows and trajectory rows present, 0 connector/server stderr bytes, and shared `campaigns/lmop/dm/**` clean.
  - First-action monitor at `2026-05-21T02:09:30-07:00`: both pilots had clean direct-dialogue first actions and 0 connector/server stderr bytes.
  - Monitor at `2026-05-21T02:25:25-07:00`: runner active, no completed results yet, no final report, no pilot decision yet. `conversation-001-positive` had 24 raw rows, 28 transcript lines, 8 trajectory records, and job-acceptance/wagon-prep progress. `conversation-002-negative` had 27 raw rows, 30 transcript lines, 8 trajectory records, repeated suspicion/failed checks, and 0 connector/server stderr bytes. Shared campaign DM files remained clean.
  - Reward check after the `02:25` monitor: `conversation-001-positive` had 6 turn records, total reward `0.11`, including `party_goal_resolved=0.25`, `repetitive_action=-0.22`, and `stalled_scene_turn=-0.30`; `conversation-002-negative` had 6 turn records, total reward `-0.15`, including `repetitive_action=-0.22` and `stalled_scene_turn=-0.36`. No errored raw action text appeared in either transcript.
- `f100-actionverb-w2` was intentionally stopped before pilot expansion:
  - Stop reason: `conversation-001-positive` accepted `From her spot ahead of the wagon, Seraphine keeps... /check Perception` as public player chat, then fell back to `/check`.
  - Root cause: the connector did not reject slash commands embedded inside natural-language story declarations, and the self-narration verb list did not include `keeps`, `murmurs`, or `whispers`.
  - Runner PID `13384` and its children were stopped successfully with no remaining child processes, and shared campaign DM files stayed clean.
- Fix: natural-language story declarations now reject embedded slash commands such as `/check`, and the self-narration detector catches persona-name action verbs including `keeps`, `murmurs`, and `whispers`.
- Current active local full-run attempt:
  - Run ID: `f100-embeddedcheck-w2`
  - Runner PID: `40616`
  - Run directory: `runs\deepseek-100-conversation-dataset\f100-embeddedcheck-w2`
  - Command record: `runs\deepseek-100-conversation-dataset\f100-embeddedcheck-w2\launcher-command.txt`
  - Process record: `runs\deepseek-100-conversation-dataset\f100-embeddedcheck-w2\runner-process.json`
  - Launch policy: local disk artifacts only; no commit/push/GitHub operations while this runner is active.
  - Initial health check at `2026-05-21T02:57:45-07:00`: runner active with 2 pilot episode dirs, both episodes have raw DeepSeek rows and trajectory rows, 0 connector/server stderr bytes, and shared `campaigns/lmop/dm/**` clean.
  - First-action monitor at `2026-05-21T03:02:02-07:00`: both pilots had clean direct-dialogue first actions, 0 connector/server stderr bytes, and shared campaign DM files remained clean.
  - Monitor at `2026-05-21T03:12:40-07:00`: runner active, no completed results yet, no final report, no pilot decision yet. `conversation-001-positive` had 18 raw rows, 24 transcript lines, 6 trajectory records, a failed persuasion check, and no suspicious player lines. `conversation-002-negative` had 21 raw rows, 17 transcript lines, 6 trajectory records, risk/payment bargaining with a failed check, and no suspicious player lines. Both had 0 connector/server stderr bytes and shared campaign DM files stayed clean.
  - Reward check after the `03:12` monitor: `conversation-001-positive` had 4 turn records, total reward `0.39`, including `party_goal_resolved=0.25` and `stalled_scene_turn=-0.18`; `conversation-002-negative` had 5 turn records, total reward `0.05`, including `stalled_scene_turn=-0.30` and one negative reward turn. No errored raw action text appeared in either transcript.
  - Current user constraint: while this runner is active, do not commit, push, fetch, inspect remote GitHub state, or use GitHub connector tools. Keep dataset artifacts on local disk or in process memory only.
- Verification:
  - compile command passed with no output.
  - focused unit suite passed 45 tests.
  - dry-run wrote a balanced 4-episode plan.
  - live-smoke-2c wrote transcripts, raw interaction logs, trajectories, transitions, preferences, and quality reports for both conversations.
  - isolation regression `test_server_command_uses_isolated_episode_campaign_copy` failed before the fix and passed after it.
  - `python -m py_compile user-test\run_deepseek_100_conversation_dataset.py tests\test_deepseek_100_dataset_runner.py` passed.
  - `python -m unittest tests.test_deepseek_100_dataset_runner -v` passed 7 tests.
  - `test_build_llm_transport_applies_timeout_before_raw_logging_wrapper` and `test_connector_command_passes_llm_timeout` failed before the timeout plumbing and passed after.
  - `python -m py_compile user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py` passed.
  - `python -m unittest tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner -v` passed 26 tests.
  - `python -m unittest tests.test_rewards -v` passed 8 tests, including scene/hidden subgoal rewards and repetitive/stalled penalties.
  - `python -m unittest tests.test_trajectory.TrajectoryRecorderTests.test_trajectory_snapshot_exposes_support_and_debuff_metrics tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_quality_report_checks_split_terminals_rewards_and_artifacts -v` passed 2 tests.
  - `test_campaign_root_override_keeps_memory_writes_inside_override` failed before the memory-writer fix and passed after it.
  - `python -m unittest tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 25 tests.
  - `python -m py_compile dm_agent\memory.py session_server\bootstrap.py user-test\run_deepseek_100_conversation_dataset.py tests\test_trajectory.py tests\test_deepseek_100_dataset_runner.py` passed after rerunning outside the parallel test import.
  - `test_party_connector_retries_quoted_dialogue_with_third_person_self_narration` failed before the validator fix and passed after it.
  - `test_full_story_demo_records_story_turn_jsonl` failed under the shared-DM guard before the trajectory fixture isolation fix and passed after it.
  - `test_server_command_uses_short_trajectory_episode_id` failed before the short trajectory id was passed and passed after it.
  - `python -m unittest tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 45 tests after the dialogue, fixture-isolation, and path-length fixes.
  - `python -m py_compile dm_agent\memory.py session_server\bootstrap.py user-test\web_story_demo_server.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_story_demo_party_connector.py tests\test_trajectory.py tests\test_deepseek_100_dataset_runner.py` passed.
  - `git status --short -- campaigns/lmop/dm` stayed clean after the relevant suite and after the current run's initial health checks.
  - `test_invalid_story_declaration_does_not_append_public_action_event` failed before the story-action commit ordering fix and passed after it.
  - `python -m unittest tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 61 tests.
  - `python -m py_compile session_server\storytelling_session.py tests\test_storytelling_session.py dm_agent\memory.py session_server\bootstrap.py user-test\web_story_demo_server.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_story_demo_party_connector.py tests\test_trajectory.py tests\test_deepseek_100_dataset_runner.py` passed.
  - `git status --short -- campaigns/lmop/dm` stayed clean after the isolated storytelling-session suite and the 61-test focused suite.
  - `test_party_connector_retries_quoted_dialogue_with_short_name_action_verb` failed before the short-name action-verb fix and passed after it.
  - `python -m unittest tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 62 tests.
  - The focused py_compile command passed again after the short-name action-verb fix.
  - `test_party_connector_retries_third_person_scouting_with_embedded_check` failed before the embedded slash/self-narration fix and passed after it.
  - `python -m unittest tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 63 tests.
  - The focused py_compile command passed again after the embedded slash/self-narration fix.
  - remote `elijah/newdndagents` contains the isolation fixes through commit `65a2993`.
  - remote `elijah/newdndagents` contains the timeout-control fix through commit `a7647de`.
- Remaining gap: the full 100-conversation DeepSeek dataset is in progress, not complete. The final `conversations.jsonl`, combined datasets, and quality report must be inspected after the background run finishes before this goal can be marked complete.

## 2026-05-21 - DeepSeek Dataset Check-Reward Fix And Fresh Local Relaunch

### Scope
- Keep the 100-conversation DeepSeek dataset run local-only, with no commit/push/fetch/GitHub work while running.
- Stop the active run before pilot expansion if monitoring finds reward or transcript quality issues.
- Fix reward shaping so required `/check` prompt responses are not mislabeled as repetitive/stalling player declarations.
- Relaunch a fresh 100-conversation run with the same 50/50 split, 10-episode pilot, 2 workers, raw DeepSeek logs, transcripts, and isolated episode campaign roots.

### Steps
- [x] Monitor `f100-embeddedcheck-w2` and inspect raw rows, transcripts, trajectory rewards, stderr, and shared campaign dirtiness.
- [x] Stop `f100-embeddedcheck-w2` before pilot expansion after the reward scan found required `/check` prompt responses getting `repetitive_action` and `stalled_scene_turn` penalties.
- [x] Add a failing regression for required story-check responses in `tests/test_rewards.py`.
- [x] Fix `training/rewards.py` so exact `/check` story-check responses keep progress rewards but skip repetition and stalled-scene penalties.
- [x] Verify the fix with focused and broader suites.
- [x] Relaunch a fresh local run as `f100-checkrewardfix-w2`.
- [x] Run initial health checks for `f100-checkrewardfix-w2`.
- [ ] Continue pilot monitoring through first completed episodes and inspect the pilot control decision.
- [ ] Audit the final 100-conversation artifacts after completion: `conversations.jsonl`, combined transitions/preferences, quality report, reward split, and raw transcript retention.

### Verification
- [x] `python -m unittest tests.test_rewards.RewardSignalTests.test_required_story_check_response_is_not_repetition_or_stalling -v` failed before the reward fix with `repetitive_action` and `stalled_scene_turn` present.
- [x] The same regression passed after the fix.
- [x] `python -m py_compile training\rewards.py tests\test_rewards.py`
- [x] `python -m unittest tests.test_rewards -v` passed 9 tests.
- [x] `python -m unittest tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 64 tests.
- [x] Focused compile for the dataset/story/reward touched modules passed.
- [x] Recomputed old `f100-embeddedcheck-w2` pilot rewards in memory only: positive sample changed from `-0.02` to `0.60` by removing `/check`-specific penalties while preserving real story-declaration stalled penalties.
- [x] Fresh run `f100-checkrewardfix-w2` launched locally as PID `60640`; initial health checks show runner active, 2 pilot episodes, zero runner/episode stderr bytes, and clean shared `campaigns/lmop/dm/**`.

### Review
- Current active local run: `runs\deepseek-100-conversation-dataset\f100-checkrewardfix-w2`, PID `60640`.
- Launch policy: local disk artifacts only; no commit, push, fetch, remote inspection, or GitHub connector use while active.
- Latest monitor at `2026-05-21T03:33:45-07:00`: `conversation-001-positive` had 12 raw rows, 18 transcript lines, 3 turn rows, reward total `0.12`; `conversation-002-negative` had 14 raw rows, 14 transcript lines, 3 turn rows, reward total `0.07`; both had zero stderr bytes.
- Monitor at `2026-05-21T03:47:57-07:00`: runner active, 2 pilot episode dirs, no completed results, no pilot control file, 0 runner/episode stderr bytes. `conversation-001-positive` had 30 raw rows, 28 transcript lines, 6 turn rows, reward total `0.19`; `conversation-002-negative` had 29 raw rows, 27 transcript lines, 6 turn rows, reward total `0.59` due one `open_loop_resolved=0.4`.
- Monitor at `2026-05-21T03:52:54-07:00`: runner active, 0 stderr, no shared campaign DM dirtiness, both pilots at 7 turn rows. Positive sample had begun concrete wagon preparation and departure-time planning; negative sample was still legal/processable but over-cautious and repetitive about road hazards and magic.
- Monitor at `2026-05-21T03:58:12-07:00`: positive pilot advanced to `scene-00-high-road-journey`; negative pilot remained in the briefing but had resolved a party goal/open loop. Both still had 0 stderr and 0 trajectory errors.
- Monitor at `2026-05-21T04:08:15-07:00`: positive pilot had 12 turn rows and reward total `1.51`, including `scene_goal_completed=0.7`, `hidden_subgoal_completed=0.35`, and `discovery_made=0.12`; negative pilot had 9 turn rows and reward total `0.96`, still lower than positive after positive scene progress. Both remained active with no episode results yet.
- Live reward check: a fresh `/check` turn now records only `valid_action`, `state_progress`, and `story_progress`, with no `repetitive_action` or `stalled_scene_turn`.
- Remaining gap: this run was stopped before completion because `conversation-001-positive` duplicated player quoted speech as a public story transcript entry. The requested full 100-conversation dataset is still unverified; do not mark the goal complete until final artifacts prove all requirements.

## 2026-05-21 - DeepSeek Dataset Quoted-Speech Echo Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion after finding duplicated player speech in public story transcript entries.
- Fix the story-turn echo filter so DM transcript entries that repeat only the quoted speech subset of a longer player declaration are dropped.
- Verify the fix with a red/green regression, focused story/reward/dataset tests, compile checks, and a fresh local relaunch.

### Steps
- [x] Stop `f100-checkrewardfix-w2` and confirm no runner or child processes remain.
- [x] Add a failing regression for quoted direct-dialogue subsets echoed as public story transcript entries.
- [x] Fix the transcript echo filter at the story-turn boundary.
- [x] Run focused and broader verification.
- [x] Relaunch a fresh local 100-conversation run with the same split and worker settings.
- [x] Monitor the new pilot for transcript echoes, stderr, rewards, and shared campaign dirtiness.
- [x] Add a failing regression for DM-authored public transcript entries that use a `Player N` speaker.
- [x] Fix story-turn transcript filtering so player-speaker transcript entries from DM decisions are dropped even when paraphrased.
- [x] Verify again and relaunch a fresh local run.
- [x] Add a failing regression for transient incomplete HTTP reads from the DeepSeek transport.
- [x] Retry transient HTTP read failures in `LLMHttpTransport.post()` without hiding HTTP status errors.
- [x] Verify transport and focused suites after the retry fix.
- [x] Relaunch a fresh local run after the HTTP retry fix.

### Verification
- [x] Regression fails before the fix and passes after it.
- [x] Focused compile and unit suites pass.
- [x] Fresh run health check shows local artifacts, raw logs, 0 stderr, and clean shared `campaigns/lmop/dm/**`.

### Review
- Root-cause evidence: `conversation-001-positive` in `f100-checkrewardfix-w2` appended `[chat:public:story] Player 4: Stand back...` after the same quoted speech already appeared in `[chat:public:player]`.
- Current status: runner PID `60640` and its children were stopped at `2026-05-21T04:20:05-07:00`; the full dataset is not complete.
- Verification so far: the new regression failed before the filter change and passed after it; the two echo-filter tests passed; `python -m unittest tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 65 tests; focused compile passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-quotedechofix-w2` launched locally as PID `28000` at `2026-05-21T04:23:10-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Monitor through roughly 12 pilot turns: runner active, 2 episode dirs, no result files yet, no pilot-control file, 0 runner/web/connector stderr bytes, no shared campaign DM dirtiness, no public story entries with `Player` speakers, and no suspicious sampled player action lines. Positive reached `scene-00-high-road-journey`; negative remained more cautious in the Waterdeep briefing. Some DeepSeek speaker-vote calls ended with `finish_reason=length`, but the connector continued without trajectory errors.
- Stop reason for `f100-quotedechofix-w2`: at roughly 17 positive turns, `conversation-001-positive` appended `[chat:public:story] Player 4: Stay back...` after the public player action line. This was a DM-authored player-speaker paraphrase rather than an exact/subset echo, so the first echo filter fix was too narrow. Runner PID `28000` and its children were stopped at `2026-05-21T05:40:14-07:00`.
- Second fix: story-turn decision application now drops public transcript entries whose `speaker` matches a player actor id or player actor name, while keeping the existing exact/subset echo filter for NPC echoes. The new regression failed before the fix and passed after it.
- Verification after second fix: focused compile passed; the three echo-filter tests passed; `python -m unittest tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 66 tests; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Stop reason for `f100-playerspeakerfix-w2`: `conversation-001-positive` failed when the DeepSeek HTTP response closed mid chunk, causing `http.client.IncompleteRead` inside `LLMHttpTransport.post()` and connector exit code 1. The runner recorded `episode_result.json` with `status: failed`; PID `27304` and its children were stopped at `2026-05-21T05:56:17-07:00`.
- Transport retry fix: `test_post_retries_incomplete_chunked_response_read` failed before the fix with `http.client.IncompleteRead` and passed after `LLMHttpTransport.post()` added bounded retry on incomplete response reads.
- Verification after transport retry fix: focused transport tests passed; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 69 tests; focused compile passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-httpretry-w2` launched locally as PID `57484` at `2026-05-21T06:00:42-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Initial health check for `f100-httpretry-w2`: runner active, 2 pilot episode dirs, 0 result files, no pilot-control file, 0 runner/web/connector stderr bytes, no public story entries with `Player` speakers, no suspicious player action lines, and shared `campaigns/lmop/dm/**` stayed clean.
- Stop reason for `f100-httpretry-w2`: first-turn monitoring showed the speaker-vote implementation was collecting four independent DeepSeek votes sequentially before each player action, making the 100-conversation job impractically slow. Runner PID `57484` and 5 children were stopped at `2026-05-21T06:13:02-07:00`.

## 2026-05-21 - DeepSeek Dataset Parallel Speaker Votes

### Scope
- Keep the same player-voting behavior and deterministic vote tally semantics.
- Reduce per-turn latency by collecting independent speaker votes concurrently inside the connector.
- Keep all artifacts local-only and do not commit/push/fetch/GitHub while dataset runs are active.

### Steps
- [x] Add a failing regression proving all speaker-vote LLM requests are issued before waiting on slow vote responses.
- [x] Parallelize speaker-vote collection without changing action submission, validation retries, or vote tie-break behavior.
- [x] Verify focused connector tests, broader dataset/reward/story tests, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local run after the parallel-vote fix.
- [ ] Continue pilot monitoring through first completed episodes and inspect the pilot control decision.

### Verification
- [x] Regression fails before the parallel-vote fix and passes after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Design: preserve the existing four-voter model, but use bounded thread parallelism to collect independent votes concurrently, then tally exactly as before.
- Regression evidence: `test_party_connector_collects_speaker_votes_concurrently` failed before the fix with `AssertionError: speaker votes were collected sequentially instead of concurrently` and passed after the fix.
- Implementation: `_vote_for_story_controller()` now submits one vote task per candidate with `ThreadPoolExecutor`, collects results, and runs the existing deterministic tally/tie-break logic; retry-count increments are guarded with a small lock.
- Verification after parallel-vote fix: adjacent vote tests passed; `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py` passed; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 70 tests; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-parallelvote-w2` launched locally as PID `34480` at `2026-05-21T06:16:43-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Initial health check for `f100-parallelvote-w2`: runner active, 2 pilot episode dirs, 0 result files, no pilot-control file, 0 runner/web/connector stderr bytes, no public story entries with `Player` speakers, no suspicious player action lines, and shared `campaigns/lmop/dm/**` stayed clean.
- First-turn monitor: both pilots committed direct in-character dialogue, with no `I ask`/`I tell` phrasing and no public story entries with `Player` speakers. The positive pilot recovered from one DeepSeek `finish_reason=length` speaker vote through the existing retry path.
- Mid-pilot monitor: `conversation-002-negative` produced one intended invalid-action trajectory row with `invalid_action=-1.0`, no connector crash, and no public transcript append for the rejected action.
- Latest monitor: runner active, 0 result files, no pilot-control file, 0 runner/web/connector stderr bytes. `conversation-001-positive` had 41 raw rows, 38 transcript lines, 9 turn rows, reward total `0.20`, 0 invalid/system-error rows; `conversation-002-negative` had 37 raw rows, 33 transcript lines, 8 turn rows, reward total `0.18`, 1 invalid-action row, 0 system-error rows. Both had 0 public story player-speaker echoes, 0 suspicious action lines, remained in `scene-waterdeep-gundren-briefing`, and shared `campaigns/lmop/dm/**` stayed clean.
- Stop reason for `f100-parallelvote-w2`: `conversation-001-positive` accepted `Iri rolls her eyes... She pulls out... She casts Detect Magic...` as public player chat. Root cause: the third-person self-narration detector was verb-list based and did not include `rolls`, so a persona-name action sentence could bypass the validator. Runner PID `34480` and 5 children were stopped at `2026-05-21T06:39:59-07:00`.

## 2026-05-21 - DeepSeek Dataset Leading Third-Person Action Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Reject player story actions that begin with the acting persona's name plus third-person action narration, including the live `Iri rolls...` pattern.
- Verify with a red/green regression, focused connector tests, broader suite, compile checks, and a fresh local relaunch.

### Steps
- [x] Add a failing regression for leading persona-name third-person narration in player story actions.
- [x] Fix the validator so the live `Iri rolls...` pattern retries into first-person/direct player wording.
- [x] Verify focused connector tests, broader dataset/reward/story tests, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local run after the validator fix.
- [ ] Continue pilot monitoring through first completed episodes and inspect the pilot control decision.

### Verification
- [x] Regression fails before the fix and passes after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Regression evidence: `test_party_connector_retries_leading_third_person_persona_action` failed before the fix with `invalid_action_retries` equal to 0 and passed after the fix.
- Implementation: `_SELF_NARRATION_VERBS_RE` now includes `rolls?`, so `Iri rolls...` is rejected at the same validator boundary as other persona-name third-person action narration.
- Verification after fix: the targeted validator tests passed; `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py` passed; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 71 tests; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-leadingthirdfix-w2` launched locally as PID `58180` at `2026-05-21T06:43:23-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Initial health check for `f100-leadingthirdfix-w2`: runner active, 2 pilot episode dirs, 0 result files, no pilot-control file, 0 runner/web/connector stderr bytes, no public story entries with `Player` speakers, no suspicious player action lines, and shared `campaigns/lmop/dm/**` stayed clean.
- Monitor after first few turns: runner active, 0 result files, no pilot-control file, 0 runner/web/connector stderr bytes. `conversation-001-positive` had 20 raw rows, 29 transcript lines, 5 turn rows, reward total `0.53`, 0 invalid/system-error rows; `conversation-002-negative` had 19 raw rows, 27 transcript lines, 5 turn rows, reward total `0.63`, 0 invalid/system-error rows. Both had 0 public story player-speaker echoes, 0 suspicious player action lines, remained in `scene-waterdeep-gundren-briefing`, and shared `campaigns/lmop/dm/**` stayed clean.
- Quality note: sampled player actions were direct in-character speech and `/check` responses. Negative reward was slightly higher at this early point due an `open_loop_resolved=0.4` cargo question; leave pilot control to adjust once completed pilot episodes exist unless transcript/system quality regresses first.

## 2026-05-21 - DeepSeek Dataset Attack-Pattern Hostility Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Fix the false hostile-escalation classification where an information request about goblin "attack patterns" is treated as an attack declaration.
- Verify with a red/green regression before relaunching the 100-conversation DeepSeek dataset run.

### Steps
- [x] Stop `f100-leadingthirdfix-w2` before pilot expansion after monitoring found a valid information request recorded as an invalid hostile action.
- [x] Trace the classifier path to `rules_engine/hostile_escalation.py` and identify the broad `attack` regex as the root cause.
- [x] Add a failing regression for information requests about "attack patterns" remaining in story mode.
- [x] Fix hostile-declaration detection without weakening real attack/stab/grapple/block escalation.
- [x] Add a failing fixture regression proving hostile-escalation tests use an isolated campaign root.
- [x] Fix the hostile-escalation test fixture so DM memory writes stay inside the test temp copy.
- [x] Verify focused hostile-escalation tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Continue pilot monitoring through first completed episodes and inspect the pilot control decision.

### Verification
- [x] Targeted regression fails before the fix for the expected `CLARIFICATION_REQUIRED` outcome.
- [x] Targeted regression passes after the fix.
- [x] Fixture isolation regression fails before the test-helper fix and passes after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-leadingthirdfix-w2`: the player asked Gundren about goblin "numbers or attack patterns" and the trajectory recorded `invalid_action=-1.0` with clarification text `Who are you trying to attack or physically force into the fight?`.
- Regression evidence: `test_information_request_about_attack_patterns_remains_story_mode` failed before the fix with `CLARIFICATION_REQUIRED` and now passes; `test_direct_attack_declaration_still_escalates` confirms `I attack Gundren Rockseeker.` still escalates.
- Fixture isolation evidence: `test_test_fixture_uses_isolated_campaign_root` failed before passing a temp campaign root and now passes; `test_verbal_threat_alone_can_remain_in_story_mode` no longer dirties `campaigns/lmop/dm/**`.
- Verification after fix: `python -m unittest tests.test_hostile_escalation -v` passed 12 tests; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation -v` passed 83 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-attackpatternfix-w2` launched locally as PID `27112` at `2026-05-21T07:13:28-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-attackpatternfix-w2`: `conversation-001-positive` accepted quoted direct speech followed by third-person pronoun narration (`She turns to Gundren...`). Runner PID `27112` and five children were stopped at `2026-05-21T07:24:45-07:00`.
- Current status: the full 100-conversation dataset is still incomplete; do not mark the goal complete until final local artifacts pass quality review.

## 2026-05-21 - DeepSeek Dataset Pronoun Narration Validator Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Reject story-mode player speech that mixes quoted dialogue with third-person pronoun self narration such as `She turns...`.
- Verify with a red/green regression, focused connector tests, broader suite, compile checks, diff checks, and clean shared campaign DM files.

### Steps
- [x] Stop `f100-attackpatternfix-w2` before pilot expansion after detecting third-person pronoun narration in a player action.
- [x] Add a failing regression for quoted dialogue followed by `She turns...` narration.
- [x] Fix the direct-story-speech validator and retry prompt guidance.
- [x] Verify focused connector tests, broader dataset/story/reward/hostile suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Continue pilot monitoring through first completed episodes and inspect the pilot control decision.

### Verification
- [x] Targeted regression fails before the validator fix.
- [x] Targeted regression passes after the validator fix.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence: `_third_person_self_narration_match()` strips quoted dialogue and checks persona names, but not pronoun subjects, so `"Before..." She turns ... "I know..."` passed validation.
- Regression evidence: `test_party_connector_retries_quoted_dialogue_with_pronoun_self_narration` failed before the fix with `invalid_action_retries` equal to 0 and passes after adding a sentence-boundary pronoun self-narration check.
- Verification after fix: adjacent direct-speech validator tests passed; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation -v` passed 84 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-pronounfix-w2` launched locally as PID `50080` at `2026-05-21T07:28:11-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-pronounfix-w2`: by 11 positive turns and 11 negative turns, both pilots were still in `scene-waterdeep-gundren-briefing`; positive had no scene-goal or hidden-subgoal completion and reward total `0.30`, while negative had a higher reward total `0.61`. Runner PID `50080` and five children were stopped at `2026-05-21T07:54:59-07:00`.

## 2026-05-21 - DeepSeek Dataset Positive Scene-Closure Pressure

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Add explicit stale-scene pressure to positive player-agent context and instructions so the party closes the briefing and moves to the road instead of accumulating low-value questions.
- Preserve negative-profile ability to produce legal lower-quality stalling examples, while still allowing the run to progress later.

### Steps
- [x] Stop `f100-pronounfix-w2` before pilot expansion after monitoring showed positive progression was worse than negative and neither sample left the briefing.
- [x] Add a failing regression proving the connector sends stale-scene pressure to the player agent after repeated same-scene story turns.
- [x] Fix player-agent context and positive-profile prompt guidance to close stale scenes.
- [x] Verify focused connector tests, broader dataset/story/reward/hostile suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Continue pilot monitoring through first completed episodes and inspect the pilot control decision.

### Verification
- [x] Targeted stale-scene pressure regression fails before the prompt/context fix.
- [x] Targeted stale-scene pressure regression passes after the prompt/context fix.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence: positive-profile instructions say to finish goals, but the request context does not expose accumulated same-scene turn pressure or tell the model to stop asking preparatory questions after the scene has become stale.
- Regression evidence: `test_party_connector_sends_scene_closure_pressure_to_positive_player` failed before the fix with missing `current_scene_story_turn_count` and now passes with `scene_progress_pressure=close_scene_now`.
- Verification after fix: focused connector pressure tests passed; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation -v` passed 85 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-sceneclosure-w2` launched locally as PID `31464` at `2026-05-21T07:59:59-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Monitoring result: positive stale-scene pressure reached DeepSeek at `scene_progress_pressure=close_scene_now`; `conversation-001-positive` accepted the job, moved to `scene-00-high-road-journey`, and later found a hidden snare in narration. `conversation-002-negative` remained lower-reward and more repetitive in the briefing.
- Stop reason for `f100-sceneclosure-w2`: the hidden snare discovery stayed narrative-only in the trajectory snapshot: `hidden_subgoal_completion_count=0`, `trap_resolution_count=0`, and no hidden/scene goal reward fired after the Perception success. Runner PID `31464` and five children were stopped at `2026-05-21T08:37:00-07:00` before pilot expansion.
- Current status: the full 100-conversation dataset is still incomplete; next step is a deterministic trap/progress-state regression and fix so discovered/resolved hidden scene goals affect reward through canonical state, not text alone.

## 2026-05-21 - DeepSeek Dataset Hidden Trap Reward State Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Fix the gap where a narrated High Road snare discovery does not update canonical hidden subgoal/trap progress counts and therefore does not earn hidden/scene goal reward.
- Preserve the DM-vs-rules authority boundary: reward must come from typed/canonical state transitions, not from raw LLM narration matching.

### Steps
- [x] Trace the High Road trap discovery path from player declaration/check result into exploration state and trajectory snapshot fields.
- [x] Add a failing regression that reproduces the live successful snare discovery without changing canonical trap state.
- [x] Implement the smallest deterministic state update at the proper authority boundary.
- [x] Verify focused exploration/storytelling/trajectory/reward tests and broader dataset suites.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted trap-progress regression fails before the fix and passes after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence: the live positive pilot received a generic DM-issued Perception story check, not an exploration pending check, so the check-resolution path let the DM narrate a snare without applying `TrapDetectedEvent` or detect-procedure progress to canonical exploration state.
- Regression evidence: `test_story_perception_check_can_detect_active_hidden_trap` failed before the fix with `TrapStatus.HIDDEN` and passes after the fix.
- Reward-boundary evidence: `test_story_check_trap_detection_records_hidden_subgoal_reward` verifies the resulting `/check` turn increases `hidden_subgoal_completion_count` and records positive `hidden_subgoal_completed` plus `discovery_made` reward components.
- Fixture isolation fix: `tests/test_exploration_procedures.py` now runs against a temp copied `campaign_root`, after parallel verification showed it could dirty shared `campaigns/lmop/dm/**` while trajectory tests were asserting memory isolation.
- Verification after fix: `python -m unittest tests.test_exploration_procedures tests.test_trajectory tests.test_rewards -v` passed 30 tests; `python -m unittest tests.test_llm_client tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures -v` passed 97 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean after restoring test-run memory writes.
- Fresh run: `f100-traprewardfix-w2` launched locally as PID `59264` at `2026-05-21T08:44:37-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm the first positive High Road trap discovery now records hidden-subgoal/discovery reward instead of narrative-only progress, then continue to first completed pilot episodes and inspect the pilot control decision.
- Stop reason for `f100-traprewardfix-w2`: the positive close-pressure action `"Gundren, we accept..."` was interpreted as a social influence attempt because `_match_social_declaration()` treats `accept`/`agree` as influence keywords when an NPC name is present. That opened another Persuasion check and kept the positive pilot in the briefing at 10 turns with reward `0.28`, while the negative pilot was higher at `0.68`. Runner PID `59264` and five children were stopped at `2026-05-21T09:08:00-07:00`.

## 2026-05-21 - DeepSeek Dataset Acceptance Social-Matcher Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Prevent plain job acceptance such as `Gundren, we accept...` from being treated as a social influence check.
- Preserve real bargaining, persuasion, deception, intimidation, and favor requests.

### Steps
- [x] Add a failing regression for direct job acceptance not opening a pending social check.
- [x] Fix social declaration matching at the smallest safe boundary.
- [x] Verify focused exploration/storytelling/reward/dataset suites and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted acceptance regression fails before the fix and passes after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence: direct job acceptance included both an NPC name and `accept`, so the exploration social matcher selected `SocialApproachType.PERSUADE` and opened another social check.
- Regression evidence: `test_plain_job_acceptance_does_not_open_social_check` failed before the fix with an `ExplorationDeclarationPrompt(... kind=SOCIAL, approach=PERSUADE ...)` and passes after removing bare `accept`/`agree` from the automatic persuade term set.
- Preservation check: the same regression verifies real bargaining still produces a social prompt.
- Verification after fix: `python -m unittest tests.test_exploration_procedures tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation -v` passed 95 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-acceptancefix-w2` launched locally as PID `49476` at `2026-05-21T09:11:59-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Next monitoring target: verify positive `close_scene_now` acceptance advances out of the briefing without opening another social check, then verify High Road trap discovery reward.
- Monitoring result: positive close-pressure acceptance advanced to `scene-00-high-road-journey`, and a later successful Investigation check recorded `hidden_subgoal_completed`, `scene_goal_completed`, and `discovery_made` reward.
- Stop reason for `f100-acceptancefix-w2`: after the snare was detected, reasonable trap-handling declarations such as using Mage Hand to spring the line and marking the trap to steer clear were rejected as invalid disarm attempts lacking `Thieves' Tools`. Runner PID `49476` and children were stopped before pilot expansion.

## 2026-05-21 - DeepSeek Dataset Detected Trap Safe-Resolution Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Fix detected-trap declarations that safely spring, mark, avoid, or steer around the snare so they resolve through typed exploration state instead of being misrouted to the thieves-tools disarm check.
- Preserve the existing explicit disarm path for real `Thieves' Tools` disarm declarations.

### Steps
- [x] Add failing regressions for safe Mage Hand trap triggering and party-wide trap bypass from natural storytelling declarations.
- [x] Implement the smallest typed exploration-engine change for safe trigger and party-wide bypass.
- [x] Verify focused exploration/storytelling/trajectory/reward/dataset suites and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted safe-trigger and bypass regressions fail before the fix and pass after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-acceptancefix-w2`: after detecting the High Road snare, the positive pilot tried to spring it with Mage Hand and later mark/steer clear, but both were routed to the disarm procedure and failed with `Disarm Goblin Snare Line requires an explicit tool choice for disarm. Valid tools: Thieves' Tools.`
- Regression evidence: `test_detected_trap_can_be_safely_sprung_from_range` and `test_detected_trap_can_be_marked_and_bypassed_by_party` failed before the fix, then passed after routing those natural declarations through typed safe-trigger and party-wide bypass intents.
- Verification after fix: `python -m unittest tests.test_exploration_procedures tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation -v` passed 97 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-safetrapfix-w2` launched locally as PID `49476` at `2026-05-21T09:53:01-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm detected-trap handling no longer records invalid actions, then continue to first completed pilot episodes and inspect the pilot control decision.
- Stop reason for `f100-safetrapfix-w2`: `conversation-002-negative` asked whether goblins attack in the dark and the hostile-escalation detector treated the contextual question as an attack declaration, producing `Who are you trying to attack or physically force into the fight?`. Runner PID `49476` and children were stopped before pilot expansion.

## 2026-05-21 - DeepSeek Dataset Contextual Attack Question Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Prevent questions about whether goblins/bandits/monsters attack from being treated as player attack declarations.
- Preserve direct hostile declarations such as `I attack Gundren Rockseeker.`

### Steps
- [x] Add a failing regression for a contextual question about goblins attacking at night.
- [x] Fix hostile action detection at the `attack` word classification boundary.
- [x] Verify focused hostile-escalation tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted contextual-attack regression fails before the fix and passes after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-safetrapfix-w2`: the live negative pilot asked `do goblins attack in the dark?` and the hostile-escalation detector treated the contextual question as an overt attack because `attack` matched as a bare hostile verb.
- Regression evidence: `test_question_about_goblins_attacking_remains_story_mode` failed before the fix with `CLARIFICATION_REQUIRED` and now passes.
- Preservation check: `test_direct_attack_declaration_still_escalates` and `test_information_request_about_attack_patterns_remains_story_mode` both pass.
- Verification after fix: `python -m unittest tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_story_demo_party_connector tests.test_rewards tests.test_trajectory tests.test_deepseek_100_dataset_runner -v` passed 98 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-attackquestionfix-w2` launched locally as PID `61120` at `2026-05-21T10:10:43-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm contextual attack questions no longer record invalid actions, then continue to trap handling and pilot-control completion.
- Monitoring result: positive trap discovery worked and no trap invalid was recorded; the episode reached combat.
- Stop reason for `f100-attackquestionfix-w2`: after Player 1 cast Magic Missile and spent its action, the connector still treated stale action groups as available, asked Player 1 to cast/attack again, then fallback also attempted an action. The episode failed with `The actor has already used its action this turn.`

## 2026-05-21 - DeepSeek Dataset Combat Action-Spent Fallback Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Prevent the player connector from choosing attack/cast/dodge actions after the active actor's action is already spent.
- End the active actor's turn when the view indicates `Action no`, even if projected action groups still contain stale action choices.

### Steps
- [x] Add failing connector regressions for action-spent combat retry and fallback behavior.
- [x] Fix combat action availability detection and validation from the active actor action-economy summary.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted action-spent connector regressions fail before the fix and pass after it.
- [x] Focused and broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-attackquestionfix-w2`: after `/cast player-1 magic-missile monster-goblin-1`, the view summary showed `player-1 ... Action no`, but action groups still exposed attacks and magic. The connector trusted the stale action groups, submitted more action-cost commands, and fallback chose `/dodge` instead of `/endturn`.
- Regression evidence: `test_party_connector_retries_attack_when_active_actor_action_spent` and `test_party_connector_fallback_ends_turn_when_active_actor_action_spent` failed before the fix and now pass.
- Preservation check: `test_party_connector_retries_endturn_when_action_is_available` and `test_party_connector_fallback_uses_dodge_instead_of_endturn_when_actions_remain` still pass, so the connector only ends turns when the active actor has actually spent its action.
- Verification after fix: `python -m unittest tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 100 tests; focused `py_compile` passed; `git diff --check` reported only CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-combatspentfix-w2` launched locally as PID `56768` at `2026-05-21T10:49:24-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 2 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm combat turns now end cleanly after action spend, then continue to pilot-control completion.
- Monitoring result: `f100-combatspentfix-w2` produced one completed positive pilot episode with total reward `5.995`, 0 invalid actions, hidden/snare rewards, trap resolution, terminal success, and action-spent `/endturn` behavior working in combat.
- Stop reason for `f100-combatspentfix-w2`: the run was correctness-clean but slow because every spent player action still required a DeepSeek request to choose `/endturn`. Runner PID `56768` and children were stopped before pilot completion so the connector could fast-path deterministic spent-action end turns.
- Fast-path optimization: added a combat loop shortcut that submits `/endturn <active_actor_id>` without an LLM call when the active player-owned actor has `Action no`, while preserving validator coverage for illegal action-cost commands after action spend.
- Regression evidence: `test_party_connector_fast_paths_endturn_when_active_actor_action_spent` failed before the fix because the connector called the LLM transport, then passed after the fast path. Existing spent-action retry/fallback tests were updated to preserve validator coverage and assert no invalid-output fallback is needed on the fast path.
- Verification after fast path: targeted spent-action tests passed; `python -m unittest tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 101 tests; focused `py_compile` passed.
- Fresh run: `f100-fastendturn-w4` launched locally as PID `12580` at `2026-05-21T11:48:57-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-fastendturn-w4`: initial health was clean with 4 active pilot episodes and 0 invalid actions, but early briefing turns were still spending too many DeepSeek calls before close-scene pressure activated. Runner PID `12580` and children were stopped before pilot completion to tighten stale-scene pressure.
- Prompt-control optimization: changed stale-scene pressure from 6 same-scene story actions to 4, and added stale-scene guidance for negative examples so they keep lower-quality flavor while still moving the scene forward with a concrete imperfect action.
- Regression evidence: `test_party_connector_sends_scene_closure_pressure_to_positive_player` failed at 4 turns before the threshold change and passed after it. `test_player_agent_negative_profile_prompts_legal_stalling_examples` failed before the negative stale-scene instruction and passed after it.
- Verification after prompt-control fix: targeted prompt-control tests passed; `python -m unittest tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 101 tests; focused `py_compile` passed.
- Fresh run: `f100-fastpressure-w4` launched locally as PID `27700` at `2026-05-21T11:59:56-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-fastpressure-w4`: the runner was stopped after `conversation-003-positive` submitted invalid `/travel start`, producing an `invalid_action` row before the retry could recover. Root cause: story-mode slash commands bypassed local connector validation, so the authoritative session rejected an unsupported travel subcommand after the reward trajectory had already recorded it.
- Local-only re-plan: add a failing regression that `/travel start` is rejected and retried before submission, implement minimal story `/travel` subcommand validation in the connector, re-run focused and broad verification, then launch a fresh local dataset run without commit or GitHub operations.
- Slash preflight fix: added connector-side story `/travel` subcommand validation that mirrors the authoritative session's allowed `status|pace|route|advance|resume|engage` surface and retries unsupported travel commands before submission.
- Regression evidence: `test_party_connector_retries_unknown_story_travel_command_before_submit` failed before the fix with `invalid_action_retries` equal to 0, then passed after the connector preflight.
- Verification after slash preflight: `python -m unittest tests.test_story_demo_party_connector -v` passed 29 tests; `python -m unittest tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 102 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-storyslashfix-w4` launched locally as PID `52788` at `2026-05-21T12:46:41-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-storyslashfix-w4`: the runner was stopped after `conversation-003-positive` failed with connector exit code 1. Root cause: a transient DeepSeek `URLError` / connection reset during a concurrent speaker-vote request was logged in raw interactions and then propagated out of `LLMHttpTransport.post` without retrying.
- Transport resilience fix: extended the existing bounded HTTP POST retry loop from incomplete reads to transient `URLError` failures. Exhausted retries still raise `LLMResponseError`; no synthetic action or fallback content is generated.
- Regression evidence: `test_post_retries_transient_url_error` failed before the fix with immediate `LLMResponseError`, then passed after the transport retried and consumed the successful second response.
- Verification after transport fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 106 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-transportretry-w4` launched locally as PID `39088` at `2026-05-21T12:59:27-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-transportretry-w4`: the run stayed technically clean through early pilot monitoring, with 0 invalid rows, 0 raw transport errors, and 0 stderr, but stale briefing scenes were still too slow. Positive stale-scene actions sometimes accepted while adding a new demand such as a ledger request, causing another check instead of cleanly closing the briefing.
- Stale-closure prompt fix: strengthened positive close-scene guidance so the Gundren briefing uses plain acceptance/departure and explicitly avoids new demands, ledger requests, bargaining terms, or fresh checks.
- Regression evidence: `test_party_connector_sends_scene_closure_pressure_to_positive_player` failed before the fix because the stale-scene instructions did not include the no-new-demands rule or a plain acceptance example, then passed after the prompt change.
- Verification after stale-closure prompt fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 106 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-staleclosure-w4` launched locally as PID `53176` at `2026-05-21T13:13:26-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-staleclosure-w4`: one positive pilot reached good reward shape (`3.42` reward, 2 hidden subgoals, 2 scene goals, 1 party goal, 0 invalids) but then failed after three empty speaker-vote outputs. Root cause: DeepSeek returned `finish_reason=length` with `reasoning_content` but empty `message.content`; the 2200-token speaker-vote completion budget was too small for late-scene vote context.
- Speaker-vote budget fix: increased `party_speaker_vote` max output tokens from 2200 to 6000 for DeepSeek reasoning models, leaving player action decisions at 3000.
- Regression evidence: `test_deepseek_json_requests_use_large_completion_budgets_for_reasoning_models` failed before the fix with `2200 not greater than or equal to 6000`, then passed after the budget increase.
- Verification after speaker-vote budget fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 106 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-votebudget-w4` launched locally as PID `12244` at `2026-05-21T13:53:49-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-votebudget-w4`: early pilot was technically clean with 0 invalid rows, 0 stderr, 0 raw errors, and no length-capped speaker votes, but a positive briefing still accepted extra ledger/inspection demands before close-scene pressure activated. Root cause: `/check` responses are excluded from story-rotation counts, so the threshold of 4 counted story actions was still too late for real briefing trajectories.
- Scene-pressure threshold fix: changed `close_scene_now` activation from 4 counted story actions to 3, so checks and prompt turns do not delay stale-scene pressure too far into the briefing.
- Regression evidence: `test_party_connector_sends_scene_closure_pressure_to_positive_player` failed before the fix at 3 counted story actions with `scene_progress_pressure=normal`, then passed after the threshold change.
- Verification after pressure-threshold fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 106 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-pressure3-w4` launched locally as PID `26700` at `2026-05-21T14:07:17-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-pressure3-w4`: early pilot remained technically clean with 0 invalid rows, 0 stderr, 0 raw errors, and 0 length-capped votes, but a positive stale acceptance phrased as `"Gundren, you've got a deal..."` still opened a Charisma check instead of closing the briefing. Root cause: prompt-only closure guidance is not strict enough; the connector needs to reject stale Gundren-briefing outputs that add negotiation/check triggers or omit explicit accept-and-depart wording.
- Stale-briefing validator fix: added connector validation under `close_scene_now` for `scene-waterdeep-gundren-briefing`, requiring explicit accept-and-depart wording and rejecting deal/ledger/bargain/pay/gold/potion/secret/found/magic/spell/inspect/copy/question triggers before submission.
- Regression evidence: `test_party_connector_retries_stale_briefing_closure_that_can_trigger_checks` failed before the validator with 0 invalid retries, then passed by retrying to plain `"Gundren, we accept the job..."` wording before any submission.
- Verification after stale-briefing validator fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 107 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-stalevalidate-w4` launched locally as PID `60208` at `2026-05-21T14:21:30-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-stalevalidate-w4`: stale validation improved one positive episode, but exact generated wording `"Gundren, we accept the job. Let us finish loading..."` still opened a Charisma request/favor check in other episodes. Root cause: the validator's canonical example used phrasing that the exploration interpreter can read as a request; the safe phrase already covered by `test_plain_job_acceptance_does_not_open_social_check` is `"Gundren, we accept the job. We will take the wagon to Phandalin."`
- Safe-acceptance wording fix: changed the stale-briefing canonical phrase to `"Gundren, we accept the job. We will take the wagon to Phandalin."` and reject `let us` phrasing under stale Gundren-briefing closure.
- Regression evidence: `test_party_connector_retries_stale_briefing_closure_that_can_trigger_checks` failed before the fix when the bad first output used `Let us...`, then passed after retrying to the safe no-check phrase. `test_plain_job_acceptance_does_not_open_social_check` also passed against the same safe phrase.
- Verification after safe-acceptance wording fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 107 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-safeaccept-w4` launched locally as PID `36940` at `2026-05-21T14:35:55-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-safeaccept-w4`: the run reached combat in `conversation-003-positive` with no transport errors or stderr, but the connector submitted invalid `/cast player-1 magic-missile monster-goblin-4 monster-goblin-2`; the server rejected the extra target token (`Expected an integer token, got 'monster-goblin-4'`) and recorded an invalid reward row. Root cause: connector combat validation did not reject malformed multi-target spell commands before submission.
- Cast-shape validator fix: added connector-side `/cast` command shape validation so the local retry loop rejects multi-target spell commands and visible-enemy target mismatches before the server records an invalid action.
- Regression evidence: `test_party_connector_retries_cast_with_multiple_targets` failed before the fix by submitting `/cast player-1 magic-missile monster-goblin-4 monster-goblin-2`, then passed after the connector retried to a single-target spell command before submission.
- Verification after cast-shape fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 108 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-castshape-w4` launched locally as PID `51680` at `2026-05-21T15:14:58-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm malformed multi-target `/cast` commands are retried before submission, then inspect pilot-control completion and reward/data artifacts.
- Monitoring result: `f100-castshape-w4` stayed technically clean with 0 invalid rows, 0 raw transport errors, and 0 stderr; the stale Gundren briefing closure worked, with positive and negative pilot episodes moving to `scene-00-high-road-journey`.
- Stop reason for `f100-castshape-w4`: the run was stopped before pilot completion because High Road scenes were still spending many valid low-progress prep/check turns instead of using the travel route/advance path to reach the ambush. Root cause under investigation: stale-scene pressure is generic after the briefing and does not force High Road actions toward authoritative `/travel` advancement.
- Local-only re-plan: add a failing regression for stale High Road closure, implement minimal scene-specific stale guidance/validation that drives travel to the ambush path without bypassing typed intents, re-run verification, then launch a fresh local run without GitHub operations.
- High Road travel-closure fix: under stale-scene pressure, `scene-00-high-road-journey` now rejects more natural prep/check declarations and forces the authoritative travel path: `/travel route phandalin` while travel status is idle, then `/travel advance 5` once a route is planned.
- Regression evidence: `test_party_connector_retries_stale_high_road_idle_scene_to_travel_route` failed before the fix with 0 invalid retries, then passed after retrying to `/travel route phandalin`; `test_party_connector_retries_stale_high_road_planned_route_to_travel_advance` failed before the route-planned branch with 0 invalid retries, then passed after retrying to `/travel advance 5`.
- Verification after High Road fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 33 tests; `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 110 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-highroadtravel-w4` launched locally as PID `32952` at `2026-05-21T15:36:42-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm High Road stale scenes route and advance through `/travel` commands, then inspect pilot-control completion and reward/data artifacts.
- Monitoring result: `f100-highroadtravel-w4` confirmed the High Road fix live: pilot episodes emitted `/travel route phandalin` followed by `/travel advance 5`, reached `scene-triboar-goblin-ambush`, and entered combat.
- Stop reason for `f100-highroadtravel-w4`: the run was stopped after 4 completed pilot results because combat preflight still allowed invalid range actions. The invalid rows were `/cast player-4 charm-person monster-goblin-2` (`Target is out of capability range`) and `/attack player-2 unarmed-strike monster-goblin-1` (`Target is out of melee range`). Root cause: connector validation checked option ids and visible targets but not map distance or spell range before submission.
- Combat distance validator fix: added map-position distance checks for melee attack option ids and range-limited targeted spells, while preserving the rules engine as final authority. Distant melee attacks now retry toward ranged/thrown options or dodge, and `charm-person` beyond 30 feet retries before the server records an invalid action.
- Regression evidence: `test_party_connector_retries_melee_attack_against_distant_target` and `test_party_connector_retries_range_limited_spell_against_distant_target` failed before the fix by submitting the invalid commands, then passed after retrying to legal thrown/ranged commands. The older syntax-repair attack test was adjusted to use an adjacent target so it still isolates missing-argument repair.
- Verification after combat distance fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 35 tests; `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 112 tests; focused `py_compile` passed; `git diff --check` reported only existing CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Fresh run: `f100-combatrange-w4` launched locally as PID `51928` at `2026-05-21T16:16:38-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm distant melee and short-range spell outputs are retried before submission, then inspect pilot-control completion and reward/data artifacts.
- Monitoring result: `f100-combatrange-w4` is no longer running. It created 5 pilot episode directories, 4 raw LLM logs/transcript markdown files, and 1 `episode_result.json`, but that result is failed (`conversation-003-positive`, connector exit `4294967295`). No completed/accepted dataset episode from this run is ready.
- Current stage: debug/re-plan before relaunch. Evidence to address next includes generic last-resort fallback text in `conversation-003-positive` and a `ConnectionResetError` in `conversation-004-negative` connector stderr.

## 2026-05-21 - DeepSeek Dataset Last-Resort Fallback Quality Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Remove generic meta fallback player text from positive and negative training transcripts.
- Preserve deterministic typed travel closure for stale High Road scenes.
- Treat the observed connection reset as secondary shutdown evidence unless reproduction shows it is the primary failure.

### Steps
- [x] Add failing regressions for last-resort fallback in stale Gundren briefing, High Road idle travel, and High Road route-planned travel.
- [x] Replace generic story last-resort text with scene-specific safe actions that move the current scene forward.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted last-resort fallback regressions fail before the fix and pass after it.
- [x] Focused connector suite passes.
- [x] Broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-combatrange-w4`: `conversation-003-positive` submitted generic meta fallback text twice: `I take a fresh angle in scene-waterdeep-gundren-briefing...`, which bypassed the intended direct-speech and stale-scene quality guards because `_execute_fallback_action` applied `_last_resort_fallback_decision` without revalidation.
- Regression evidence: the new last-resort tests failed before the fix with the generic `fresh angle` text, then passed after the last-resort path emitted direct job acceptance or `/travel` commands.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 38 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 115 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-lastresortfix-w4` launched locally as PID `48124` at `2026-05-21T16:46:44-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm generic `fresh angle` fallback no longer appears, stderr remains empty, and pilot episodes move from briefing through High Road travel into the ambush without invalid rows.
- Monitoring result: by `2026-05-21T17:07:05-07:00`, the run remained active with 4 pilot episode dirs, 0 result files, 0 non-empty stderr logs, 0 invalid/system-error trajectory rows, 0 generic `fresh angle` fallback hits, and live High Road routing in `conversation-001-positive` via `/travel route phandalin` then `/travel advance 5`.

## 2026-05-21 - DeepSeek Dataset Point-Target Spell Preflight Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a positive trajectory records an invalid point-target spell.
- Add connector preflight for combat spells that require grid coordinates, starting from the observed `mage-hand` failure and covering `light`.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-lastresortfix-w4` after `conversation-003-positive` recorded `Mage Hand requires a point target.`
- [x] Add a failing regression for `/cast <actor> mage-hand` without point coordinates.
- [x] Implement minimal combat cast validation for point-target spell coordinates.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted point-target spell regression fails before the fix and passes after it.
- [x] Focused connector suite passes.
- [x] Broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-lastresortfix-w4`: `conversation-003-positive` reached `demo-complete` but `episode_result.json` had `invalid_action_count: 1` and `trajectory_summary.error_messages` contained `Mage Hand requires a point target.`
- Regression evidence: `test_party_connector_retries_point_target_spell_without_coordinates` failed before the fix for both `mage-hand` and `light` by submitting `/cast player-1 <spell>` without coordinates, then passed after connector preflight rejected the missing point target and retried to `/cast player-1 magic-missile monster-goblin-1`.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 39 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 116 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-pointtarget-w4` launched locally as PID `31840` at `2026-05-21T17:30:19-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm point-target spell commands without coordinates no longer enter trajectories, stderr remains empty, and pilot episodes reach ambush combat without invalid rows.

## 2026-05-21 - DeepSeek Dataset Earlier Stale Scene Pressure Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a positive briefing starts a third question/demand instead of accepting the job.
- Activate stale-scene closure before the third recorded story action in a scene, so checks cannot delay closure into another demand.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-pointtarget-w4` after `conversation-001-positive` demanded Gundren's ledger and opened another check.
- [x] Add failing regressions for stale pressure at two prior story actions.
- [x] Implement minimal threshold change for stale-scene pressure.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] Targeted stale pressure regressions fail before the fix and pass after it.
- [x] Focused connector suite passes.
- [x] Broader unit suites pass.
- [x] Focused compile passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-pointtarget-w4`: `conversation-001-positive` had two prior natural-language briefing actions, a `/check`, then a third briefing action demanding the wagon ledger; `_scene_progress_pressure(2)` was still `normal`, so stale-briefing validation did not reject it.
- Regression evidence: the stale briefing and High Road closure tests failed at two prior story actions before the fix, then passed after `_scene_progress_pressure` returned `close_scene_now` at count 2.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 39 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 116 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-stalepressure2-w4` launched locally as PID `48492` at `2026-05-21T17:44:30-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm positive briefing closes after two prior story actions, High Road uses `/travel`, point-target spell commands without coordinates do not enter trajectories, and stderr/invalid rows stay clean.
- Status snapshot at `2026-05-21T18:05:29-07:00`: runner PID `48492` is alive with 10 active processes; 4 pilot episode directories exist, split 2 positive and 2 negative; 0 `episode_result.json` files are finalized; stderr bytes and invalid/system-error trajectory rows are both 0. Current stage remains active pilot generation/monitoring before the 10-episode pilot-control decision and before full 100-conversation expansion.

## 2026-05-21 - DeepSeek Dataset Logistics Voice Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a positive transcript accepts third-person persona narration.
- Add a regression for the observed `Mira heads... she mutters...` logistics action and keep player turns in first-person/direct character voice.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-stalepressure2-w4` after `conversation-003-positive` accepted `Mira heads to the stable yard...` as player output.
- [x] Add a failing regression for leading third-person logistics narration by Mira.
- [x] Implement the minimal validator fix for the missing `heads` self-narration verb.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_party_connector_retries_leading_third_person_logistics_action` fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v` passes.
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passes.
- [x] Focused `py_compile` passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-stalepressure2-w4`: `conversation-003-positive` had `Mira heads to the stable yard to inspect the wagon... "We will want those tarps tight..." she mutters...` in public player output. The direct-speech validator only matched persona-name narration when the verb appeared in `_SELF_NARRATION_VERBS_RE`, and `heads` was missing.
- Regression evidence: `test_party_connector_retries_leading_third_person_logistics_action` failed before the fix with `invalid_action_retries` equal to `0`, then passed after adding `heads?` to the self-narration verb list.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 40 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 117 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-logisticsvoice-w4` launched locally as PID `21012` at `2026-05-21T18:12:16-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Initial health at `2026-05-21T18:12:54-07:00`: 4 pilot episode directories exist, split 2 positive and 2 negative; 4 trajectory files and 4 transcript files exist; 0 completed results; 0 stderr bytes; shared campaign DM files stayed clean.
- Next monitoring target: confirm no `Mira heads`/persona-name self narration, no generic fallback text, no point-target spell commands without coordinates, no ledger regressions, and no invalid/system-error trajectory rows before pilot-control expansion.

## 2026-05-21 - DeepSeek Dataset Copied Template Guard

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when all pilot episodes copy the action schema example as a real turn.
- Replace the valid action sentence inside the JSON contract template with a shape-only placeholder and reject copied template/example text before submission.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-logisticsvoice-w4` after all 4 active pilot transcripts copied `Gundren, what signs of danger should we watch for on the road?`.
- [x] Add a failing regression for copied action-template text.
- [x] Change the action JSON template to a placeholder and add validator rejection for copied template/example text.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_party_connector_retries_copied_action_template_text` fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v` passes.
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passes.
- [x] Focused `py_compile` passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-logisticsvoice-w4`: by `2026-05-21T18:15:20-07:00`, all 4 active pilot episodes had accepted the exact action-template sentence `Gundren, what signs of danger should we watch for on the road?` as their first real action, producing duplicate low-diversity openings.
- Regression evidence: `test_party_connector_retries_copied_action_template_text` failed before the fix with `invalid_action_retries` equal to `0`, then passed after copied template/example text was rejected and retried.
- Fix: `_ACTION_DECISION_TEMPLATE` now uses `<write one unique in-character action or slash command here>` instead of a valid action sentence, prompt instructions explicitly say the template is shape-only, and `_validate_direct_story_speech` rejects copied template/example text before submission.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 41 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 118 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-templateguard-w4` launched locally as PID `51548` at `2026-05-21T18:18:52-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Initial health by `2026-05-21T18:20:50-07:00`: 4 pilot episode directories exist, split 2 positive and 2 negative; 0 completed results; 0 stderr bytes; 0 invalid/system-error rows; 0 copied-template hits; 0 suspicious third-person hits. The first accepted action was distinct direct quoted speech from player 3, followed by a legal `/check`.
- Next monitoring target: confirm the other active pilot episodes avoid template copying, close stale briefing cleanly, use High Road `/travel`, and reach ambush/combat without invalid rows.

## 2026-05-21 - DeepSeek Dataset Briefing Follow-Up Closure Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a positive briefing still spends its second story action on ledger/secret/find demands.
- Make the Waterdeep Gundren briefing close after one prior story action while keeping the existing two-action stale threshold for other scenes.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-templateguard-w4` after `conversation-001-positive` asked for Gundren's wagon ledger and hidden find as the second briefing story action.
- [x] Add a failing regression for a second briefing ledger detour after one prior story action.
- [x] Implement scene-specific pressure so `scene-waterdeep-gundren-briefing` enters `close_scene_now` after one prior story action.
- [x] Keep duplicate-topic coverage isolated from the Gundren briefing closure rule.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_party_connector_retries_second_briefing_ledger_detour` fails before the fix and passes after it.
- [x] `test_party_connector_retries_duplicate_story_topic_and_accepts_revision` still passes in a neutral fake scene.
- [x] `python -m unittest tests.test_story_demo_party_connector -v` passes.
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passes.
- [x] Focused `py_compile` passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-templateguard-w4`: `conversation-001-positive` reached briefing turn 4 with `"Gundren, if you'll not speak of your find, at least let me examine your wagon ledger..."`. The connector did not apply stale closure because `/check` turns do not count as story actions and the briefing had only one prior counted story action.
- Regression evidence: `test_party_connector_retries_second_briefing_ledger_detour` failed before the fix with `invalid_action_retries` equal to `0`, then passed after the briefing-specific pressure change. The retry prompt exposes `scene_progress_pressure: close_scene_now` at one prior briefing action.
- Fix: `_scene_progress_pressure` now takes `scene_id`; the Gundren briefing closes after one prior story action, while other scenes keep the two-action threshold.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 42 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 119 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-briefclose1-w4` launched locally as PID `43148` at `2026-05-21T18:27:49-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm one-question briefing closure, no copied-template hits, no ledger/secret follow-up detours, High Road `/travel` routing, no invalid/system-error rows, no stderr, and clean shared campaign DM files.

## 2026-05-21 - DeepSeek Dataset Observation Voice Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a player turn starts with third-person observation narration.
- Add coverage for `Thalen narrows his eyes...` and keep the direct-speech validator aligned with observed persona-name action verbs.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-briefclose1-w4` after `conversation-001-positive` accepted `Thalen narrows his eyes...` as player output.
- [x] Add a failing regression for leading third-person observation narration.
- [x] Implement the minimal validator fix for the missing `narrows` self-narration verb.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_party_connector_retries_leading_third_person_observation_action` fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v` passes.
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passes.
- [x] Focused `py_compile` passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-briefclose1-w4`: `conversation-001-positive` accepted `Thalen narrows his eyes, studying the dwarf's eagerness...` as a player action. The direct-speech validator uses persona names plus `_SELF_NARRATION_VERBS_RE`, and `narrows` was not in that list.
- Regression evidence: `test_party_connector_retries_leading_third_person_observation_action` failed before the fix with `invalid_action_retries` equal to `0`, then passed after adding `narrows?`.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 43 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 120 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-narrowsfix-w4` launched locally as PID `45876` at `2026-05-21T18:33:43-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm no leading persona-name/pronoun self narration, no copied-template hits, no ledger/secret follow-up detours, clean briefing closure, High Road `/travel` routing, no invalid/system-error rows, no stderr, and clean shared campaign DM files.

## 2026-05-21 - DeepSeek Dataset Canonical Acceptance Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a noncanonical acceptance phrase fails to leave the Gundren briefing.
- Require the exact transition-safe acceptance phrase under stale Gundren briefing closure.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-narrowsfix-w4` after `conversation-002-negative` used noncanonical acceptance and remained in `scene-waterdeep-gundren-briefing`.
- [x] Add a failing regression for noncanonical briefing acceptance.
- [x] Implement exact safe-phrase validation for stale Gundren briefing closure.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_party_connector_retries_noncanonical_briefing_acceptance` fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v` passes.
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passes.
- [x] Focused `py_compile` passes.
- [x] `git diff --check` has no substantive issues beyond existing CRLF warnings.
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-narrowsfix-w4`: three active pilot episodes reached High Road after acceptance, but `conversation-002-negative` submitted `"Gundren, the job is accepted. We'll guard the wagon north to Phandalin. Point us to it and we'll be off."` and remained in `scene-waterdeep-gundren-briefing`.
- Regression evidence: `test_party_connector_retries_noncanonical_briefing_acceptance` failed before the fix with `invalid_action_retries` equal to `0`, then passed after exact safe-phrase validation.
- Fix: `_SAFE_BRIEFING_ACCEPTANCE_TEXT` now holds the known transition-safe phrase, and `_validate_stale_scene_closure` requires that exact normalized text for stale Gundren briefing closure.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 44 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 121 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-canonicalaccept-w4` launched locally as PID `48796` at `2026-05-21T18:42:36-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Next monitoring target: confirm canonical acceptance exits briefing in all active pilot episodes, no leading persona-name/pronoun self narration, no copied-template hits, no ledger/secret follow-up detours, High Road `/travel` routing, no invalid/system-error rows, no stderr, and clean shared campaign DM files.

## 2026-05-21 - DeepSeek Dataset Post-Acceptance Travel Route Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Treat `f100-canonicalaccept-w4` evidence as a connector guardrail gap: after the briefing has already accepted the job and changed goals to rest/depart, a second natural-language acceptance can narrate acceptance without leaving `scene-waterdeep-gundren-briefing`.
- Require `/travel route phandalin` when the stale Gundren briefing is already in the accepted/rest state with travel idle.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Confirm the previous runner is stopped and inspect the failing local transcript/trajectory evidence.
- [x] Add a failing regression for accepted briefing still in scene requiring `/travel route phandalin`.
- [x] Implement the minimal connector validation and last-resort fallback change.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] New targeted regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from `f100-canonicalaccept-w4`: `conversation-002-negative` was already in `scene-waterdeep-gundren-briefing` with party goals `Get some rest at the inn and depart at first light.; Get the wagon safely onto the High Road.` and `Travel status: idle`. Submitting the canonical natural acceptance narrated acceptance but left the scene unchanged.
- Regression evidence: `test_party_connector_routes_after_briefing_acceptance_still_in_scene` failed before the fix with `invalid_action_retries` equal to `0`; `test_accepted_briefing_last_resort_routes_idle_travel` failed before the fix because last-resort fallback still used natural acceptance.
- Fix: added `_briefing_ready_for_travel()` and `_is_travel_route_phandalin()`. Stale Gundren briefing closure now requires `/travel route phandalin` when accepted/rest goals and idle travel are visible, and last-resort fallback uses the same command in that state.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 46 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 123 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-postacceptroute-w4` launched locally as PID `60616` at `2026-05-21T19:00:45-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Monitoring result before stop: 6 episode dirs, 2 clean completed positive results, 0 stderr bytes, 0 copied-template/voice/ledger guardrail hits, and High Road travel routing reached the ambush in multiple episodes.
- Stop reason for `f100-postacceptroute-w4`: `conversation-004-negative` produced invalid combat cast rows after the connector accepted `/cast player-4 detect-magic` and `/cast player-3 guidance player-1`; the rules engine rejected them with missing slots and missing `--skill`. Runner PID `60616` and children were stopped before further pilot expansion.

## 2026-05-21 - DeepSeek Dataset Combat Utility Spell Guard

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when combat casts pass connector validation but fail in the rules engine.
- Reject unsupported combat utility/support spell commands before submission, especially `detect-magic` without provable slots and `guidance` without required `--skill` arguments.
- Keep combat progress deterministic by retrying toward targeted enemy spells, ranged attacks, dodge, or endturn.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-postacceptroute-w4` after invalid combat spell rows appeared.
- [x] Add failing connector regressions for `detect-magic` and `guidance` combat casts.
- [x] Implement minimal combat spell validation and prompt filtering.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] New targeted regressions fail before the fix and pass after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-postacceptroute-w4`: `conversation-004-negative` reached combat and the connector accepted `/cast player-4 detect-magic` and `/cast player-3 guidance player-1`; the rules engine rejected them as invalid because the actor had no spell slots for `detect-magic` and `guidance` requires `--skill`.
- Regression evidence: `test_player_agent_combat_context_filters_unsupported_spell_options`, `test_party_connector_retries_unsupported_combat_detect_magic_cast`, and `test_party_connector_retries_unsupported_combat_guidance_cast` failed before the fix and passed after it.
- Fix: combat prompt context now exposes only targeted combat spell ids, and `_validate_combat_command` rejects unsupported non-targeted combat spells before they can enter the rules engine, while preserving existing point-target coordinate validation.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 49 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 126 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-combatspellguard-w4` launched locally as PID `18072` at `2026-05-21T19:44:05-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Stop reason for `f100-combatspellguard-w4`: pilot monitoring found the combat spell guard held, but after acceptance the runtime entered `scene-00-high-road-journey` and allowed extra acceptance, Detect Magic, wagon inspection, and check turns before `/travel route phandalin`. Runner PID `18072` and children were stopped before pilot expansion.

## 2026-05-21 - DeepSeek Dataset Immediate High Road Routing Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when accepted briefing output reaches the High Road scene but still allows first-turn inspection/casting/check detours.
- Treat `scene-00-high-road-journey` as travel-command closure immediately, so the first High Road story action routes or advances travel through the authoritative travel system.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-combatspellguard-w4` after High Road detours appeared before `/travel route phandalin`.
- [x] Add a failing connector regression for a first High Road idle-scene detour with no prior High Road story history.
- [x] Implement the minimal scene-pressure change so High Road travel closure applies immediately.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_party_connector_routes_high_road_idle_scene_before_any_detour` fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-combatspellguard-w4`: raw contexts showed accepted briefing had already transitioned to `scene-00-high-road-journey`, but `_scene_progress_pressure` returned `normal` at High Road story counts 0 and 1, so validation did not require `/travel route phandalin` yet.
- Regression evidence: `test_party_connector_routes_high_road_idle_scene_before_any_detour` failed before the fix with `invalid_action_retries: 0`, proving the connector accepted `Before we roll, I inspect the wagon again...` as the first High Road action.
- Fix: `_scene_progress_pressure()` now returns `close_scene_now` immediately for `scene-00-high-road-journey`, reusing the existing High Road travel closure validator and prompt instructions.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 50 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 127 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-highroadroute0-w4` launched locally as PID `56052` at `2026-05-21T20:00:54-07:00`, with 100 episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, and isolated campaign roots.
- Monitoring result before stop: 6 episode dirs, 2 completed positive results with rewards `5.01` and `3.65`, 0 invalid trajectory errors, 0 stderr bytes, and High Road route/advance commands appeared across active pilots.
- Stop reason for `f100-highroadroute0-w4`: negative combat transcripts repeated older public story/player chat entries after later combat actions, indicating transcript logger de-duplication by entry id was insufficient when old chat replayed with fresh ids.

## 2026-05-21 - DeepSeek Dataset Combat Transcript Replay Dedup Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when transcript markdown repeats old public chat after later combat actions.
- De-duplicate transcript chat entries by stable content fingerprint as well as entry id, so replayed old chat with fresh ids does not pollute RL transcript artifacts.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-highroadroute0-w4` after repeated combat transcript entries appeared.
- [x] Add a failing transcript logger regression for same chat text replayed under a new entry id.
- [x] Implement minimal transcript chat fingerprint de-duplication.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.

### Verification
- [x] `test_transcript_logger_dedupes_same_chat_text_when_entry_ids_change` fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-highroadroute0-w4`: transcripts for `conversation-002-negative` and `conversation-004-negative` replayed identical older briefing/ambush public chat entries after later combat actions even though trajectory errors stayed null.
- Regression evidence: `test_transcript_logger_dedupes_same_chat_text_when_entry_ids_change` failed before the fix with the duplicate text appearing twice when the same chat text was replayed under a different `entry_id`.
- Fix: `PartyTranscriptLogger` now tracks `_seen_chat_entry_fingerprints` keyed by visibility, category, speaker, and exact text, in addition to `_seen_chat_entry_ids`.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 51 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 128 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-transcriptdedupe-w4` launched locally as PID `60160` at `2026-05-21T20:34:09-07:00`, with 100 planned episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, transcripts, trajectories, and isolated campaign roots.
- Current monitoring at `2026-05-21T20:55:21-07:00`: runner PID `60160` alive, 6 pilot episode dirs, 3 positive and 3 negative dirs, 2 completed positive results, 4 in progress, 0 launcher stderr bytes, 0 non-null trajectory errors, 0 suspicious transcript hits, 0 duplicate public chat lines, and shared `campaigns/lmop/dm/**` clean.

## 2026-05-21 - DeepSeek Dataset Rolling Combat Transcript Outcome Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when transcript markdown stops recording public combat outcome lines while trajectory events still prove the mechanics resolved.
- Preserve replay de-duplication for identical chat text, but do not drop new combat outcome text when rolling encounter chat entry ids are reused.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-transcriptdedupe-w4` after `conversation-004-negative` showed later `/cast` and `/attack` commands without corresponding public combat outcome lines in the transcript.
- [x] Add a failing transcript logger regression for new combat text under a reused rolling `encounter:0` chat entry id.
- [x] Fix transcript de-duplication so content fingerprints suppress true replay duplicates, while reused entry ids with new text are still appended.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.
- [ ] Monitor the new pilot through combat and verify transcript outcome lines continue past rolling recent-event id reuse.

### Verification
- [x] `test_transcript_logger_records_new_chat_text_when_entry_id_is_reused` fails before the fix and passes after it.
- [x] `test_transcript_logger_dedupes_same_chat_text_when_entry_ids_change` still passes after the fix.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-transcriptdedupe-w4`: `conversation-004-negative` transcript lines 57-69 logged later combat commands/endturns only, while trajectory turns 30, 34, 36, and 38 had null errors plus recent miss/damage/death events.
- Root cause: encounter chat projection reuses rolling ids such as `encounter:0`; `PartyTranscriptLogger` skipped reused entry ids before comparing stable content fingerprints, so new combat outcome text disappeared once the recent-event window shifted.
- Fix: `PartyTranscriptLogger` still requires non-empty entry ids, but it now de-duplicates on `visibility/category/speaker/text` fingerprints instead of treating entry id reuse as sufficient to skip a line.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 52 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 129 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-transcriptoutcomes-w4` launched locally as PID `45608` at `2026-05-21T21:07:46-07:00`, with 100 planned episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, transcripts, trajectories, and isolated campaign roots.
- Initial health at `2026-05-21T21:09:11-07:00`: runner PID `45608` alive, 4 pilot episode dirs, 2 positive and 2 negative dirs, 0 completed results, 4 trajectories, 4 raw logs, 4 transcripts, 0 launcher stderr bytes, 0 non-null trajectory errors, and shared `campaigns/lmop/dm/**` clean.
- Stop reason for `f100-transcriptoutcomes-w4`: the rolling-id fix worked for mid-combat outcomes, but completed `conversation-003-positive` ended with transcript line 39 `/cast player-1 magic-missile monster-goblin-4` and omitted the terminal damage/death outcome lines that were visible in the final trajectory post-observation.

## 2026-05-21 - DeepSeek Dataset Terminal Combat Transcript Outcome Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a terminal killing blow is recorded as a player command but its public damage/death result is missing from the transcript markdown.
- Preserve terminal `Recent events:` combat lines in transcripts even when the final `demo-complete` snapshot no longer exposes those outcomes as chat entries.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-transcriptoutcomes-w4` after `conversation-003-positive` omitted final damage/death transcript lines.
- [x] Add a failing transcript logger regression for `Recent events:` combat lines in terminal/demo-complete snapshots.
- [x] Fix `PartyTranscriptLogger` to append `Recent events:` lines as public combat transcript lines, de-duplicated by the existing content fingerprint.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.
- [x] Monitor the new pilot through a completed combat episode and verify final terminal damage/death outcome lines are present in the transcript.

### Verification
- [x] `test_transcript_logger_records_recent_event_summary_lines` fails before the fix and passes after it.
- [x] Transcript logger regressions for reused ids and same-text replay still pass.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-transcriptoutcomes-w4`: the final trajectory post-observation included `Goblin Ambusher 4 takes 11 force damage` and `Goblin Ambusher 4 dies`, but the transcript ended at the submitted `/cast` command because terminal `demo-complete` snapshots exposed those outcomes only in `summary_lines`.
- Fix: `PartyTranscriptLogger.record_snapshots()` now scans the `Recent events:` block in each view's `summary_lines` and appends those lines as `[chat:public:combat] System: ...`, using the same content fingerprint set to avoid duplicating normal chat-entry output.
- Focused verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 53 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 130 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-terminaloutcomes-w4` launched locally as PID `24272` at `2026-05-21T21:27:28-07:00`, with 100 planned episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, transcripts, trajectories, and isolated campaign roots.
- Initial health at `2026-05-21T21:28:50-07:00`: runner PID `24272` alive, 4 pilot episode dirs, 2 positive and 2 negative dirs, 0 completed results, 4 trajectories, 4 raw logs, 4 transcripts, 0 launcher stderr bytes, 0 non-null trajectory errors, and shared `campaigns/lmop/dm/**` clean.
- Completed-pilot evidence at `2026-05-21T21:47:01-07:00`: `conversation-001-positive` wrote `episode_result.json` with `status=completed`, `terminal_reason=demo-complete`, `turn_count=17`, `total_reward=4.55`, `invalid_action_count=0`, and `transition_count=13`.
- Transcript evidence: the completed `conversation-001-positive` transcript includes all four Magic Missile killing blows followed by public combat damage/death outcome lines, including the final terminal `Goblin Ambusher 3 takes 10 force damage` and `Goblin Ambusher 3 dies` lines.
- Dataset-quality evidence for the completed episode: `training_transitions.jsonl` has 13 records and `transition_quality.json` reports `status=pass`; the per-episode preference-pair file is empty, which is expected for single-trajectory exact-context pairing and will be judged at the combined scene-level preference stage after more mixed pilot episodes complete.
- Current run state at `2026-05-21T21:47:01-07:00`: runner PID `24272` remains alive, 5 pilot episode dirs exist, 1 completed positive episode result exists, launcher stderr is still 0 bytes, trajectory parsing shows 0 non-null errors across 5 trajectory files, and transcript scans show 0 suspicious hits and 0 duplicate public chat lines.

## 2026-05-21 - DeepSeek Dataset Repeated Combat Outcome Text Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when transcript markdown suppresses a legitimate repeated combat outcome text.
- Preserve replay de-duplication for repeated recent-event windows, while allowing two distinct rolls to produce the same outcome text, such as two `fire-bolt misses Goblin Ambusher 3.` lines.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-terminaloutcomes-w4` after `conversation-003-positive` omitted a second `fire-bolt misses Goblin Ambusher 3.` line after a distinct Player 1 Fire Bolt roll.
- [x] Add a failing transcript logger regression for repeated recent-event outcome text after distinct roll events.
- [x] Fix recent combat event de-duplication to use ordered recent-event sequence overlap instead of global text-only fingerprints.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.
- [ ] Monitor the new pilot through repeated combat miss/hit text and verify both distinct occurrences are preserved without replay duplicates.

### Verification
- [x] `test_transcript_logger_records_repeated_recent_event_text_after_distinct_rolls` fails before the fix and passes after it.
- [x] Transcript logger regressions for same-text chat replay, reused entry ids, and terminal recent events still pass.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-terminaloutcomes-w4`: `conversation-003-positive` transcript lines 51-58 logged Player 4 Fire Bolt roll plus miss, then Player 1 Fire Bolt roll, but omitted the second identical miss text. The trajectory post-observation for turn 24 included both `Player 1 rolled 4 for fire-bolt: total 9.` and `fire-bolt misses Goblin Ambusher 3.` with no error.
- Root cause: terminal/recent-event transcript de-duplication reused the same global `visibility/category/speaker/text` fingerprint set, so legitimate repeated combat text was treated as old replay instead of a distinct event after a different roll.
- Fix: `PartyTranscriptLogger` now tracks ordered recent combat event text and appends only the suffix beyond the longest existing sequence overlap. This suppresses replayed recent-event windows while preserving repeated outcome text after distinct preceding events.
- Focused regression verification: the new repeated-outcome test plus same-text replay, reused-id, and terminal-recent-events tests passed.
- Focused connector verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 54 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 131 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-combatsequence-w4` launched locally as PID `11152` at `2026-05-21T21:55:27-07:00`, with 100 planned episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, transcripts, trajectories, and isolated campaign roots.
- Initial health at `2026-05-21T21:56:35-07:00`: runner PID `11152` alive, 4 pilot episode dirs, 2 positive and 2 negative dirs, 0 completed results, 4 trajectory files, 0 launcher stderr bytes, 0 non-null trajectory errors, and shared `campaigns/lmop/dm/**` clean.
- Stop reason for `f100-combatsequence-w4`: non-terminal `Recent events:` summary lines replayed older combat events with mutated current HP text after `conversation-001-positive` Player 4 Magic Missile, polluting transcript lines 39-46 and 51-58.

## 2026-05-21 - DeepSeek Dataset Nonterminal Recent-Events Replay Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when non-terminal `Recent events:` summary lines replay mutable old combat events into the transcript.
- Preserve live combat transcript output from chat entries, preserve repeated live outcome text after distinct events, and use summary-line recovery only for terminal/demo-complete snapshots.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-combatsequence-w4` after non-terminal recent-event summaries replayed older combat events with mutated HP text.
- [x] Add a failing transcript logger regression proving non-terminal `Recent events:` replay is ignored.
- [x] Adjust the repeated-outcome regression to use live combat chat entries rather than non-terminal summary lines.
- [x] Fix summary-line recovery so it runs only for `Runtime mode: demo-complete` views.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch the local 100-conversation DeepSeek run after the fix.
- [ ] Monitor the new pilot through live combat and terminal completion to verify no non-terminal summary replay, no missing repeated combat outcomes, and terminal final outcomes remain present.

### Verification
- [x] `test_transcript_logger_ignores_nonterminal_recent_event_summary_replay` fails before the fix and passes after it.
- [x] `test_transcript_logger_records_repeated_recent_event_text_after_distinct_rolls` still passes using live combat chat entries.
- [x] Transcript logger regressions for same-text replay, reused ids, and terminal recent events still pass.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-combatsequence-w4`: after `/cast player-4 magic-missile monster-goblin-1`, transcript lines 39-46 replayed older Goblin 3 death, Player 2 Fire Bolt, and Goblin 2 death events, and rewrote the earlier Fire Bolt damage line as `HP 1/10` instead of the original `HP 8/10`.
- Root cause: non-terminal `summary_lines` `Recent events:` are a rolling view of recent combat state, not an immutable event-log transcript source. Using them outside terminal recovery can replay old events and reflect current HP rather than the original event-time HP.
- Fix: `_record_recent_event_summary_lines()` now exits unless the view reports `Runtime mode: demo-complete`. Live combat transcript lines come from chat entries and ordered event-sequence overlap; terminal `demo-complete` still recovers final damage/death lines from `Recent events:`.
- Focused regression verification: non-terminal replay, repeated live outcome text, same-text replay, reused-id, and terminal-recent-events tests passed.
- Focused connector verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 55 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 132 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-chatevents-w4` launched locally as PID `8812` at `2026-05-21T22:15:33-07:00`, with 100 planned episodes, 50 positive, 50 negative, 10-episode pilot, 4 workers, raw logs, transcripts, trajectories, and isolated campaign roots.

## 2026-05-21 - DeepSeek Dataset Story Command Guard Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work while dataset generation is active.
- Stop and debug `f100-chatevents-w4` after pilot trajectory rows recorded invalid story commands before the dataset could expand.
- Prevent the autonomous party connector from submitting malformed story-mode slash commands to the web server, preserving trajectory quality for RL data.
- Normalize live travel status spellings so `route-planned` and `route_planned` both drive `/travel advance 5`, not invalid `/travel resume`.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Inspect stopped pilot trajectory rows and transcripts for `conversation-002-negative`, `conversation-003-positive`, and `conversation-004-negative`.
- [x] Add failing regressions for hyphenated `route-planned` travel status and story-mode malformed slash commands.
- [x] Fix travel-status normalization and story-mode slash validation without adding new fallback behavior.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation DeepSeek run after the fix.
- [ ] Monitor the new pilot for zero non-null trajectory errors before allowing full expansion.

### Verification
- [x] New route-planned regression fails before the fix and passes after it.
- [x] New story slash-command regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-chatevents-w4`: `conversation-002-negative` submitted `/travel resume` while the observation showed `Travel status: route-planned`; `conversation-003-positive` submitted `/cast Detect Magic as ritual` and then `/ritual Detect Magic` while the ambush scene was still storytelling/interrupted.
- Root cause: connector travel-state checks only recognized underscore status names, while live views render hyphenated enum values. Story-mode slash validation only checked `/travel`, so malformed `/cast` and unknown `/ritual` were submitted to the authoritative server instead of being retried locally.
- Fix: `_travel_status()` now normalizes hyphenated live status values to underscore form, and storytelling slash validation now rejects unsupported slash verbs plus malformed `/cast` syntax before submission. Valid story-mode `/do`, `/improvise`, `/say`, `/story`, `/check`, `/status`, `/view`, `/travel`, and actor-owned `/cast` forms remain available.
- Focused regression verification: both new tests failed before the fix with zero retries and passed after the fix.
- Focused connector verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 57 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 134 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-storyslashguard-w4` launched locally as PID `44664` at `2026-05-21T22:39:06-07:00`.
- Initial monitoring proved the story slash/travel fixes through High Road and ambush transition: 5 episode dirs created, 1 positive episode completed, 0 trajectory errors, 0 stderr bytes, 0 suspicious story slash/travel transcript hits, and shared `campaigns/lmop/dm/**` stayed clean.
- Stop reason for `f100-storyslashguard-w4`: before pilot expansion, `conversation-005-positive` accepted `Leaning forward, I ask, "Gundren, what exactly are we hauling..."`, violating the direct-player-voice requirement. Runner PID `44664` was stopped, then 8 orphaned run-specific server/connector children were stopped successfully.

## 2026-05-21 - DeepSeek Dataset Narrated Direct-Speech Guard Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop the active run before pilot expansion when a player action wraps quoted dialogue in narrated speech such as `I ask`.
- Reject unquoted narrated-speech framing even when the same action contains direct quoted dialogue.
- Preserve valid direct dialogue such as `Gundren, what exactly are we hauling?`.
- Relaunch a fresh local 100-conversation DeepSeek run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-storyslashguard-w4` after `conversation-005-positive` accepted narrated direct speech.
- [x] Inspect the trajectory, transcript, raw interaction evidence, and current validator branch.
- [x] Add a failing regression for narrated direct speech wrapped around quoted dialogue.
- [x] Fix direct-story-speech validation to reject narrated framing outside quotes.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [x] Monitor the new pilot for direct-player voice and zero non-null trajectory errors before allowing expansion.
- [ ] Relaunch a fresh local 100-conversation run after the monitor-side false positive stop.
- [ ] Use UTF-8-aware JSONL parsing in manual pilot monitoring before stopping future runs for trajectory integrity.

### Verification
- [x] New narrated-direct-speech regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence: `conversation-005-positive` trajectory line 3 and transcript both contain `Leaning forward, I ask, "Gundren, what exactly are we hauling..."` with no error.
- Root cause: `_validate_direct_story_speech()` checked `_NARRATED_SPEECH_RE`, but returned early when `_has_direct_dialogue(text)` was true, allowing narrated speech if it also contained a direct quote.
- Fix: direct-speech validation now strips quoted text before applying the narrated-speech regex, so narration such as `I ask` is rejected when it appears outside quotes while pure direct dialogue remains valid.
- Focused regression verification: `test_party_connector_retries_narrated_framing_around_quoted_dialogue` failed before the fix and passed after it.
- Focused connector verification after fix: `python -m unittest tests.test_story_demo_party_connector -v` passed 58 tests.
- Broad verification after fix: `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v` passed 135 tests.
- Compile/diff/cleanliness verification: focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; `git status --short campaigns/lmop/dm` stayed empty.
- Fresh run: `f100-directspeechguard-w4` launched locally as PID `31620` at `2026-05-21T23:07:03-07:00`.
- Monitoring result: the run reached 4 pilot episode dirs with direct-player voice and no UTF-8-parsed trajectory errors, but it was stopped before expansion after a manual PowerShell monitor read UTF-8 JSONL with the wrong default encoding and treated a valid non-ASCII row as malformed. The connector stderr was caused by the intentional stop while a request was in flight.

## 2026-05-22 - DeepSeek Dataset UTF-8 Pilot Monitor False Positive

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Correct the current stage after `f100-directspeechguard-w4` was stopped due monitor-side evidence, not a runner-quality defect.
- Relaunch a fresh 100-conversation run because the previous pilot was killed intentionally.

### Steps
- [x] Re-read latest pilot trajectories with explicit UTF-8 decoding.
- [x] Confirm the apparent malformed row in `conversation-002-negative` parses as valid JSONL under UTF-8.
- [x] Inspect connector stderr and identify it as stop-induced `ConnectionResetError`.
- [ ] Relaunch a fresh local 100-conversation run.
- [ ] Monitor the new pilot with UTF-8-aware trajectory parsing before allowing expansion.

### Verification
- [x] UTF-8 trajectory parse: all 34 rows across 4 `f100-directspeechguard-w4` trajectory files parsed, with 0 malformed rows and 0 non-null `error` rows.
- [x] Process cleanup: no active Python dataset/server/connector process remained after the stop.

### Review
- Current accepted target dataset count remains `0/100`; stopped pilot artifacts are debug evidence only.
- Historical local artifacts currently include 386 episode directories and 218 `episode_result.json` files across prior stopped attempts, but they are not the final balanced 50/50 dataset.

## 2026-05-22 - DeepSeek Dataset Proper-Name Third-Person Voice Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop `f100-utf8monitor-w4` before pilot expansion after proper-name third-person narration was submitted.
- Reject character-name narrated framing such as `Mira fixes Gundren...` before it reaches the authoritative web server.
- Preserve pure direct dialogue and legal slash commands.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-utf8monitor-w4` and verify 0 remaining run-specific processes.
- [x] Inspect the failing pilot trajectory row and validator code path.
- [x] Add a failing regression for proper-name third-person framing with a missed narration verb.
- [x] Fix the validator with the smallest root-cause change.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for direct-player voice and zero non-null trajectory errors before allowing expansion.

### Verification
- [x] New proper-name third-person regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-utf8monitor-w4`: `conversation-003-positive` trajectory line 3 submitted `Leaning forward, Mira fixes Gundren with a steady gaze. "How many days to Phandalin..."` with no trajectory error.
- Root cause: `_third_person_self_narration_match()` strips quoted text and checks character-name narration via `_SELF_NARRATION_VERBS_RE`, but that curated verb list did not include `fixes`, so `Mira fixes` was not rejected.
- Fix: added `test_party_connector_retries_proper_name_fixes_narrated_dialogue`, confirmed it failed before the fix with zero invalid-action retries, then added `fix(?:es)?` to the third-person self-narration verb set.
- Verification: adjacent direct-speech regressions passed, full connector suite passed 59 tests, broad LLM/story/dataset/reward/trajectory suite passed 136 tests, focused `py_compile` passed, `git diff --check` reported only existing LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-propernamefix-w4` was stopped before pilot expansion after another proper-name/pronoun narration escaped: `Mira kneels near the torn packs... She then moves to the horses...`.

## 2026-05-22 - DeepSeek Dataset Name-Mention Voice Guard Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop relying on an open-ended proper-name verb list for direct-player-voice validation.
- Reject any player persona name outside quoted dialogue as third-person self narration.
- Reject pronoun narration with an intervening adverb such as `She then moves`.
- Preserve pure direct dialogue, first-person action declarations, and legal slash commands.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-propernamefix-w4` and verify 0 remaining run-specific processes.
- [x] Inspect the failing pilot trajectory row and identify the repeated verb-list fragility.
- [x] Add failing regressions for proper-name narration with `kneels` and pronoun-adverb narration.
- [x] Replace proper-name verb matching with a stricter unquoted persona-name guard.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for direct-player voice and zero non-null trajectory errors before allowing expansion.

### Verification
- [x] New name-mention/pronoun-adverb regressions fail before the fix and pass after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-propernamefix-w4`: `conversation-003-positive` trajectory line 8 submitted `Mira kneels near the torn packs... She then moves to the horses...` with no trajectory error.
- Root cause: the proper-name self-narration detector still depended on a curated verb list, so every unlisted verb could leak third-person character-name narration. The pronoun detector also required the pronoun to be directly adjacent to a verb, so `She then moves` was not rejected.
- Fix: added regressions for proper-name `kneels` narration and pronoun-adverb narration, then changed `_third_person_self_narration_match()` to reject any unquoted player persona name and to allow up to two words between third-person pronouns and known narration verbs. Added `kneels?` for pronoun-only narration.
- Verification: new regressions failed before the fix and passed after it; direct-voice regression group passed; full connector suite passed 61 tests; broad LLM/story/dataset/reward/trajectory suite passed 138 tests; focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-nameguard-w4` was stopped before pilot expansion after connector fallback submitted `Gundren, what sign would prove this road danger is organized rather than random?` in `scene-triboar-goblin-ambush`.

## 2026-05-22 - DeepSeek Dataset Offstage NPC Fallback Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop connector fallback from addressing Gundren after the briefing scene.
- Use scene-safe fallback actions for travel/ambush contexts when LLM output is invalid.
- Preserve Gundren dialogue fallback only while the current scene is the Waterdeep briefing.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-nameguard-w4` and verify 0 remaining run-specific processes.
- [x] Inspect trajectory/transcript evidence and identify the stale fallback table as root cause.
- [x] Add a failing regression for invalid-LLM fallback in the ambush scene.
- [x] Fix story fallback selection to be scene-aware and avoid offstage NPC address.
- [x] Verify focused connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for direct-player voice, offstage NPC address, and zero non-null trajectory errors before allowing expansion.

### Verification
- [x] New offstage NPC fallback regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-nameguard-w4`: `conversation-001-positive` trajectory line 7 had `agent_id=player-2-controller`, `PreScene=scene-triboar-goblin-ambush`, and raw text `Gundren, what sign would prove this road danger is organized rather than random?` with no trajectory error.
- Transcript evidence showed `[system:player-2-controller] fallback after invalid LLM output` immediately before the stale Gundren line, proving it came from connector fallback rather than a new DeepSeek decision.
- Root cause: `_story_fallback_decision()` used a fixed fallback table with Gundren-addressed lines regardless of current scene; the table is only valid during `scene-waterdeep-gundren-briefing`.
- Fix: added `test_story_fallback_avoids_offstage_gundren_in_ambush_scene`, confirmed it failed before the fix, then made `_story_fallback_decision()` keep Gundren-addressed fallbacks only in the Waterdeep briefing, use travel slash fallbacks in High Road route states, and use first-person investigation/guarding actions in ambush/other scenes.
- Verification: focused fallback tests passed; full connector suite passed 62 tests; broad LLM/story/dataset/reward/trajectory suite passed 139 tests; focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-offstagefallback-w4` was stopped before pilot expansion after a DM-side DeepSeek HTTP request exhausted transient connection retries and recorded `LLM request failed: [WinError 10060]` in a trajectory row.

## 2026-05-22 - DeepSeek Dataset Transient LLM Retry Budget Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Reduce pilot-killing transient DeepSeek connection failures by increasing the default retry budget for non-HTTP transport errors.
- Preserve hard failures for HTTP status errors and persistent provider/network outages.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-offstagefallback-w4` and verify 0 remaining run-specific processes.
- [x] Inspect the trajectory error and identify exhausted DM-side LLM transport retries.
- [x] Add a failing regression for several transient URL errors before a successful response.
- [x] Increase the default post retry budget while preserving explicit retry override behavior.
- [x] Verify focused LLM transport tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice, offstage NPC address, and zero non-null trajectory errors before allowing expansion.

### Verification
- [x] New transient retry budget regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_llm_client -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-offstagefallback-w4`: `conversation-001-positive` trajectory line 3 recorded `LLM request failed: [WinError 10060]` after a valid Waterdeep briefing player action, with no connector/server stderr before the manual stop.
- Root cause: `LLMHttpTransport` retries transient `URLError`/connection failures, but the default `post_read_retries=2` allows only three total attempts, which was not enough for this live DeepSeek connection failure.
- Fix: added `test_default_post_retry_budget_covers_several_transient_url_errors`, confirmed it failed before the fix, then increased the default `LLMHttpTransport` `post_read_retries` from 2 to 4, allowing five total transient attempts. Explicit retry overrides still work.
- Verification: focused LLM transport suite passed 5 tests; broad LLM/story/dataset/reward/trajectory suite passed 140 tests; focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-retrybudget-w4` is active in pilot monitoring with 4 in-progress conversations, 15 submitted turns, 84 raw LLM rows, 0 malformed trajectory rows, 0 non-null trajectory errors, 0 stderr bytes, and 0 watched voice/offstage fallback pattern hits.
- Stop result: `f100-retrybudget-w4` was stopped at 45 submitted turns after the ad hoc monitor matched ` kneels ` in the full JSON trajectory row. Root-cause inspection showed the submitted raw texts were `/check` and monster `/endturn` commands; the match came from `recent_public_transcript_texts`, not player-controller `raw_text`.

## 2026-05-22 - DeepSeek Dataset Raw-Text Monitor False Positive

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Treat suspicious quality hits as pilot gates, but distinguish player submitted `raw_text` from replayed state/transcript fields.
- Relaunch a fresh local 100-conversation run with the monitor checking only relevant submitted action text and trajectory errors.

### Steps
- [x] Stop `f100-retrybudget-w4` before pilot expansion after the suspicious-pattern gate fired.
- [x] Verify 0 remaining run-specific processes.
- [x] Inspect the exact matched rows and fields.
- [x] Record the stop diagnosis in `manual-stop-pilot-quality-gate.json`.
- [x] Relaunch a fresh local 100-conversation run after tightening the manual monitor.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address in `raw_text`, malformed rows, and non-null trajectory errors before allowing expansion.

### Verification
- [x] `f100-retrybudget-w4` has 0 remaining run-specific Python processes.
- [x] Matched raw texts are `/check`, `/endturn monster-goblin-1`, `/endturn monster-goblin-2`, `/endturn monster-goblin-3`, and `/endturn monster-goblin-4`; none contain third-person player narration or offstage NPC address.

### Review
- Root-cause evidence: `rg -n "kneels"` showed the match inside `recent_public_transcript_texts`, including DM/check-result narration such as `Player-3 kneels...`, while the actual submitted turn `raw_text` was `/check` or monster `/endturn`.
- Root cause: the ad hoc monitor scanned full serialized JSON trajectory rows, so state snapshots and public transcript history could trigger player-output quality gates.
- Fix: no generation-code change. Tighten subsequent monitoring commands to parse JSONL with UTF-8 and apply voice/offstage patterns only to submitted `raw_text` fields for relevant player-controller turns.
- Relaunch result: `f100-rawtextmonitor-w4` started locally with root PID `13212`, 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-rawtextmonitor-w4` was stopped at 13 submitted turns after `conversation-003-positive` repeated the safe briefing acceptance as a system fallback and received `-0.20` reward for stalling/repetition.

## 2026-05-22 - DeepSeek Dataset Accepted-Briefing Fallback Progress Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop positive-profile fallback from repeating the safe briefing acceptance after the briefing has already accepted the job.
- Route idle travel once the accepted briefing exposes the high-road wagon goal, even if a prior failed social check removed the rest-at-inn goal.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-rawtextmonitor-w4` and verify 0 remaining run-specific processes.
- [x] Inspect trajectory, transcript, and state summary evidence for the repeated positive-profile fallback.
- [x] Add a failing regression for accepted briefing travel readiness without the rest-at-inn goal.
- [x] Fix accepted briefing readiness with the smallest root-cause change.
- [x] Verify focused fallback tests, full connector suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address in `raw_text`, malformed rows, non-null trajectory errors, and positive-profile fallback repetition before allowing expansion.

### Verification
- [x] New accepted-briefing fallback regression fails before the fix and passes after it.
- [x] Adjacent briefing/travel fallback tests pass.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-rawtextmonitor-w4`: `conversation-003-positive` submitted `Gundren, we accept the job. We will take the wagon to Phandalin.` from `player-4-controller` with reward `0.33`, then `[system:player-1-controller] fallback after invalid LLM output` submitted the exact same text and received reward `-0.20`.
- State evidence after the first acceptance: `Travel status: idle`, `Party goals: Get the wagon safely onto the High Road.`, and story log lines saying the wagon was loaded and ready for dawn departure. The scene was still `scene-waterdeep-gundren-briefing`, so fallback needed to route travel rather than repeat acceptance.
- Root cause: `_briefing_ready_for_travel()` required both `Get some rest at the inn and depart at first light` and `Get the wagon safely onto the High Road`; a failed social check path exposed only the high-road goal, so last-resort fallback considered the briefing not ready and repeated `_SAFE_BRIEFING_ACCEPTANCE_TEXT`.
- Fix: added `test_accepted_briefing_routes_idle_travel_without_rest_goal`, confirmed it failed with repeated acceptance, then relaxed `_briefing_ready_for_travel()` so idle travel plus the high-road wagon goal is enough to route `/travel route phandalin`.
- Verification: full connector suite passed 63 tests; broad LLM/story/dataset/reward/trajectory suite passed 141 tests; focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-briefingready-w4` started locally with root PID `32876`, 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-briefingready-w4` was stopped at 8 submitted turns after the fixed path routed `/travel route phandalin` successfully but left the scene id as Waterdeep with `Travel status: route-planned`, exposing a next-fallback risk.

## 2026-05-22 - DeepSeek Dataset Route-Planned Briefing Fallback Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- When travel has already been routed from the Waterdeep briefing but the scene id has not yet changed, fallback must advance travel rather than repeat briefing acceptance.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-briefingready-w4` and verify 0 remaining run-specific processes.
- [x] Inspect the route-planned briefing trajectory row.
- [x] Add a failing regression for route-planned travel while still in the Waterdeep briefing scene.
- [x] Fix Waterdeep briefing last-resort fallback to advance planned travel.
- [x] Verify focused fallback tests, full connector suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [x] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address in `raw_text`, malformed rows, non-null trajectory errors, duplicate story raw text, and route-planned briefing fallback progression before allowing expansion.

### Verification
- [x] New route-planned briefing fallback regression fails before the fix and passes after it.
- [x] Adjacent briefing/travel fallback tests pass.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-briefingready-w4`: `conversation-001-positive` submitted `/travel route phandalin` with no error. The row's post-observation still had `Current scene: scene-waterdeep-gundren-briefing`, but travel changed from `idle` to `route-planned` with route `Phandalin; 480 minutes at current pace`.
- Root cause: `_last_resort_fallback_decision()` handled travel status only after the scene id became `scene-00-high-road-journey`. In the transient Waterdeep/route-planned state, the same invalid-output fallback path would still return `_SAFE_BRIEFING_ACCEPTANCE_TEXT`.
- Fix: added `test_briefing_with_planned_route_last_resort_advances_travel`, confirmed it failed with repeated acceptance, then made Waterdeep briefing last-resort fallback return `/travel advance 5` when `_travel_status(view)` is `route_planned` or `traveling`.
- Verification: adjacent briefing/travel fallback tests passed; full connector suite passed 64 tests; broad LLM/story/dataset/reward/trajectory suite passed 142 tests; focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-routeplannedfix-w4` started locally with root PID `18520`, 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-routeplannedfix-w4` was stopped at 11 submitted turns after `conversation-002-negative` routed `/travel route phandalin` while the briefing still had the pending goal to decide whether to take the job, then accepted afterward.

## 2026-05-22 - DeepSeek Dataset Premature Briefing Travel Routing Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Do not route or advance travel from the Waterdeep briefing while the party still has an explicit goal to decide whether to take the Phandalin job.
- Preserve the accepted-briefing behavior: after acceptance is no longer pending, idle travel routes and planned travel advances.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-routeplannedfix-w4` and verify 0 remaining run-specific processes.
- [x] Inspect the premature route and subsequent acceptance trajectory rows.
- [x] Add a failing regression for idle travel with acceptance still pending.
- [x] Add a failing regression for route-planned travel with acceptance still pending.
- [x] Fix briefing readiness/advance gates with an explicit pending-acceptance detector.
- [x] Verify focused fallback tests, full connector suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address in `raw_text`, malformed rows, non-null trajectory errors, duplicate story raw text, premature route-before-acceptance, and route-planned briefing fallback progression before allowing expansion.

### Verification
- [x] New pending-acceptance idle routing regression fails before the fix and passes after it.
- [x] New pending-acceptance route-planned advancing regression fails before the fix and passes after it.
- [x] Adjacent briefing/travel fallback tests pass.
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-routeplannedfix-w4`: `conversation-002-negative` submitted `/travel route phandalin` from `scene-waterdeep-gundren-briefing`, changed travel status to `route-planned`, and then submitted `Gundren, we accept the job...`, which finally transitioned to `scene-00-high-road-journey`.
- Root cause: `_briefing_ready_for_travel()` treated the high-road wagon goal as sufficient, but pre-acceptance briefing states can also include that goal while still carrying `Hear Gundren out and decide whether to take the Phandalin job.` The route-planned fallback branch also needed the same pending-acceptance gate.
- Fix: added `_briefing_acceptance_pending()` and used it so idle briefing travel routes only after acceptance is no longer pending, and route-planned/traveling briefing state advances only after acceptance is no longer pending.
- Verification: adjacent briefing/travel fallback tests passed; full connector suite passed 66 tests; broad LLM/story/dataset/reward/trajectory suite passed 144 tests; focused `py_compile` passed; `git diff --check` reported only existing LF/CRLF warnings; shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-acceptgate-w4` started locally with root PID `7808`, 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.

## 2026-05-22 - DeepSeek Dataset Unprompted Story Check Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop story-mode player controllers from submitting `/check*` unless the server has issued a pending story-check prompt.
- Preserve legal `/check` answers for pending story-check prompts.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-acceptgate-w4` after the zero-error pilot gate failed.
- [x] Verify 0 remaining run-specific processes.
- [x] Inspect trajectory, transcript, and raw DeepSeek interaction evidence for the unprompted `/check investigation`.
- [x] Record the stop diagnosis in `manual-stop-unprompted-story-check.json`.
- [x] Add a failing regression for unprompted story-mode `/check*`.
- [x] Fix story slash-command validation so `/check*` is only valid through the pending story-check prompt path.
- [x] Verify focused connector tests, full connector suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address in `raw_text`, malformed rows, non-null trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, and unprompted `/check*`.

### Verification
- [x] New unprompted story-check regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_unprompted_story_check_before_submit tests.test_story_demo_party_connector.PartyConnectorTests.test_player_agent_negative_profile_prompts_legal_stalling_examples -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-acceptgate-w4`: `conversation-004-negative` trajectory line 11 submitted `/check investigation` with `prompt: null`, `Current scene: scene-triboar-goblin-ambush`, and error `There is no pending story check for this controller.`
- Raw DeepSeek evidence showed the model chose `/check investigation` even though the player context had `prompt: null` and no recent visible check entries.
- Root cause: `_validate_story_slash_command()` allowed `/check` during non-prompt storytelling turns, while `/check` is only executable when the server has already issued a story-check prompt.
- Fix: non-prompt story-mode `/check*` now fails connector validation before submit, and the player-agent prompt explicitly says never to use `/check` unless a visible story-check prompt is present.
- Relaunch result: `f100-unpromptedcheck-w4` started locally with 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-unpromptedcheck-w4` was stopped during pilot monitoring after `conversation-001-positive` submitted `/travel route phandalin` before the party accepted the job.

## 2026-05-22 - DeepSeek Dataset Premature Waterdeep Travel Command Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop direct DeepSeek `/travel*` commands from routing or advancing travel while Waterdeep briefing still has the explicit goal to decide whether to take the Phandalin job.
- Preserve post-acceptance travel routing and advancing.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-unpromptedcheck-w4` after the premature-travel quality gate fired.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect trajectory, transcript, and raw DeepSeek interaction evidence for premature `/travel route phandalin`.
- [x] Record the stop diagnosis in `manual-stop-premature-waterdeep-travel-command.json`.
- [x] Add a failing regression for direct `/travel route phandalin` before job acceptance.
- [x] Fix story slash-command validation so Waterdeep `/travel*` is rejected while job acceptance is pending.
- [x] Verify focused connector tests, full connector suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address in `raw_text`, malformed rows, non-null trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, and unprompted `/check*`.

### Verification
- [x] New direct premature-travel regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_waterdeep_travel_before_job_acceptance -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory -v`
- [x] `python -m py_compile dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-unpromptedcheck-w4`: `conversation-001-positive` trajectory line 5 submitted `/travel route phandalin` from `scene-waterdeep-gundren-briefing` with `Travel status: idle` and party goal `Hear Gundren out and decide whether to take the Phandalin job.`
- Raw DeepSeek evidence showed the model's topic focus was `accept job and plan travel route`, but the executable command only routed travel; it did not actually accept the job.
- Root cause: direct story-mode `/travel*` validation only checked travel command syntax and did not apply the pending job-acceptance gate unless the scene was already considered stale.
- Fix: Waterdeep briefing `/travel*` now fails connector validation while `_briefing_acceptance_pending(view)` is true, forcing the retry/fallback path to accept the job before routing.
- Relaunch result: `f100-accepttravelgate-w4` started locally with 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-accepttravelgate-w4` was stopped during pilot monitoring after the DM narrated offstage Gundren and Sildar as present during the Triboar ambush.

## 2026-05-22 - DeepSeek Dataset Offstage NPC DM Narration Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop DM story-turn outputs from making Gundren or Sildar speak or visibly act when their NPC ids are not in `visible_npc_ids`.
- Preserve valid absent/clue mentions such as asking who ambushed Gundren and Sildar.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-accepttravelgate-w4` after the offstage NPC quality gate fired.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect trajectory, transcript, and runtime context evidence for offstage Gundren/Sildar narration.
- [x] Record the stop diagnosis in `manual-stop-offstage-npc-dm-narration.json`.
- [x] Add a failing DM-runtime regression for offstage NPC speaker/action narration.
- [x] Fix DM story-turn validation and prompt guidance so offstage NPCs cannot speak or visibly act.
- [x] Verify focused DM runtime tests, connector tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, direct-player voice in `raw_text`, offstage NPC address/narration, malformed rows, non-null trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, and unprompted `/check*`.

### Verification
- [x] New offstage NPC DM narration regression fails before the fix and passes after it.
- [x] New story/check prompt guidance assertions fail before the fix and pass after it.
- [x] `python -m unittest tests.test_dm_runtime.DMRuntimeTests.test_story_turn_prompt_explicitly_requires_bare_json_object tests.test_dm_runtime.DMRuntimeTests.test_check_outcome_prompt_marks_rules_engine_result_as_final tests.test_dm_runtime.DMRuntimeTests.test_story_turn_retries_offstage_npc_speaker_and_action -v`
- [x] `python -m unittest tests.test_dm_runtime -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-accepttravelgate-w4`: `conversation-003-positive` trajectory line 8 had `Current scene: scene-triboar-goblin-ambush` and the DM transcript included `Gundren grows impatient`, `Gundren Rockseeker: "Well?"`, and `Sildar Hallwinter: Sildar kneels by a torn pack`.
- The session view's visible NPC ids were empty for the ambush; Gundren and Sildar should be absent/captive clues, not active speakers.
- Fix: DM story-turn and check-outcome prompts now state that only NPC ids listed in `visible_npc_ids` may speak or visibly act, check-outcome prompts include `visible_npc_ids`, and runtime parsing rejects Gundren/Sildar speaker entries or active present-tense narration outside Waterdeep unless their ids are visible.
- Verification: focused offstage/prompt regressions passed, full DM runtime passed 31 tests, full connector passed 68 tests, broad dataset/story/reward/trajectory suite passed 177 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-offstagedmguard-w4` started locally with 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-offstagedmguard-w4` was stopped during pilot monitoring after `conversation-006-negative` failed before any submitted turns because stale port `9110` was already occupied.

## 2026-05-22 - DeepSeek Dataset Port Preflight Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Prevent stale local HTTP/WS server ports from corrupting a live dataset run.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-offstagedmguard-w4` before pilot expansion after the stale-port failure.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect episode result and server/connector logs for the stale websocket collision.
- [x] Record the stop diagnosis in `manual-stop-stale-port-preflight-failure.json`.
- [x] Add a failing runner regression for occupied websocket ports.
- [x] Fix the dataset runner to preflight all planned HTTP and websocket ports before launching live episodes.
- [x] Verify focused runner tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, stale-port preflight failures, direct-player voice in `raw_text`, offstage NPC address/narration, malformed rows, structural trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, and unprompted `/check*`.

### Verification
- [x] New occupied-websocket regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_port_preflight_rejects_occupied_websocket_port -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-offstagedmguard-w4`: `conversation-006-negative` failed before any submitted turn. `web-server.stderr.log` showed `OSError: [Errno 10048]` while binding websocket `127.0.0.1:9110`, and the connector later hit an ownership mismatch against a stale session.
- Root cause: the runner waited only for the HTTP automation endpoint and did not preflight the paired websocket port. A stale websocket listener could leave the new server half-started and route the connector into the wrong session.
- Fix: the runner now checks every planned episode's HTTP and websocket ports with a socket probe before launching live episodes, failing early with an explicit stale-port error.
- Verification: focused port-preflight regression passed, full runner suite passed 10 tests, broad dataset/story/reward/trajectory suite passed 178 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-portpreflight-w4` started locally with 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-portpreflight-w4` was stopped during pilot monitoring after `conversation-001-positive` submitted `/travel advance 5` while travel was interrupted by the ambush hook.

## 2026-05-22 - DeepSeek Dataset Interrupted Travel Advance Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop story-mode player controllers from submitting `/travel route` or `/travel advance` while travel is interrupted by a pending scene hook.
- Preserve legal ways to resolve the interrupted scene through plain-text action or `/travel resume` when applicable.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-portpreflight-w4` after the interrupted-travel quality gate fired.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect trajectory and stop artifact evidence for `/travel advance 5` during interrupted travel.
- [x] Record the stop diagnosis in `manual-stop-interrupted-travel-advance.json`.
- [x] Add a failing regression for `/travel advance` while travel is interrupted.
- [x] Fix story slash-command validation so interrupted travel rejects `/travel route` and `/travel advance` before submit.
- [x] Verify focused connector tests, full connector suite, runner suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, stale-port preflight failures, direct-player voice in `raw_text`, offstage NPC address/narration, malformed rows, structural trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, unprompted `/check*`, and `/travel route` or `/travel advance` while interrupted.

### Verification
- [x] New interrupted-travel advance regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_travel_advance_while_interrupted -v`
- [x] `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-portpreflight-w4`: `conversation-001-positive` trajectory line 11 had `Current scene: scene-triboar-goblin-ambush`, `Travel status: interrupted`, raw text `/travel advance 5`, and server error `Travel is interrupted by a pending hook and must be resumed or resolved first.`
- Root cause: `_validate_story_slash_command()` gated Waterdeep pre-acceptance travel and unprompted checks, but did not treat interrupted travel as a state where route/advance commands are invalid.
- Fix: story-mode `/travel route` and `/travel advance` are now rejected locally when `_travel_status(view)` is `interrupted`, forcing DeepSeek or fallback to resolve the current hook through plain text or an allowed resume path instead of sending an invalid executable command.
- Verification: focused interrupted-travel regression passed, full connector suite passed 69 tests, full runner suite passed 10 tests, broad dataset/story/reward/trajectory suite passed 179 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-interruptedtravelgate-w4` started locally with 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-interruptedtravelgate-w4` was stopped during pilot monitoring after `conversation-001-positive` directly addressed offstage Gundren and Sildar in the Triboar ambush scene.

## 2026-05-22 - DeepSeek Dataset Offstage Direct Address Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop player story raw text from directly addressing Gundren or Sildar when they are absent rescue targets or clues rather than visible NPCs.
- Preserve direct Gundren/Sildar dialogue in Waterdeep or other scenes where the scene/visible NPC context makes them present.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-interruptedtravelgate-w4` before pilot expansion after the offstage direct-address quality gate fired.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect trajectory evidence for the accepted offstage direct address.
- [x] Record the stop diagnosis in `manual-stop-offstage-direct-address.json`.
- [x] Add a failing regression for direct Gundren/Sildar address in the Triboar ambush scene.
- [x] Fix player story validation and prompt guidance so offstage NPC direct address is retried locally.
- [x] Verify focused connector tests, full connector suite, runner suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, stale-port preflight failures, direct-player voice in `raw_text`, offstage NPC address/narration, malformed rows, structural trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, unprompted `/check*`, and `/travel route` or `/travel advance` while interrupted.

### Verification
- [x] New offstage direct-address regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_offstage_npc_direct_address_in_ambush_scene -v`
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_story_fallback_avoids_offstage_gundren_in_ambush_scene tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_offstage_npc_direct_address_in_ambush_scene tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_narrated_speech_as_direct_dialogue tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_narrated_framing_around_quoted_dialogue -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-interruptedtravelgate-w4`: `conversation-001-positive` trajectory line 14 had `Current scene: scene-triboar-goblin-ambush`, `Travel status: interrupted`, party goals to follow the hidden trail and rescue Gundren/Sildar, and raw text that spoke to `Gundren, Sildar` as if they were present.
- Root cause: `_validate_direct_story_speech()` rejected narrated speech and third-person self narration, but it did not know whether a directly addressed NPC was visible/onstage. Direct dialogue to absent rescue targets could therefore pass local validation and receive positive reward.
- Fix: player story validation now rejects direct address to known scene NPCs when they are not explicitly visible and the current scene id does not identify their present scene. The player prompt also says to address only visibly present NPCs and refer to absent Gundren/Sildar in third person.
- Verification: focused offstage/direct-speech regressions passed, full connector suite passed 70 tests, full runner suite passed 10 tests, broad dataset/story/reward/trajectory suite passed 180 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.
- Relaunch result: `f100-offstageaddressguard-w4` started locally with 100 planned episodes, 50 positive, 50 negative, a 10-episode pilot, and 4 workers.
- Stop result: `f100-offstageaddressguard-w4` was stopped during pilot monitoring after `conversation-002-negative` accepted quoted dialogue followed by third-person `She eyes...` narration.

## 2026-05-22 - DeepSeek Dataset Broad Pronoun Narration Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop player story raw text from appending broad `he/she` third-person self narration after quoted dialogue.
- Avoid another narrow verb-list-only patch; make the guard catch sentence-initial `he/she` narration even with previously unseen verbs.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-offstageaddressguard-w4` before pilot expansion after the pronoun-narration quality gate fired.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect trajectory evidence for the accepted `She eyes...` narration.
- [x] Record the stop diagnosis in `manual-stop-pronoun-eyes-narration.json`.
- [x] Add a failing regression for quoted dialogue followed by broad `She eyes...` narration.
- [x] Fix the player voice guard with a broad sentence-start `he/she` detector while preserving narrower `they` handling.
- [x] Verify focused connector tests, full connector suite, runner suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, stale-port preflight failures, direct-player voice in `raw_text`, offstage NPC address/narration, malformed rows, structural trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, unprompted `/check*`, and `/travel route` or `/travel advance` while interrupted.

### Verification
- [x] New broad-pronoun narration regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_quoted_dialogue_with_broad_pronoun_self_narration -v`
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_pronoun_adverb_narrated_action tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_quoted_dialogue_with_pronoun_self_narration tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_quoted_dialogue_with_broad_pronoun_self_narration tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_retries_offstage_npc_direct_address_in_ambush_scene -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-offstageaddressguard-w4`: `conversation-002-negative` trajectory line 3 accepted `"Gundren, what's the pay, exactly? ..."` followed by `She eyes the dwarf, a ledger already open in her mind.`
- Root cause: `_third_person_self_narration_match()` had been broadened for proper names, but `he/she/they` pronoun narration still depended on `_SELF_NARRATION_VERBS_RE`. The unseen verb `eyes` was not listed, so the row bypassed local retry validation.
- Fix: the pronoun detector now catches sentence-initial `he/she` narration after quote stripping regardless of the specific verb, while leaving `they` on the narrower verb-list path to avoid overmatching group or enemy references.
- Verification: focused broad-pronoun regression passed, full connector suite passed 71 tests, full runner suite passed 10 tests, broad dataset/story/reward/trajectory suite passed 181 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.

## 2026-05-22 - DeepSeek Dataset Contextual Attack Aftermath Fix

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop positive-profile story text from being misclassified as hostile merely because it refers to clues or residue "from the attack".
- Preserve direct hostile declarations such as "I attack..." so combat escalation still remains rules-authoritative.
- Relaunch a fresh local 100-conversation run only after focused and broad verification pass.

### Steps
- [x] Stop `f100-pronounguard-w4` before pilot expansion after the contextual attack false-positive quality gate fired.
- [x] Verify the run's local server ports are no longer listening.
- [x] Inspect trajectory evidence for the positive-profile `from the attack` false hostile escalation.
- [x] Record the stop diagnosis in `manual-stop-contextual-attack-aftermath.json`.
- [x] Add a failing regression for contextual attack aftermath references that should remain in story mode.
- [x] Fix the hostile-escalation attack-token classifier so prepositional aftermath/reference phrases are contextual instead of direct attacks.
- [x] Verify focused hostile tests, full hostile suite, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch a fresh local 100-conversation run after the fix.
- [ ] Monitor the new pilot for transport errors, stale-port preflight failures, direct-player voice in `raw_text`, offstage NPC address/narration, malformed rows, structural trajectory errors, duplicate story raw text, premature route-before-acceptance, route-planned briefing fallback progression, unprompted `/check*`, `/travel route` or `/travel advance` while interrupted, and contextual attack-reference false positives.

### Verification
- [x] New contextual attack aftermath regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_hostile_escalation.HostileEscalationTests.test_contextual_attack_aftermath_reference_remains_story_mode tests.test_hostile_escalation.HostileEscalationTests.test_direct_attack_declaration_still_escalates tests.test_hostile_escalation.HostileEscalationTests.test_information_request_about_attack_patterns_remains_story_mode tests.test_hostile_escalation.HostileEscalationTests.test_question_about_goblins_attacking_remains_story_mode -v`
- [x] `python -m unittest tests.test_hostile_escalation -v`
- [x] `python -m py_compile rules_engine\hostile_escalation.py tests\test_hostile_escalation.py`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py rules_engine\hostile_escalation.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py tests\test_hostile_escalation.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.

### Review
- Root-cause evidence from stopped `f100-pronounguard-w4`: `conversation-003-positive` submitted `...Detect Magic...to see if any magical residue lingers from the attack.` in `scene-triboar-goblin-ambush`, and the server returned `Who are you trying to attack or physically force into the fight?`
- Root cause: `_attack_match_is_contextual_reference()` recognized some informational uses of `attack`, but not prepositional aftermath phrases like `from the attack`. The hostile-escalation detector therefore treated a clue/reference phrase as a direct hostile action.
- Fix: the attack-token classifier now treats `about`, `after`, `before`, `during`, `following`, `from`, `of`, and `since` plus optional `the` before `attack` as contextual references, while direct attack declarations still escalate.
- Verification: focused hostile regressions passed, full hostile suite passed 14 tests, broad dataset/story/reward/trajectory suite passed 182 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, and shared `campaigns/lmop/dm/**` stayed clean.

## 2026-05-22 - DeepSeek Dataset Pilot Failure Expansion Guard

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Stop accepting or expanding a dataset run when pilot episodes fail, especially external provider failures such as DeepSeek HTTP 402.
- Preserve the pilot artifacts and quality report so the failure is auditable.
- Do not relaunch live DeepSeek generation until the provider balance issue is resolved.

### Steps
- [x] Relaunch a fresh local run as `f100-attackaftermathguard-w4-cleanports` after the contextual attack fix.
- [x] Verify early pilot quality: first scans had no malformed rows, no trajectory errors, no positive invalid actions, and one completed `demo-complete` positive episode.
- [x] Stop the run after pilot/main expansion produced widespread `episode-error` failures.
- [x] Inspect connector/server stderr and identify DeepSeek HTTP 402 `Insufficient Balance` as the dominant connector failure, with additional memory pressure from rapid failed expansion.
- [x] Record the stopped run diagnosis in `manual-stop-pilot-failures-and-deepseek-402.json`.
- [x] Add a failing regression proving the runner expands into main episodes after a failed pilot.
- [x] Fix the runner so any failed or incomplete pilot creates final local reports and halts before main expansion.
- [x] Fix the occupied-port regression to allocate an independent free HTTP port instead of assuming `ws_port + 2` is free.
- [x] Verify focused runner tests, broader dataset/story/reward suites, compile checks, diff checks, and shared campaign cleanliness.
- [ ] Relaunch live generation only after the DeepSeek account can answer requests without HTTP 402.

### Verification
- [x] New pilot-halt regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_run_dataset_stops_after_failed_pilot_before_main_expansion -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_port_preflight_rejects_occupied_websocket_port tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_run_dataset_stops_after_failed_pilot_before_main_expansion -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py rules_engine\hostile_escalation.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py tests\test_hostile_escalation.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.
- [x] No listeners remain on the stopped run's `12000-13199` port range.

### Review
- Root-cause evidence from stopped `f100-attackaftermathguard-w4-cleanports`: `conversation-002-negative` and other connector stderr logs show `LLM request failed with HTTP 402` and response body `Insufficient Balance`. The run reached 77 episode dirs before manual process stop because the runner proceeded into main expansion even though the pilot had already failed.
- Root cause: `run_dataset()` always evaluated pilot control and then ran the remaining plan; it adjusted negative intensity but did not treat failed/incomplete pilot episodes as a hard expansion blocker.
- Fix: `run_dataset()` now calls `_pilot_blocking_issues()` after the pilot. Any failed or incomplete pilot writes local conversations, combined dataset outputs, quality reports, and a failed run report with `pilot_failed_before_expansion` or `pilot_incomplete_before_expansion`, then returns before scheduling main episodes.
- Verification: focused pilot-halt regression passed, full runner suite passed 11 tests, broad dataset/story/reward/trajectory suite passed 183 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, shared `campaigns/lmop/dm/**` stayed clean, and the stopped run's clean-port range has no remaining listeners.
- Current blocker: accepted final dataset remains `0/100`; live DeepSeek generation cannot continue until the HTTP 402 `Insufficient Balance` condition is resolved.

## 2026-05-22 - DeepSeek Dataset Provider Preflight Guard

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Recheck the DeepSeek HTTP 402 condition before launching any new generation.
- Prevent the 100-conversation runner from creating episode directories or starting servers when the configured LLM provider cannot answer a tiny preflight request.
- Preserve a local failed report explaining the provider failure for auditability.

### Steps
- [x] Re-read task lessons and current TODO state before making new runner changes.
- [x] Run a tiny live DeepSeek probe against `D:\DND-newagent\.env`.
- [x] Add a failing regression for provider preflight halting before episode execution.
- [x] Implement the runner provider preflight and failed-report path.
- [x] Verify focused runner tests, broad relevant suite, compile checks, diff checks, and shared campaign cleanliness.

### Verification
- [x] Live probe result: DeepSeek still returns HTTP 402 with response body `Insufficient Balance`.
- [x] New provider-preflight regression fails before the fix and passes after it.
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_run_dataset_preflights_provider_before_episode_execution -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_run_dataset_preflights_provider_before_episode_execution tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_run_dataset_stops_after_failed_pilot_before_main_expansion -v`
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] Real preflight-only run `f100-providerpreflight-402-check` returns `status=failed`, `episode_count=0`, and `llm_provider_preflight_failed`.
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile dm_agent\runtime.py dm_agent\client.py user-test\web_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py rules_engine\hostile_escalation.py tests\test_dm_runtime.py tests\test_llm_client.py tests\test_story_demo_party_connector.py tests\test_deepseek_100_dataset_runner.py tests\test_hostile_escalation.py training\rewards.py tests\test_rewards.py`
- [x] `git diff --check`
- [x] Shared `campaigns/lmop/dm/**` stays clean.
- [x] No listeners remain on the real preflight run's `20000-20150` or `21000-21150` port ranges.

### Review
- Root-cause evidence: both a direct minimal client request and the real runner preflight returned DeepSeek HTTP 402 with response body `Insufficient Balance`.
- Fix: `run_dataset()` now probes unique DM/player LLM env files before resolving character data or launching episodes. On failure, it writes `provider_preflight.json`, empty `conversations.jsonl`, `dataset_quality_report.json`, and `dataset_run_report.json` with `episode_count=0` and `llm_provider_preflight_failed`.
- Verification: focused preflight regression passed, full runner suite passed 12 tests, broad dataset/story/reward/trajectory suite passed 184 tests, focused `py_compile` passed, `git diff --check` reported only LF/CRLF warnings, shared `campaigns/lmop/dm/**` stayed clean, and the real failed-preflight run created no `episodes` directory and no listeners.
- Current blocker: accepted final dataset remains `0/100`; live generation cannot resume until DeepSeek stops returning HTTP 402.

## 2026-05-22 - DeepSeek Dataset Blocked Provider Recheck

### Scope
- Keep all dataset artifacts local-only and avoid commit/push/fetch/GitHub work.
- Recheck whether the external DeepSeek HTTP 402 blocker has cleared before relaunching generation.
- Do not start another 100-conversation run while the tiny provider probe still fails.

### Steps
- [x] Recheck the live DeepSeek endpoint using `D:\DND-newagent\.env`.
- [x] Verify no listeners remain on the stopped dataset ranges `12000-13199` or preflight ranges `20000-21150`.
- [x] Confirm the latest local run artifacts remain failed/preflight artifacts, not accepted final training data.
- [x] Leave the active dataset goal blocked instead of redefining completion around local scaffolding.

### Verification
- [x] Live probe result: DeepSeek still returns HTTP 402 with response body `Insufficient Balance`.
- [x] No listeners are present on `12000-13199` or `20000-21150`.

### Review
- This is the same external provider blocker observed in the stopped `f100-attackaftermathguard-w4-cleanports` run and the `f100-providerpreflight-402-check` run.
- Accepted final dataset remains `0/100`; live DeepSeek generation cannot continue until the account can answer requests again.

## 2026-05-22 - Retrieve Most Recent Local DeepSeek Dataset

### Scope
- Keep retrieval local-only and avoid commit/push/fetch/GitHub work.
- Package the most recent usable dataset artifacts regardless of quality.
- Preserve the newer preflight-only failure report so the latest-run chronology stays clear.

### Steps
- [x] Identify the strict latest run as `f100-providerpreflight-402-check`, which has `episode_count=0`.
- [x] Identify the latest non-empty episode run as `f100-attackaftermathguard-w4-cleanports`.
- [x] Create a local export manifest and README with quality/status counts.
- [x] Archive the latest non-empty run plus the preflight-only report into `runs/deepseek-100-conversation-dataset/exports/most-recent-deepseek-dataset-20260522-175922.zip`.
- [x] Clean up failed intermediate export folders created while working around Windows path-length limits.

### Verification
- [x] Archive listing has 3,770 entries and includes `EXPORT_MANIFEST.json`, `README.md`, `f100-attackaftermathguard-w4-cleanports/`, and `f100-providerpreflight-402-check/`.
- [x] Manifest confirms `accepted_final_dataset_count=0`, `episode_dir_count=77`, status counts `completed=1`, `failed=72`, `missing_result=4`, and label counts `positive=39`, `negative=38`.
- [x] Archive size is 4,022,783 bytes.

### Review
- The export is not accepted training data. It is a retrieval of the latest local artifacts regardless of quality, with the single completed episode and all failed/missing-result episode artifacts preserved for audit.

## 2026-05-22 - DM-Controlled Monster Turns

### Scope
- Keep the rules engine authoritative for combat legality, action economy, dice, HP, and turn order.
- Fix the demo/dataset controller path where DM-owned monster turns are currently auto-ended by the party connector.
- Use DM-owned slash commands for monster combat actions instead of player narration or direct state mutation.
- Keep all work local-only; do not commit, push, fetch, or contact GitHub.

### Plan
- [x] Reproduce the current connector behavior with a failing unit regression: active monster with available action should not produce `[system:dm] /endturn`.
- [x] Add a DM combat action planner that sees the DM combat snapshot and emits one legal monster slash command.
- [x] Route active DM-owned monster turns through the DM combat planner when the monster still has an action.
- [x] Preserve fast end-turn only when the active monster has already spent its action.
- [x] Make combat target summarization choose enemies relative to the active actor side so monsters target players and players target monsters.
- [x] Verify focused connector tests and compile checks.

### Verification
- [x] Focused red regression fails before the fix: missing `build_default_dm_combat_agent` / no DM monster-control path.
- [x] `python -m unittest tests.test_story_demo_party_connector.PartyConnectorTests.test_party_connector_routes_active_monster_turn_through_dm_agent -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime -v`
- [x] `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py user-test\run_deepseek_100_conversation_dataset.py`
- [x] `git diff --check -- user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py tasks\TODO.md tasks\LESSONS.md tasks\SUMMARIES.md`

### Review
- Root cause: `PartyConnector._execute_combat_cycle()` treated active actors not owned by player controllers as a connector-owned auto-pass path, submitting `/endturn <monster>` as `dm` and recording it as `[system:dm]`.
- Fix: added `DMCombatAgent`, wired `run_party_connector()` to build it by default, and routed DM-owned active monster turns through a validated DM slash-command decision when the monster has an action available. End-turn fast-path remains only for DM-owned monsters that have already spent their action.
- The combat context now computes visible enemy targets relative to the active actor side, so player turns target monsters and monster turns target players.
- Verification: focused regression passed, full connector suite passed 72 tests, broad dataset/story/reward/trajectory suite passed 185 tests, focused `py_compile` passed, and diff hygiene check reported only existing LF/CRLF warnings.

## 2026-05-22 - Accepted Dataset Pool and Stable Combat Events

### Scope
- Keep all dataset artifacts local-only and avoid commit, push, fetch, or GitHub work.
- Persist each strict-good generated conversation immediately into a durable accepted pool.
- Reduce future 100-conversation generation by the accepted positive/negative counts already in that pool.
- Fix the combat transcript issue where old magic missile damage lines are re-rendered with later HP and replayed as new events.

### Plan
- [x] Add failing accepted-pool tests for reduced remaining generation, pilot-good persistence before a failed pilot halt, and invalid completed conversations not being accepted.
- [x] Add failing combat projection/transcript tests proving old damage event HP stays immutable and recent combat chat IDs remain stable when the recent window slides.
- [x] Implement accepted-pool load/dedup/append logic and report pool progress in run outputs.
- [x] Rework combat recent-event formatting to use event-owned HP-after fields and stable event-log IDs.
- [x] Run focused tests, relevant broad suites, compile checks, and diff hygiene.

### Verification
- [x] Focused accepted-pool regressions failed before implementation and passed after implementation.
- [x] Focused combat-event regressions failed before implementation and passed after implementation.
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_encounter_session tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime tests.test_encounter_session -v`
- [x] `python -m py_compile user-test\run_deepseek_100_conversation_dataset.py user-test\web_story_demo_party_connector.py session_server\encounter_session.py session_server\encounter_projection.py session_server\web_projection.py shared_types\session_projection.py tests\test_deepseek_100_dataset_runner.py tests\test_encounter_session.py tests\test_story_demo_party_connector.py`
- [x] `git diff --check -- user-test\run_deepseek_100_conversation_dataset.py user-test\web_story_demo_party_connector.py session_server\encounter_session.py session_server\encounter_projection.py session_server\web_projection.py shared_types\session_projection.py tests\test_deepseek_100_dataset_runner.py tests\test_encounter_session.py tests\test_story_demo_party_connector.py tasks\TODO.md tasks\SUMMARIES.md tasks\LESSONS.md`
- [x] Attempted `tests.test_web_server`; it failed before exercising these changes because this worktree lacks `5etools-mirror-2.github.io\data\items-base.json`.

### Review
- Root cause for the transcript issue: encounter recent-event text formatted each `DamageAppliedEvent` with the target actor's current HP, so old magic missile damage lines changed after later damage and looked like new combat events in the transcript.
- Fix: recent-event formatting now uses `DamageAppliedEvent.target_hit_points_after` and `target_temp_hit_points_after`, and web combat chat entries use stable `encounter-event:<event-log-index>` IDs. The transcript logger now ignores replayed combat entries with already-seen stable IDs.
- Accepted-pool logic: `run_deepseek_100_conversation_dataset.py` loads `accepted_conversations.jsonl` from the output root by default, subtracts strict-good accepted positive/negative rows from the target, and appends newly strict-good rows after the pilot and main phases. Strict-good means completed `demo-complete`, successful trajectory summary, zero invalid actions, minimum transitions, and required artifacts.
- Verification: focused regressions passed, full runner suite passed 15 tests, full encounter suite passed 19 tests, full connector suite passed 72 tests, broad relevant suite passed 207 tests, focused `py_compile` passed, and diff hygiene reported only existing LF/CRLF warnings.

## 2026-05-22 - GPT Pro Review Follow-Up

### Scope
- Commit and push the local implementation branch to GitHub as requested.
- Ask ChatGPT Pro through Chrome for another code-review pass.
- Treat Pro feedback as advisory, verify it against local code, and implement only concrete, scoped correctness fixes.

### Plan
- [x] Push the current implementation commit to `newdndagents`.
- [x] Submit a concise review prompt in a fresh ChatGPT Pro conversation.
- [x] Verify Pro's findings against local code before editing.
- [x] Add red tests for accepted-pool identity tampering, transition artifact count mismatches, and unscoped combat event IDs.
- [x] Implement minimal accepted-pool artifact validation and session-scoped projected combat chat IDs.
- [x] Run focused and relevant broad verification.
- [x] Commit and push the follow-up fixes.

### Verification
- [x] Pro could not access the private GitHub commit and reviewed from the supplied summary.
- [x] Red regressions failed before implementation:
  - `python -m unittest tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_accepted_pool_rejects_tampered_acceptance_key tests.test_deepseek_100_dataset_runner.DeepSeek100DatasetRunnerTests.test_accepted_pool_rejects_transition_count_mismatching_artifact -v`
  - `python -m unittest tests.test_encounter_session.EncounterSessionTests.test_combat_chat_entry_ids_are_scoped_by_web_session -v`
- [x] The same focused regressions passed after implementation.
- [x] `python -m unittest tests.test_deepseek_100_dataset_runner -v`
- [x] `python -m unittest tests.test_encounter_session -v`
- [x] `python -m unittest tests.test_story_demo_party_connector -v`
- [x] `python -m unittest tests.test_llm_client tests.test_story_demo_party_connector tests.test_deepseek_100_dataset_runner tests.test_hostile_escalation tests.test_exploration_procedures tests.test_storytelling_session tests.test_rewards tests.test_trajectory tests.test_dm_runtime tests.test_encounter_session -v`
- [x] `python -m py_compile user-test\run_deepseek_100_conversation_dataset.py session_server\web_projection.py tests\test_deepseek_100_dataset_runner.py tests\test_encounter_session.py`
- [x] `git diff --check -- user-test\run_deepseek_100_conversation_dataset.py session_server\web_projection.py tests\test_deepseek_100_dataset_runner.py tests\test_encounter_session.py tasks\TODO.md tasks\SUMMARIES.md`

### Review
- Pro's most actionable local findings were valid: accepted-pool dedupe could trust a stored `acceptance_key`, transition artifacts were only checked for existence, and `encounter-event:<index>` was not scoped at the web chat-entry layer.
- Fix: accepted-pool validation now derives identity from artifacts instead of trusting row-provided keys, rejects tampered keys, parses required JSONL artifacts, checks non-empty transcript/raw/trajectory/transition artifacts, and verifies `transition_count` against the transitions artifact. Web combat chat IDs now include `session_id` before the stable encounter event id.
- Verification: focused regressions passed, full runner suite passed 17 tests, full encounter suite passed 20 tests, full connector suite passed 72 tests, broad relevant suite passed 210 tests, focused `py_compile` passed, and diff hygiene reported only existing LF/CRLF warnings.

## 2026-05-21 - Negative Raw Reward Totals

### Scope
- [x] Change `StoryRewardGrader.total_reward` from clamped `[0, 1]` output to the raw component sum so bad turns can be negative.
- [x] Remove the invalid/empty-action `no_invalid_narration` positive credit exposed by the mixed negative probe.
- [x] Bump `reward_version` because the numeric meaning of `total_reward` changes.
- [x] Add focused regression tests for negative invalid/stagnated rewards and no clamp behavior.
- [x] Regenerate the mixed negative probe to verify negative totals are visible in JSONL.
- [x] Run compile/unit/diff verification and update repo task docs.

### Verification Plan
- `python -m py_compile user-test\reward_grader.py tests\test_story_reward_grader.py`
- `python -m unittest tests.test_story_reward_grader -v`
- `python -m py_compile user-test\reward_grader.py user-test\story_demo_replay.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_story_reward_grader.py tests\test_story_demo_replay_scripts.py`
- `python -m unittest tests.test_story_reward_grader tests.test_story_demo_replay_scripts -v`
- regenerate `user-test/full-story-demo/logs/2026-05-21-negative-mixed-reward-probe.jsonl`
- `git diff --check`

### Review
- Updated `user-test/reward_grader.py` to `reward_version=story-reward-v4-negative-raw`.
- `total_reward` is now the raw sum of hard + quality + penalty components. There is no clamped reward field.
- Invalid or empty actions no longer receive `valid_action`, `no_invalid_narration`, scene-subgoal, duplicate/novelty, procedural, or quality rewards.
- Added regression coverage for invalid empty output returning `total_reward=-0.35`, and for a stalled narrated turn returning a negative total.
- Regenerated `user-test/full-story-demo/logs/2026-05-21-negative-mixed-reward-probe.jsonl`; it now has negative totals for turn 6 (`-0.12`) and turn 7 (`-0.35`).
- Verification passed:
  - `python -m py_compile user-test\reward_grader.py user-test\story_demo_replay.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_story_reward_grader.py tests\test_story_demo_replay_scripts.py`
  - `python -m unittest tests.test_story_reward_grader tests.test_story_demo_replay_scripts -v` passed 16 tests.

## 2026-05-20 - Evidence-Backed Story Reward Grader

### Scope
- Add a deterministic reward grader for story-demo/player-agent action records.
- Split reward components into hard objective signals and deterministic quality-rubric signals.
- Require evidence on every component and include `reward_version` in every JSONL record.
- Penalize duplicate intent and narrated speech consistently.
- Reward meaningful state progress, stage transitions, combat outcomes, and side-quest hooks only from observable state/event evidence.
- Keep gameplay progression XP/milestones separate from dataset reward scoring.

### Steps
- [x] Inspect the existing story-demo, party connector, replay, travel-hook, and progression paths before implementing.
- [x] Add the reward data model, duplicate detection, strict progress detection, narration checks, and quality rubric in a dedicated module.
- [x] Wire optional reward JSONL logging into replay/live-agent tooling without changing default gameplay behavior.
- [x] Add focused tests for reward versioning, evidence, duplicate penalties, strict progress, narrated-speech penalties, stage transitions, and side quests.
- [x] Run focused compile/unit verification and review the implementation for reward-hacking shortcuts.
- [x] Record verification results and summarize the change.

### Verification Plan
- `python -m py_compile user-test\reward_grader.py user-test\story_demo_replay.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_story_reward_grader.py tests\test_story_demo_replay_scripts.py`
- `python -m unittest tests.test_story_reward_grader tests.test_story_demo_replay_scripts -v`
- `git diff --check`

### Review
- Confirmed there was no existing reward module in the repo; the nearest paths were the full-story replay runner, live web runner, autonomous party connector, travel hooks, and the separate progression XP/milestone ledger.
- Added `user-test/reward_grader.py` with versioned `story-reward-v2` records, hard/quality/penalty components, and evidence on every component.
- Hard signals now include valid action, transcript advancement, prompt resolution, meaningful state progress, stage transition, side-quest progress, combat outcome, and no invalid narration. Meaningful progress requires state/event evidence and does not fire on transcript-only changes.
- Quality scoring is a deterministic rubric over observable context: relevance, novelty, character voice, useful question, party coordination, actionable detail, and procedural action quality.
- Duplicate-intent detection compares normalized text and topic-token overlap against recent same-scene story actions; near repeats receive an explicit penalty with prior record evidence.
- Narrated speech such as "I ask..." / "I tell..." without direct dialogue receives a consistent penalty, while direct-address dialogue such as "Gundren, ..." is accepted.
- Optional reward JSONL logging is now available in:
  - `user-test/story_demo_replay.py --reward-log-path ...`
  - `user-test/web_story_demo_live_runner.py --reward-log-path ...`
  - `user-test/web_story_demo_party_connector.py --reward-log-path ...`
- Reward-hacking review: the grader reads accepted actions plus before/after snapshots/events; it does not change story goals, XP/milestone progression, LLM prompts, or success conditions.
- Verification passed:
  - `python -m py_compile user-test\reward_grader.py user-test\story_demo_replay.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_story_reward_grader.py tests\test_story_demo_replay_scripts.py`
  - `python -m unittest tests.test_story_reward_grader tests.test_story_demo_replay_scripts -v` passed 10 tests.
  - `git diff --check` passed with only existing CRLF warnings.

## 2026-05-14 - Redo DeepSeek Run With Raw IO Transcript

### Scope
- Redo the full DeepSeek-backed web/subagent run because the previous run did not persist raw input-output transcriptions.
- Record original inputs and raw outputs for:
  - subagent consensus prompts and replies,
  - every web automation `GET`/`POST` request and raw HTTP response,
  - final state verification.
- Continue until terminal `demo-complete`.

### Steps
- [x] Capture the transcript-retention correction in `tasks/LESSONS.md`.
- [x] Start a fresh DeepSeek-backed web demo server with no `--local-llm`.
- [x] Create a repo-local JSONL raw I/O transcript artifact.
- [x] Run subagent consensus for the opening sentence and record all subagent I/O.
- [x] Drive story/travel/combat through web automation while recording every request and raw response.
- [x] Verify final `demo-complete` and transcript completeness.
- [x] Append summary.

### Verification Plan
- The server process command line contains `--env-path .env` and not `--local-llm`.
- The JSONL transcript exists under `user-test/full-story-demo/logs/`.
- The transcript contains entries for initial state, selected player input, check resolution, travel commands, combat commands, and final state.
- Final web state is `demo-complete`.

### Review
- Confirmed the previous completed DeepSeek run had no raw input-output transcript; only summaries and server startup logs existed.
- Added a correction to `tasks/LESSONS.md`: every input-output structured workflow must persist original inputs and raw outputs in a repo-local artifact unless explicitly told not to.
- Started a fresh DeepSeek-backed web server on `http://127.0.0.1:8017` / `ws://127.0.0.1:8777`, with process command line verified as `--env-path .env` and no `--local-llm`.
- Wrote the raw transcript artifact to `user-test/full-story-demo/logs/2026-05-14-deepseek-full-run-raw-io.jsonl`.
- Recorded exact subagent consensus prompt/reply records for four initial votes and four tie-break votes.
- Tie-break selected `player-2-controller` 3-1.
- Submitted selected opening text through web automation and recorded the raw HTTP request/response:
  - `Gundren, your coin is usually good, but what exactly are we guarding on the road to Phandalin?`
- Recorded all following web automation I/O: story-check `/check`, downtime/travel commands, `/travel engage`, combat state polls, monster end-turns, player casts, player end-turns, and final state.
- Final run reached `demo-complete`; final summary shows all four goblins died and the demo completed.
- Transcript verification:
  - 54 JSONL records.
  - Sequence range 1 through 54.
  - Contains phases for subagent consensus, tie-break, config/state verification, story opening, story-check, travel, combat, and final verification.
  - Contains the selected opening POST.
  - Contains final `driver_result` with `final_runtime_mode=demo-complete`.
- Server stderr log for the fresh run was empty.

## 2026-05-14 - DeepSeek Full Web Subagent Run

### Scope
- Use the DeepSeek-backed web demo server, not `--local-llm`.
- Spawn four player subagents and enforce one selected speaking player/action per round.
- Prove the DM runtime successfully completes at least one live DeepSeek-backed turn.
- Continue through the whole demo flow until terminal completion if the live DM and rules runtime permit it.

### Steps
- [x] Re-read lessons and verify `.env` DeepSeek settings.
- [x] Confirm current web server state on `http://127.0.0.1:8015`.
- [x] Spawn four persistent player subagents.
- [x] Submit the first consensus-selected story sentence and verify the DeepSeek-configured server accepted it.
- [x] Continue player consensus rounds, resolving checks/prompts through the owning player.
- [x] Drive travel and combat commands one selected player/controller action at a time.
- [x] Stop only at `demo-complete` or a hard runtime/API blocker.
- [x] Record review and append summary.

### Verification Plan
- `.env` shows DeepSeek base URL/model/API format without printing secrets.
- Web automation state remains healthy.
- A player turn returns successfully from the live server while no local transport is configured.
- Final state reaches `demo-complete`, or the exact blocker is captured with server/API output.

### Review
- Restarted the DeepSeek-backed web demo with logs on fresh ports after the prior port/session died:
  - HTTP: `http://127.0.0.1:8016`
  - WebSocket: `ws://127.0.0.1:8776`
  - Logs: `run-logs/deepseek-web/server.out.log` and `run-logs/deepseek-web/server.err.log`
- Verified the server process command line contains `--env-path .env` and does not contain `--local-llm`.
- Verified `.env` DeepSeek settings without printing the key: `OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_RESPONSES_MODEL=deepseek-v4-pro`, `OPENAI_API_FORMAT=chat_completions`.
- Spawned four player subagents and ran a consensus/tie-break opening vote. Tie-break selected `player-1-controller` 3-1.
- Submitted selected Player 1 sentence: `Gundren, it is good to see you again; before we speak of coin, tell us what worries you most about this road.`
- The DeepSeek-configured server accepted the turn and produced a Player 1 story-check prompt. The check resolved through `/check`: Charisma (Persuasion), die 1, total 1 vs DC 10 (failure).
- Drove deterministic setup and travel through the web automation API: downtime ledger attempt, marching order, watch order, travel route to Phandalin, and travel advances to `scene-triboar-goblin-ambush`.
- Engaged the ambush and completed combat through legal server commands:
  - DM passed monster turns with `/endturn`.
  - Players cast `magic-missile` at live goblin targets and ended turns as needed.
- Final state reached `demo-complete`; final summary says all four goblins died and `The demo is complete. Restart the full story demo to begin a new run.`
- Server stderr was empty after the successful run.
- Note: the first live story action produced a rules-owned story-check and deterministic social consequences rather than a long freeform narration block, but the active web server was verified as DeepSeek-configured and not local-LLM-backed.

## 2026-05-14 - Switch Web DM To DeepSeek And Clear Tmp

### Scope
- Confirm whether the running browser demo DM uses DeepSeek.
- Restart the web demo without `--local-llm` so the DM runtime uses the configured DeepSeek `.env`.
- Clear workspace temp artifacts whose names begin with `tmp` or `.tmp`.
- Verify the web automation API still responds after restart.

### Steps
- [x] Inspect `.env` and current server launch mode.
- [x] Stop the local-LLM web demo process.
- [x] Restart the web demo using `.env` DeepSeek configuration.
- [x] Verify HTTP config and automation state.
- [x] Verify temp deletion targets are inside `D:\DND-newagent`.
- [x] Delete temp files/directories.
- [x] Record review and append summary.

### Verification Plan
- `GET /config.json` returns HTTP 200 after restart.
- `GET /automation/state?controller_id=player-1-controller` returns a valid snapshot after restart.
- No top-level `tmp*` or `.tmp*` paths remain after cleanup.

### Review
- The prior web demo was launched with `--local-llm`, so its DM used the deterministic local transport rather than DeepSeek.
- `.env` already points to DeepSeek V4: `OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_RESPONSES_MODEL=deepseek-v4-pro`, and `OPENAI_API_FORMAT=chat_completions`; the API key was not printed.
- Stopped the old local-LLM web demo process.
- Restarted the web demo without `--local-llm`, so the DM runtime now uses the configured `.env` DeepSeek client.
- Port `8774` remained stuck briefly after the prior process exit, so the DeepSeek-backed server was started on fresh ports:
  - HTTP: `http://127.0.0.1:8015`
  - WebSocket: `ws://127.0.0.1:8775`
- Verified `GET http://127.0.0.1:8015/config.json` returned HTTP 200 with automation enabled.
- Verified `GET http://127.0.0.1:8015/automation/state?controller_id=player-1-controller` returned `storytelling`, `scene-waterdeep-gundren-briefing`, no prompt, and one initial chat entry.
- Verified 18 top-level temp targets were inside `D:\DND-newagent`, then removed them with PowerShell `Remove-Item -LiteralPath ... -Recurse -Force`.
- Removed all top-level paths matching `tmp*` or `.tmp*`, including `.tmp`, `.tmp-social-debug`, `.tmp-story-spell-check`, `tmp`, `tmp6vz18e_m`, `tmpfnudiv3l`, `tmpir7sxds8`, `tmpowri7twx`, `.tmp-friendly.env`, `.tmp-unfriendly.env`, and root `tmp_*` log/command files.
- Final temp verification found zero remaining top-level `tmp*` / `.tmp*` paths.

## 2026-05-14 - Web Four-Subagent Consensus Run

### Scope
- Start a fresh browser-based LMOP story demo server.
- Use the existing server-authoritative web automation API for player input instead of manual typing.
- Spawn four Codex subagents, one per player controller.
- Enforce one-speaker-at-a-time story play: before each submitted player sentence/turn, all four player agents receive the visible context and vote on who should speak next; only the selected player input is submitted, while the others listen and update notes.
- Preserve player visibility boundaries by giving each agent only its own controller snapshot plus public transcript context.

### Steps
- [x] Verify the web launcher and automation API paths.
- [x] Start a fresh web demo server and confirm HTTP plus automation state are healthy.
- [x] Spawn four player subagents with fixed controller ownership and consensus/vote instructions.
- [x] Run a short live story sequence through the web API with exactly one speaking player per round.
- [x] Capture the selected speaker, original submitted text, and server result after each round.
- [x] Add review notes with verification commands/results.
- [x] Append a concise request summary to `tasks/SUMMARIES.md`.

### Verification Plan
- HTTP GET `/config.json` returns successful web config.
- Automation GET `/automation/state?controller_id=player-1-controller` returns a valid browser snapshot.
- Each submitted player action is sent through `/automation/input` for exactly one selected controller per round.
- Final transcript/log confirms the other three players did not submit in the same round.

### Review
- Started a fresh web demo server at `http://127.0.0.1:8014` with WebSocket `ws://127.0.0.1:8774`, automation enabled, and `--local-llm` for deterministic local DM responses.
- Spawned four Codex subagents, one per player controller, with fixed controller ownership and a one-speaker consensus protocol.
- Round 1 initially tied 1-1-1-1, so a tie-break vote was run before any web input. The tie-break selected `player-3-controller` 3-1.
- Submitted exactly one Round 1 player sentence through `/automation/input`: `I want Gundren's rate, the wagon ledger, route details, expected trouble, and whether Sildar is riding with us before we agree to guard anything north.`
- Resolved the resulting Player 3 story-check through `/check`: Charisma (Persuasion), die 1, total 1 vs DC 11 (failure).
- Round 2 selected `player-1-controller` 3-1 after all agents consumed the public check result and listening notes.
- Submitted exactly one Round 2 player sentence through `/automation/input`: `Gundren, forgive our sharpness; I trust you, and if you need the wagon guarded to Phandalin under the stated terms, I am willing to stand for the job.`
- Resolved the resulting Player 1 story-check through `/check`: Charisma (Persuasion), die 5, total 5 vs DC 9 (failure).
- Captured run notes in `tmp/web-four-subagent-run/transcript.md`.
- Verification passed:
  - `GET http://127.0.0.1:8014/config.json` returned HTTP 200 with automation enabled.
  - `GET http://127.0.0.1:8014/automation/state?controller_id=player-1-controller` returned a valid `storytelling` snapshot at `scene-waterdeep-gundren-briefing`.
  - Final automation snapshots had no pending prompt.
  - Server stderr log was empty.
- Elegance check: used the existing web automation API and Codex subagents as the deliberation layer, avoiding repo runtime code changes for an operational run.

## 2026-05-14 - Gundren And Sildar Roleplay Setup

### Scope
- Make the DM storytelling prompt receive explicit NPC roleplay facts instead of relying only on raw campaign prose.
- Establish Gundren as the party's previous employer who is hiring them again for a new Phandalin mission.
- Establish Sildar as someone who does not personally know the party before the Waterdeep briefing.
- Ensure Gundren and Sildar leave the party after the opening briefing and are not treated as present once the party starts the road journey.
- Preserve the DM-vs-rules boundary: the DM may narrate and ask checks, while travel visibility and social relationship state remain deterministic backend state.

### Steps
- [x] Add pure functions that build a structured NPC roleplay brief for DM prompts from selected campaign documents.
- [x] Wire the roleplay brief into story-turn and check-outcome prompt payloads with instructions that visible NPCs are the only NPCs available for direct dialogue.
- [x] Update LMOP Gundren/Sildar campaign content and initial influence/social state to encode prior-employer vs stranger relationships.
- [x] Add travel hook metadata and session handling so the High Road transition clears Gundren/Sildar from visible NPCs.
- [x] Add focused tests for prompt payloads, initial social relationship state, memory/playbook persistence, and travel visibility.
- [x] Run focused verification and record results.

### Verification Plan
- `python -m py_compile dm_agent\runtime.py shared_types\travel.py rules_engine\hexmap_loader.py rules_engine\exploration.py session_server\storytelling_session.py tests\test_dm_runtime.py tests\test_storytelling_session.py tests\test_social_consequences.py`
- `python -m unittest tests.test_dm_runtime tests.test_storytelling_session tests.test_social_consequences tests.test_exploration_procedures -v`
- `git diff --check`

### Review
- Added `NpcRoleplayBrief` plus `build_npc_roleplay_brief(...)` in the DM runtime. Story-turn and check-outcome prompts now include `npc_roleplay_brief` and explicitly say direct NPC dialogue may only come from `visible_npc_ids`.
- Updated LMOP Gundren/Sildar authored content and generated playbook support so Gundren is a familiar previous employer hiring the party again, while Sildar is cooperative but does not know them personally.
- Added deterministic initial influence/social state for Gundren's prior-employer trust: friendly, trust 5, willing. Sildar remains cooperative with trust 0.
- Added `suggested_visible_npc_ids` to travel hooks and wired the High Road transition to set an explicit empty visible-NPC list, keeping Gundren/Sildar offstage once the journey starts.
- Reverted unrelated test-generated campaign memory snapshot churn and kept only the intended playbook/content/runtime/test changes.
- Verification passed:
  - `python -m py_compile dm_agent\runtime.py dm_agent\__init__.py dm_agent\memory.py shared_types\travel.py shared_types\exploration.py rules_engine\hexmap_loader.py rules_engine\exploration.py session_server\storytelling_session.py tests\test_dm_runtime.py tests\test_storytelling_session.py tests\test_social_consequences.py tests\test_exploration_procedures.py tests\test_travel_system.py`
  - `python -m unittest tests.test_dm_runtime tests.test_storytelling_session tests.test_social_consequences tests.test_exploration_procedures tests.test_travel_system -v` passed 74 tests.
  - `python -m py_compile tests\test_dm_runtime.py` passed after removing a trailing-space warning.
  - `git diff --check` passed with only existing line-ending warnings.

## 2026-05-21 - Scene Subgoal Rewards And Stagnation Penalty

### Scope
- [x] Answer whether reward is LLM-scored or deterministic.
- [x] Add deterministic scene subgoal reward logic for LMOP scenes, starting with Gundren briefing information/payment/road-prep goals.
- [x] Add scene-examination and scene-push subgoals for travel/ambush-oriented scenes without changing the model prompt or shortcutting the goal.
- [x] Add a history-aware stagnation penalty when same-scene story turns keep happening without subgoal completion, meaningful progress, stage transition, prompt resolution, or combat outcome.
- [x] Store evidence for subgoal matches and stagnation state in each reward component.
- [x] Add focused tests that prove subgoal reward, no false progress, and stagnation penalty behavior.
- [x] Run compile/unit verification and record review notes.

### Verification Plan
- `python -m py_compile user-test\reward_grader.py tests\test_story_reward_grader.py`
- `python -m unittest tests.test_story_reward_grader -v`
- `git diff --check`

### Review
- Confirmed rewards are deterministic code, not LLM-scored. The LLM only emits the candidate player action.
- Versioned the reward function to `story-reward-v3-scene-goals` because scene-objective and stagnation scoring change the meaning of numeric rewards.
- Added explicit scene subgoals for Gundren briefing, High Road travel, and the Triboar goblin ambush. Gundren briefing now rewards natural payment negotiation, cargo/delivery questions, road-danger questions, urgency/secrecy probes, scene examination, and travel commitment.
- Added `scene_subgoal_progress` evidence with matched subgoal ids, descriptions, matched terms, value, and cap.
- Added `stagnation_penalty` after three same-scene storytelling turns without scene subgoal progress, prompt resolution, meaningful state progress, stage transition, side quest progress, or combat outcome.
- Tightened subgoal evidence after live dataset verification showed `extra supplies` could incorrectly satisfy `gundren_payment_terms`; payment now requires actual payment/terms evidence, and road danger requires danger/watch/threat evidence instead of the word `road` alone.
- Generated the full DeepSeek-backed reward dataset at `user-test/full-story-demo/logs/2026-05-21-live-reward-scene-advance-dataset.jsonl`, with summary at `user-test/full-story-demo/logs/2026-05-21-live-reward-scene-advance-summary.json`.
- Full dataset result: 9 LLM candidates, 3 selected reward-max turns, 2 scene advancements, final scene `scene-triboar-goblin-ambush`, and every selected turn either advanced a scene or completed new scene subgoals.
- Verification passed:
  - `python -m py_compile user-test\reward_grader.py user-test\story_demo_replay.py user-test\web_story_demo_live_runner.py user-test\web_story_demo_party_connector.py tests\test_story_reward_grader.py tests\test_story_demo_replay_scripts.py`
  - `python -m unittest tests.test_story_reward_grader tests.test_story_demo_replay_scripts -v` passed 15 tests.
  - `git diff --check` passed with only existing CRLF warnings.

## 2026-05-21 - Live DeepSeek Reward Probe Retry

### Scope
- [x] Retry the actual configured DeepSeek call with full network access.
- [x] Separate raw client/API behavior from the fuller party-player prompt path.
- [x] Persist the live LLM output and reward record as durable JSONL evidence.
- [x] Verify the JSONL artifact parses with normal UTF-8 tooling.

### Review
- Minimal synthetic probe reached `https://api.deepseek.com` with `OPENAI_API_FORMAT=chat_completions`, model `deepseek-v4-pro`, and a larger `max_output_tokens=1200` budget, then returned parseable JSON.
- Full `PlayerAgent.plan_action(...)` probe reached the same DeepSeek endpoint and returned a structured player decision for `player-4-controller`.
- The reward grader produced `reward_version=story-reward-v2`, total reward `0.19`, and correctly applied `narrated_speech_penalty` for the model output `I ask Gundren...`.
- Durable evidence was written to `user-test/full-story-demo/logs/live-deepseek-reward-probe.jsonl` and verified as 4 UTF-8 JSON records.

## 2026-05-21 - Superpowers Skills For Codex

### Scope
- Install or scaffold the external Superpowers skill bundle so this repository can use the skills through Codex native skill discovery.
- Keep the D&D runtime untouched unless the skill installation requires repo-local wiring.
- Use the official `obra/superpowers` source and record the exact local shape chosen.
- Preserve existing repo-local skills under `.agents/skills/`.

### Steps
- [x] Confirm current repo/global skill discovery state.
- [x] Fetch or install the Superpowers skill files from the official source.
- [x] Verify the expected `SKILL.md` files are present and discoverable from the chosen path.
- [x] Record review notes, verification commands, and summary.

### Verification Plan
- Inspect `.agents/skills` and any global Codex skill target used.
- Count Superpowers `SKILL.md` files and read key frontmatter.
- Run a lightweight structural check for required `name` and `description` frontmatter.
- Run `git diff --check`.

### Review
- No existing Superpowers install was present at `~/.codex/superpowers`, `~/.agents/skills/superpowers`, `~/.codex/skills/superpowers`, or `.agents/skills/superpowers`.
- Verified the official repository HEAD with `git ls-remote https://github.com/obra/superpowers.git HEAD`, then installed from commit `f2cbfbefebbfef77321e4c9abc9e949826bea9d7`.
- Copied the upstream `skills/` directory into repo-local `.agents/skills/superpowers/`, preserving the existing `.agents/skills/implement-*` skills.
- Added `.agents/skills/superpowers/SOURCE.md` with the source repository, commit, installed content, and install date.
- Removed the temporary clone after verifying it resolved under this repo's `.agents` directory.
- Verification passed:
  - `Get-ChildItem .agents/skills/superpowers -Recurse -Filter SKILL.md | Measure-Object` found 14 skills.
  - The installed skills are `brainstorming`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `using-superpowers`, `verification-before-completion`, `writing-plans`, and `writing-skills`.
  - A line-based structural check confirmed every installed `SKILL.md` has opening/closing frontmatter plus `name` and `description`.
  - `git diff --check` exited 0, with only pre-existing CRLF normalization warnings from other dirty files.
- Codex may need a restart or new session before the newly added repo-local skills appear in the available skill list.

## 2026-05-21 - Ten-Turn DeepSeek Reward Dataset

### Scope
- Generate a 10-turn live dataset through the existing LMOP story demo and DeepSeek-backed player-agent connector.
- Preserve raw DeepSeek interaction records, parsed player decisions, visible transcript, and deterministic reward JSONL as repo-local artifacts.
- Do not expose `.env` secrets in command output or summaries.
- Keep reward scoring deterministic and separate from model generation.

### Steps
- [x] Add optional raw DeepSeek interaction logging to `user-test/web_story_demo_party_connector.py`.
- [x] Verify the logger with focused tests and compile checks.
- [x] Start the automation server with the real configured DeepSeek runtime.
- [x] Run the party connector for exactly 10 actions with transcript, reward, and interaction logs.
- [x] Summarize the result, reward totals/components, and artifact paths.

### Verification Plan
- `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
- `python -m unittest tests.test_story_demo_party_connector -v`
- Parse the generated JSONL artifacts and confirm 10 interaction records and 10 reward records.
- `git diff --check`

### Review
- Added an opt-in `PartyInteractionLogger` to `user-test/web_story_demo_party_connector.py`, plus `--interaction-log-path`, so live runs can persist raw DeepSeek request payloads, raw model outputs, parsed decisions, accepted/error status, and reward records without changing default connector behavior.
- Fixed direct script execution by adding the repo root to `sys.path` before importing `dm_agent`.
- Generated the live dataset through `python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8010 --ws-port 8777 --env-path .env` and the real DeepSeek-backed connector with `--max-actions 10`.
- Connector result: 10 turns, 10 commands, 0 prompt responses, 0 retries, 10 reward records, final mode `storytelling`, final scene `scene-waterdeep-gundren-briefing`.
- Dataset artifacts:
  - `user-test/full-story-demo/logs/2026-05-21-ten-turn-deepseek-interactions.jsonl`
  - `user-test/full-story-demo/logs/2026-05-21-ten-turn-deepseek-rewards.jsonl`
  - `user-test/full-story-demo/logs/2026-05-21-ten-turn-deepseek-transcript.md`
  - `user-test/full-story-demo/logs/2026-05-21-ten-turn-deepseek-summary.json`
  - `user-test/full-story-demo/logs/2026-05-21-ten-turn-deepseek-server.out.log`
  - `user-test/full-story-demo/logs/2026-05-21-ten-turn-deepseek-server.err.log`
- Reward summary: total `4.77`, average `0.477`, hard total `4.33`, quality total `1.6`, penalty total `-1.0`, reward version `story-reward-v4-negative-raw`.
- After turn 10, the live server had no active combat actor and no pending prompt. The last connector action was `player-2-controller`; continuing the same connector rotation would make the next story turn `player-3-controller`.
- Verification passed:
  - `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
  - `python -m unittest tests.test_story_demo_party_connector -v` passed 5 tests.
  - Parsed generated JSONL and confirmed 10 interaction records, 10 reward records, and all accepted.
  - `git diff --check` exited 0 with only pre-existing CRLF normalization warnings.
- Stopped the temporary server process after artifact generation.

## 2026-05-21 - Speaker Voting And Direct Dialogue

### Scope
- Replace simple round-robin autonomous story speaking with a speaker-vote phase where the party chooses the best-positioned controller for the moment.
- Include per-character state/status, skill/resource signals, persona focus, recent checks, recent chat, and recent party actions in the voting context.
- Keep prompts/checks authoritative: if the server has a pending prompt, the owning player answers it directly instead of calling a vote.
- Force spoken social declarations away from narrated phrasing like `I ask Gundren...` and toward direct in-character words like `Gundren, ...`.
- Preserve raw input/output logging for both speaker votes and final player actions.

### Steps
- [x] Add speaker-vote dataclasses, parser, prompts, deterministic candidate summaries, and vote logging.
- [x] Wire story-mode controller selection through vote tallying with deterministic tie-breaking.
- [x] Add direct-dialogue validation and retry guidance for narrated speech.
- [x] Update focused connector tests for voting, vote logging, and direct-speech retry behavior.
- [x] Run compile/unit verification and record review notes.

### Verification Plan
- `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
- `python -m unittest tests.test_story_demo_party_connector -v`
- `git diff --check`

### Review
- Added party speaker voting to `user-test/web_story_demo_party_connector.py`. Story turns now collect one JSON vote from each currently available storytelling controller, using candidate summaries built from visible character data, status, skills/abilities, resources, persona focus, recent checks/chat, and recent party actions.
- Voting is only used for autonomous story turns. Pending prompts still go directly to the prompt owner, and combat turns still follow the active actor from the authoritative server state.
- Speaker selection is deterministic after votes: highest vote count wins, then candidate advantage score, then longer time since last story action, then stable controller order.
- Added raw interaction logging for vote records with `record_type=deepseek_party_speaker_vote`, preserving the vote request payload, raw output, parsed vote, accepted/error status, and candidate ids alongside the existing turn-attempt logging.
- Tightened story-speech prompting and validation so narrated speech such as `I ask Gundren...` is retried into direct in-character words such as `Gundren, ...`. Contractions like `it's` no longer count as quoted dialogue.
- Added CLI support for `--disable-speaker-voting`; voting is enabled by default for the party connector.
- Updated focused connector tests for vote selection/logging, raw interaction logging, legacy no-vote paths, prompt-owner bypass, duplicate-topic retry, transcript output, and narrated-speech retry.
- Elegance check: kept the change scoped to the user-test autonomous party connector rather than moving demo orchestration into the core DM/rules runtime, preserving the DM-vs-simulator authority boundary.
- Verification passed:
  - `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py`
  - `python -m unittest tests.test_story_demo_party_connector -v` passed 7 tests.
  - `git diff --check` exited 0 with only pre-existing CRLF normalization warnings.

## 2026-06-02 - Pull Current Branch

### Scope
- Pull the most recent change from the current tracked branch.
- Preserve existing local edits and untracked files.
- Resolve merge conflicts if the incoming branch overlaps local work.
- Summarize the fetched/merged changes with commit and file evidence.

### Steps
- [x] Review repo guidance and current lessons.
- [x] Inspect current branch, upstream, and dirty worktree.
- [x] Fetch the upstream branch and compare incoming file changes.
- [x] Pull or merge the upstream branch, resolving conflicts if needed.
- [x] Verify final git state and summarize what changed.

### Verification Plan
- `git status --short --branch`
- `git log --oneline --decorate --max-count=8`
- `git diff --name-status HEAD@{1}..HEAD` when HEAD moves.

### Review
- Fetched `origin` and `elijah`; current branch `dnd-newagent-migration` was 76 commits behind `elijah/dnd-newagent-migration`.
- Stashed tracked local edits as `codex-before-pull-2026-06-02`, fast-forwarded `ae0170d..06fca35`, then reapplied the stash.
- Resolved conflicts in `tasks/LESSONS.md`, `tasks/SUMMARIES.md`, `tasks/TODO.md`, `tests/test_story_demo_party_connector.py`, and `user-test/web_story_demo_party_connector.py`.
- Kept upstream connector changes as the base, preserved direct script import bootstrapping, restored optional reward JSONL logging, and added a connector regression for reward records.
- Preserved upstream task history and appended selected stashed local task sections rather than dropping either side.
- Verification passed:
  - `python -m py_compile user-test\web_story_demo_party_connector.py tests\test_story_demo_party_connector.py user-test\reward_grader.py tests\test_story_reward_grader.py`
  - `python -m unittest tests.test_story_reward_grader -v` passed 11 tests.
  - `python -m unittest tests.test_story_demo_party_connector -v` passed 74 tests.
  - `git diff --check -- tasks\LESSONS.md tasks\SUMMARIES.md tasks\TODO.md tests\test_story_demo_party_connector.py user-test\web_story_demo_party_connector.py` exited 0 with only existing LF/CRLF warnings.

## 2026-06-02 - Extend LMOP To Cragmaw Hideout

### Scope
- Extend the playable story after the goblin ambush toward Cragmaw Hideout.
- Block Phandalin content for this slice with explicit story reasons instead of advancing there.
- Branch party defeat into either Cragmaw capture or a true game-end outcome based on authored rescue conditions.
- Add Klarg/Yeemik/Sildar hideout social context and negotiation gating.
- Add DM-only player-condition context filtered by monster Intelligence and Wisdom.
- Start the manual web server at the Cragmaw slice after verification.

### Steps
- [x] Add failing tests for post-ambush Phandalin blocking and Cragmaw routing.
- [x] Add failing tests for all-player-unconscious capture vs game-end behavior.
- [x] Add failing tests for Yeemik bargaining prerequisites and weak-party refusal.
- [x] Add failing tests for monster-filtered party condition context in DM prompts.
- [x] Add Cragmaw Hideout campaign scene/location/NPC content grounded in the local 5e.tools mirror.
- [x] Implement story-session gates, defeat outcome monitor, and DM condition context.
- [x] Add a manual-server start mode for the Cragmaw slice.
- [x] Verify party connector normalization remains compatible with the post-ambush Cragmaw route.
- [x] Run focused unit tests and compile checks.
- [x] Start the manual web server at Cragmaw and record the local URL.

### Verification Plan
- `python -m unittest tests.test_storytelling_session -v`
- `python -m unittest tests.test_full_story_demo_session -v`
- `python -m unittest tests.test_story_demo_party_connector -v`
- `python -m py_compile session_server\storytelling_session.py session_server\bootstrap.py user-test\story_demo_system_server.py user-test\web_story_demo_server.py user-test\web_story_demo_party_connector.py tests\test_storytelling_session.py tests\test_full_story_demo_session.py tests\test_story_demo_party_connector.py`
- `git diff --check`

### Review
- Added post-ambush Cragmaw gating: after the ambush, `/travel route phandalin` and natural-language Phandalin attempts raise a typed validation error that points back to the Cragmaw trail.
- Added combat-completion story outcomes: player victory continues to `scene-02-trail-aftermath`, monster victory with the capture condition moves to `scene-cragmaw-kennel-prison`, and all-player-unconscious with no rescue condition emits `StoryGameEndedEvent` and completes the demo as a defeat.
- Added DM-only context notes for the Klarg/Yeemik rivalry gate, weak-party bargain refusal, and monster-filtered party condition awareness based on observer Intelligence and Wisdom.
- Added Cragmaw content for the cave mouth, wolf kennel/capture branch, goblin den, Klarg cave, Klarg, Yeemik, generic Cragmaw goblins, kennel wolves, and Ripper. Updated Sildar and the hideout/trail aftermath docs for the capture/rescue flow.
- Added `story_start='cragmaw'` plus `--story-start cragmaw` for the manual and web demo servers.
- Party connector regression suite passed without connector code changes; existing normalization remained compatible once the server exposes the Cragmaw route and blocks Phandalin only in the post-ambush slice.
- Verification passed:
  - `python -m unittest tests.test_storytelling_session -v` passed 22 tests.
  - `python -m unittest tests.test_full_story_demo_session -v` passed 8 tests.
  - `python -m unittest tests.test_story_demo_party_connector -v` passed 74 tests.
  - `python -m py_compile session_server\storytelling_session.py session_server\bootstrap.py user-test\story_demo_system_server.py user-test\web_story_demo_server.py user-test\story_demo_system_server.py user-test\web_story_demo_party_connector.py tests\test_storytelling_session.py tests\test_full_story_demo_session.py tests\test_story_demo_party_connector.py shared_types\storytelling.py shared_types\encounter_events.py dm_agent\runtime.py`
  - `git diff --check` exited 0 with only Windows LF/CRLF normalization warnings.
- Manual server running:
  - HTTP: `http://127.0.0.1:8000`
  - WebSocket: `ws://127.0.0.1:8767`
  - PID: `33320`
  - Verified automation state: `storytelling`, `scene-cragmaw-cave-mouth`, `cragmaw-hideout`.

## 2026-06-02 - Clear DM Thinking Placeholder

### Scope
- Fix the browser chat visual bug where the local `DM is thinking...` placeholder remains after the DM response appears.
- Keep ordinary system messages persistent.
- Preserve existing transient `thinking` behavior for streamed reasoning.

### Steps
- [x] Add a failing frontend chat-state regression for `DM is thinking...` emitted as a system/info entry.
- [x] Implement the minimal transient-placeholder cleanup in the chat feed state.
- [x] Verify frontend tests and relevant compile/check commands.
- [x] Restart the manual Cragmaw web server so the running UI uses the fix.

### Verification Plan
- `python -m unittest tests.test_web_frontend_chat -v`
- `python -m py_compile tests\test_web_frontend_chat.py`
- `git diff --check -- web_frontend\chat_state.js tests\test_web_frontend_chat.py tasks\TODO.md tasks\SUMMARIES.md tasks\LESSONS.md`

### Review
- Root cause: the browser receives `DM is thinking...` as an `info` event and stores it as a local `system` chat entry. Existing cleanup only expired entries categorized as `thinking`, so the placeholder survived after authoritative DM chat advanced.
- Added a regression in `tests/test_web_frontend_chat.py` proving a local system/info `DM is thinking...` placeholder expires when authoritative chat advances, while ordinary system entries remain.
- Updated `web_frontend/chat_state.js` so transient thinking entries include both category `thinking` and the exact system placeholder text `DM is thinking...`.
- Restarted the Cragmaw manual web server on `http://127.0.0.1:8000` / `ws://127.0.0.1:8767`; new PID `48524`.
- Verification passed:
  - `python -m unittest tests.test_web_frontend_chat -v` passed 3 tests.
  - `python -m py_compile tests\test_web_frontend_chat.py`
  - `git diff --check -- web_frontend\chat_state.js tests\test_web_frontend_chat.py tasks\TODO.md tasks\SUMMARIES.md tasks\LESSONS.md` exited 0 with only LF/CRLF warnings.

## 2026-06-02 - Cragmaw Hideout Map Vision Demo

### Scope
- Use the Cragmaw Hideout player-version map metadata from the verified local 5e.tools mirror.
- Align the browser square grid to the Cragmaw Hideout player map image.
- Add a 2D grid vision model with day/night default radius and wall/LOS blocking.
- Keep height/elevation out of this map slice.
- Provide a manual browser demo where the player can move with up/down/left/right controls and watch vision update.

### Steps
- [x] Add failing tests for Cragmaw Hideout map metadata, grid size, image alignment, and no-height terrain.
- [x] Add failing tests for day/night grid vision and wall-blocked cells.
- [x] Add failing tests for web projection of background image metadata and per-cell visibility.
- [x] Author the Cragmaw Hideout battlefield asset from the local 5e.tools player-version map metadata.
- [x] Implement the 2D grid vision calculator in rules/runtime code.
- [x] Expose background image and visibility through web map projection types.
- [x] Update the browser map renderer with background-image grid alignment, fogged cells, wall cells, and arrow movement controls.
- [x] Add a manual Cragmaw map demo server.
- [x] Start the manual Cragmaw map demo server and run a smoke check.
- [x] Run focused unit tests, compile checks, and frontend/static checks.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_battlefield_map -v`
- `python -m py_compile rules_engine\battlefield_loader.py encounter_runtime\vision.py session_server\bootstrap.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- `git diff --check -- data\maps\cragmaw_hideout_map.json shared_types\battlefield.py shared_types\web_ui.py rules_engine\battlefield_loader.py encounter_runtime\vision.py session_server\bootstrap.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py web_frontend\app.js web_frontend\styles.css tests\test_cragmaw_hideout_map.py tasks\TODO.md tasks\LESSONS.md tasks\SUMMARIES.md`

### Review
- Source map: verified the local 5e.tools mirror player map metadata for `adventure/LMoP/Cragmaw Hideout (Player).webp`: 4500 x 3136 image, 150 px square grid, offset -4/-7. Copied the player map into `web_frontend/assets/maps/cragmaw-hideout-player.webp`.
- Added `cragmaw_hideout_player_v1` as a flat 30 x 21 battlefield asset with all elevations at 0, cave-floor cells from the player map regions, and default rock-wall cells that block movement, LOS, and LOE.
- Added `encounter_runtime.vision` for day/night square-grid visibility. Day defaults to 120 ft, night defaults to 30 ft, and wall cells can be seen while cells behind them are blocked by LOS.
- Extended web projection types and map projection so player views receive background image metadata, `vision_time_of_day`, vision actor ids, and per-cell `visible` flags. Non-DM token/cell projection is clipped by the rules-side visibility mask.
- Updated the browser battlefield renderer to scale the background from the map's grid-size metadata, apply grid-offset alignment, fog unseen cells, hide elevation text for image maps, and expose up/left/down/right controls plus keyboard arrow movement through typed `move_proposal`.
- Added `user-test/cragmaw_map_demo_server.py` and started it with the local 5e mirror on:
  - HTTP: `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1`
  - WebSocket: `ws://127.0.0.1:8768`
  - PID: `26216`
- Smoke checks:
  - Automation state returned `combat`, map id `cragmaw_hideout_player_v1`, background `assets/maps/cragmaw-hideout-player.webp`, 630 total cells, and finite player vision.
  - Static map asset returned HTTP 200 with content length 2008220.
  - `/move player-1 14 17` moved the token and recomputed visibility.
  - Browser DOM showed `map-grid has-background`, image URL loaded, background size `1260px 878.08px`, background position `1.12px 1.96px`, 630 cells, enabled movement controls, and token movement from `(14,17,0)` to `(14,16,0)` after clicking Move up.
  - Browser screenshot capture timed out twice in the browser tool, but DOM/API and UI-click checks passed.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 4 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m py_compile rules_engine\battlefield_loader.py encounter_runtime\vision.py session_server\bootstrap.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`
  - `git diff --check -- data\maps\cragmaw_hideout_map.json shared_types\battlefield.py shared_types\web_ui.py rules_engine\battlefield_loader.py encounter_runtime\vision.py session_server\bootstrap.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py web_frontend\app.js web_frontend\styles.css tests\test_cragmaw_hideout_map.py tasks\TODO.md tasks\LESSONS.md tasks\SUMMARIES.md` exited 0 with only LF/CRLF warnings.

## 2026-06-02 - Normal And Night Vision Fog

### Scope
- Make map fog visibility actor-aware instead of only map-radius-aware.
- Treat normal vision as sight into non-dark, non-heavily-obscured cells within the map's normal vision radius and LOS.
- Treat night vision as actor darkvision into dark cells within the actor's darkvision radius and LOS.
- Make dynamic bright/dim light from active effects affect map fog.
- Make Fog Cloud and created physical objects affect both map fog and visible overlays correctly.
- Preserve server-authoritative projection: the browser receives visibility/mode data but never computes canonical visibility.
- Keep the Cragmaw map flat; do not add height/elevation behavior.

### Steps
- [x] Add failing tests for normal sight vs night vision on dark Cragmaw cells.
- [x] Add failing tests for projected web cell `vision_mode` values.
- [x] Add failing tests for bright/dim light effects changing map fog.
- [x] Add failing tests for Fog Cloud cells and visible Fog Cloud overlays.
- [x] Add failing tests for created physical objects such as crates blocking map vision.
- [x] Implement actor-aware grid vision modes using the existing combat visibility/light helpers.
- [x] Expose `vision_mode` through web map cells and apply browser classes for normal/night/fog.
- [x] Adjust persistent effect/object projection so seen effects remain visible without revealing obscured contents.
- [x] Restart or smoke-check the manual Cragmaw map demo.
- [x] Run focused unit tests, compile checks, JS syntax check, and targeted diff check.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m unittest tests.xphb_level1_spells.fog_cloud.test_fog_cloud tests.xphb_cantrips.light.test_light -v`
- `python -m py_compile encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py shared_types\web_ui.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py tests\test_visibility_system.py`
- `node --check web_frontend\app.js`
- `git diff --check -- encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py shared_types\web_ui.py user-test\cragmaw_map_demo_server.py web_frontend\app.js web_frontend\styles.css tests\test_cragmaw_hideout_map.py tests\test_visibility_system.py tasks\TODO.md tasks\SUMMARIES.md tasks\LESSONS.md`

### Review
- Added actor-aware grid vision modes. Cells are now projected as `normal`, `night`, or `none`; normal vision is available for bright/dim/no-light-block cells, night vision is available through actor darkvision in darkness, and heavy obscurement remains opaque.
- Reused the existing visibility helpers for dynamic lighting and obscurement so XPHB Light, Dancing Lights-style dim light, Fog Cloud, darkvision, blindsight/truesight, and runtime battlefield blockers feed the same map fog path.
- Updated web map projection and frontend rendering to include `vision_mode`, `vision-night` styling, unseen cells, and visibility-aware feature projection. Created physical blockers can be visible in their own square while still hiding cells behind them.
- Added regression coverage for Light turning dark cells into normal vision, Fog Cloud hiding cells while leaving the effect overlay available, a created wooden crate blocking LOS, and the manual fixture that combines Light, Fog Cloud, and a crate.
- Manual visual/projection smoke: ran the fixture server in parallel with headless Chrome/automation. The live projection reported `normal=48`, `unseen=582`, `crate=1`, `dmFog=1`, `cell13=normal/True`, and `cell16=none/False`; Chrome connected to the local player portal and wrote `tasks/cragmaw-map-vision-fixture.png`. Headless Chrome screenshot timing remained unreliable for the async map paint, so the authoritative visual evidence is the live projection plus the saved browser artifact.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 10 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m unittest tests.xphb_level1_spells.fog_cloud.test_fog_cloud -v` passed 6 tests.
  - `python -m unittest tests.xphb_cantrips.light.test_light -v` passed 3 tests.
  - `python -m py_compile encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py shared_types\web_ui.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py tests\test_visibility_system.py`
  - `node --check web_frontend\app.js`
  - `git diff --check -- encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py shared_types\web_ui.py user-test\cragmaw_map_demo_server.py web_frontend\app.js web_frontend\styles.css tests\test_cragmaw_hideout_map.py tests\test_visibility_system.py tasks\TODO.md tasks\SUMMARIES.md tasks\LESSONS.md` exited 0 with only LF/CRLF warnings.

## 2026-06-03 - Deploy Cragmaw Vision Server

### Scope
- Deploy the local Cragmaw Hideout map vision server for player visual inspection.
- Use the existing Cragmaw player map with authored walls as the base.
- Show server-authoritative player vision visually in the browser.
- Explain how to visually test bright light, dim light, darkness/darkvision, walls, Fog Cloud, and physical blockers.
- Record API/browser smoke evidence and keep the running local URL available.

### Steps
- [x] Run focused Cragmaw vision regression tests.
- [x] Run compile and frontend syntax checks for the demo/server/map projection path.
- [x] Start `user-test/cragmaw_map_demo_server.py` with the `light-fog-crate` fixture.
- [x] Fix the fixture/projection so web cells expose effective bright, dim, darkness, and Fog Cloud heavy obscurement.
- [x] Verify the automation API reports the Cragmaw map, player view, normal/night/none vision modes, lighting modes, and map features.
- [x] Open the player portal in the browser and verify the visual map renders with fog and movement controls.
- [x] Document the manual visual test procedure and server URL.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m unittest tests.xphb_level1_spells.fog_cloud.test_fog_cloud tests.xphb_cantrips.light.test_light -v`
- `python -m py_compile encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py shared_types\web_ui.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py tests\test_visibility_system.py`
- `node --check web_frontend\app.js`
- HTTP/API smoke against `/config.json`, `/automation/state`, and the static Cragmaw map asset.
- Browser visual smoke through the player controller portal.

### Review
- Started and restarted the Cragmaw map demo server with `--vision-fixture light-fog-crate` on:
  - HTTP/player portal: `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1`
  - WebSocket: `ws://127.0.0.1:8768`
  - PID: `5084`
- Found and fixed a manual-fixture/projection issue before final visual verification: the browser projection now uses effective `position_light_level` and `position_obscurement`, and the fixture darkens traversable floor after active Light/Fog effects exist so bright, dim, and darkness are all represented by server data.
- Live API smoke passed: map `cragmaw_hideout_player_v1`, background `assets/maps/cragmaw-hideout-player.webp`, 630 cells, 48 player-visible cells, 582 unseen cells, 50 dim-light cells, 106 darkness cells, Light plus crate visible to the player, Fog Cloud visible to the DM, and the map asset returned HTTP 200 with 2,008,220 bytes.
- Representative live cells: `(13,17)` is `bright/normal/visible`, `(19,17)` is `dim/none/not-visible` behind blockers, `(24,16)` is `darkness/none/not-visible`, and DM cell `(20,19)` is `heavy/visible` for Fog Cloud.
- Browser visual smoke passed in the in-app browser: connected as Player 1, rendered `.map-grid.has-background`, 630 cells, 48 visible, 582 unseen, 50 dim cells, 106 darkness cells, and enabled movement controls.
- Click-inspection smoke passed: clicking `(13,17)` showed `Lighting: bright` in the inspection panel.
- Saved visual artifacts at `tasks/cragmaw-vision-live-server-centered.png` and `tasks/cragmaw-vision-live-server-inspection.png`.
- Note: the fixture currently has `night=0` visible cells because the player position, walls, crate, Fog Cloud, and Light aura leave no open-LOS unlit dark cell visible to the player. Darkness is present and server-projected, but those cells are correctly hidden in this fixture.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 10 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m unittest tests.xphb_level1_spells.fog_cloud.test_fog_cloud tests.xphb_cantrips.light.test_light -v` passed 9 tests.
  - `python -m py_compile encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py shared_types\web_ui.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py tests\test_visibility_system.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Water Difficult Terrain

### Scope
- Fix Cragmaw Hideout water/stream cells so players can move into them.
- Treat water as difficult terrain, not blocked stone wall.
- Preserve authored wall LOS/LOE blocking and server-authoritative movement validation.
- Restart the live Cragmaw vision server and verify the in-app browser can inspect/move to water.

### Steps
- [x] Reproduce the water movement failure from the live/demo map data.
- [x] Add a failing regression for Cragmaw water as traversable difficult terrain.
- [x] Implement the minimal map/terrain fix.
- [x] Run focused tests and compile/static checks.
- [x] Restart the live Cragmaw map server.
- [x] Verify water movement in the browser/API and document the result.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m py_compile rules_engine\battlefield_loader.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke for inspecting and moving to a water cell.

### Review
- Root cause: Cragmaw stream cells `(10,17)`, `(10,18)`, and `(10,19)` were not authored as water, so the battlefield loader left them as default `stone_wall` cells with `traversable=false`, `occupiable=false`, and `blocks_los=true`.
- Added `stream_water` terrain to `data/maps/cragmaw_hideout_map.json` and assigned the stream cells to it. The terrain is traversable, occupiable, difficult terrain, movement cost `10` feet per 5-foot square, and does not block LOS/LOE.
- Added a regression in `tests/test_cragmaw_hideout_map.py` proving the stream cells are traversable difficult terrain and that a same-plane move into `(10,17)` is reachable.
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` / `ws://127.0.0.1:8768` as PID `31308`.
- Live API smoke passed: water `(10,17)` reported `stream_water`, traversable, occupiable, difficult terrain, 10-foot terrain cost, and no LOS blocking. Submitting `/move player-1 10 17` from `player-1-controller` succeeded and placed the token at `(10,17,0)`.
- Browser visual smoke passed in the in-app browser: connected as Player 1, token title showed `Map Demo Player @ (10,17,0)`, and the water cell class included `terrain-stream_water`, `visible`, and `difficult`.
- Saved visual artifact at `tasks/cragmaw-water-movement-fixed.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_stream_water_is_traversable_difficult_terrain -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 11 tests.
  - `python -m py_compile rules_engine\battlefield_loader.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Printed Legend Walls

### Scope
- Make the printed lower-left Cragmaw map legend/key area explicitly non-playable wall terrain.
- Preserve the browser UI legend; only the image's authored map-key cells are in scope.
- Add a regression so the legend cells stay walls even if map defaults or nearby floor regions change.
- Restart the live Cragmaw map server and verify the player portal reads those cells as blocked wall cells.

### Steps
- [x] Identify the printed legend/key grid cells from the verified map image metadata.
- [x] Add a failing regression for explicit printed-legend wall authoring.
- [x] Add the explicit legend wall terrain region to the Cragmaw map data.
- [x] Run focused tests and compile/static checks.
- [x] Restart the live Cragmaw map server.
- [x] Verify the legend cells through the live API/browser and document the result.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_printed_legend_cells_are_authored_as_walls -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m py_compile rules_engine\battlefield_loader.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke for printed legend cells.

### Review
- The printed lower-left map legend/key maps to cells `x=1..5`, `y=12..20` from the verified Cragmaw image grid metadata.
- Those cells were already defaulting to `stone_wall`, but the authoring intent was implicit. Added an explicit `cragmaw_hideout_printed_legend_walls` terrain region in `data/maps/cragmaw_hideout_map.json` so the printed key cannot become playable if defaults or nearby floor regions change.
- Added `test_cragmaw_printed_legend_cells_are_authored_as_walls` in `tests/test_cragmaw_hideout_map.py`. Red phase failed because the named legend wall region was missing; green phase passed after the explicit region was added.
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` / `ws://127.0.0.1:8768` as PID `2596`.
- Live API smoke passed: `(1,12)` and `(5,20)` report `stone_wall`, `traversable=false`, `occupiable=false`, `blocks_los=true`, and `blocks_loe=true`. A move into `(3,14)` returned HTTP 400 with `The destination cannot be reached on the current plane.`
- Browser smoke passed: exact rendered cells `(1,12)` and `(5,20)` have class `terrain-stone_wall ... blocked ... not-visible`; adjacent playable cell `(6,14)` remains `terrain-cave_floor`, and water `(10,17)` remains `terrain-stream_water ... difficult`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_printed_legend_cells_are_authored_as_walls -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 12 tests.
  - `python -m py_compile rules_engine\battlefield_loader.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Visible Water Passability

### Scope
- Fix the remaining Cragmaw water movement failure reported from the player portal.
- Treat all visible north-up Cragmaw stream, rapid, and pool cells as passable difficult terrain, not isolated water cells.
- Preserve printed legend walls, cave walls, LOS/LOE blocking, and server-authoritative movement validation.
- Restart the live Cragmaw map server and verify movement through the river and upper-right pool from the browser/API.

### Steps
- [x] Record the correction and narrow the failure from the live map.
- [x] Identify every visible water cell still blocking movement or missing water terrain.
- [x] Add a failing regression for all visible water passability.
- [x] Author the full visible stream/pool system as `stream_water` difficult terrain.
- [x] Run focused tests and compile/static checks.
- [x] Restart the live Cragmaw map server.
- [x] Verify live movement through the river/pool in API/browser and document the result.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_visible_water_is_passable_difficult_terrain -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m py_compile rules_engine\battlefield_loader.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke moving through the entrance river, central stream, and upper-right pool.

### Review
- Correction: the earlier water fix was too narrow because it used a few inspected cells instead of a full image-first pass over the north-up Cragmaw map. The visible water includes the bottom entrance, central stream, bridge-adjacent channel, and upper-right pools.
- Added a red/green regression, `test_cragmaw_visible_water_is_passable_difficult_terrain`, requiring every authored visible water cell to be `stream_water`, traversable, occupiable, difficult terrain, 10 ft per 5-ft square, and non-LOS/LOE-blocking. Red phase failed on `(17,3)` because it was still `cave_floor`.
- Expanded `cragmaw_hideout_stream_water` in `data/maps/cragmaw_hideout_map.json` to cover all visible water cells from the overlay/image pass, while leaving printed legend cells as `stone_wall`.
- Saved overlay artifacts at `tasks/cragmaw-water-grid-overlay.png`, `tasks/cragmaw-central-water-crop.png`, `tasks/cragmaw-upper-right-water-crop.png`, and `tasks/cragmaw-all-water-grid-overlay.png`.
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` / `ws://127.0.0.1:8768` as PID `35556`.
- Live API smoke passed: `(10,20)`, `(10,15)`, `(12,10)`, `(14,5)`, `(17,3)`, `(24,6)`, and `(27,7)` all report `stream_water`, traversable, difficult terrain, cost 10, and no LOS blocking; `(1,12)` remains `stone_wall`.
- Live movement smoke passed from a fresh server state: `/move player-1 10 20`, `/move player-1 12 10`, `/move player-1 24 6`, and `/move player-1 27 7` all returned HTTP 200 and moved the token. The player token ended at `(27,7,0)`.
- Browser smoke passed: map rendered 630 cells; `(10,20)`, `(12,10)`, `(17,3)`, `(24,6)`, and `(27,7)` render with `terrain-stream_water` and `difficult`; `(1,12)` renders `terrain-stone_wall ... blocked`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 13 tests.
  - `python -m py_compile rules_engine\battlefield_loader.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`
  - `git diff --check -- data\maps\cragmaw_hideout_map.json tests\test_cragmaw_hideout_map.py tasks\TODO.md tasks\SUMMARIES.md tasks\LESSONS.md` exited 0 with only Windows line-ending warnings.

## 2026-06-03 - Cragmaw Water Vision

### Scope
- Fix the player-portal visibility issue where water still appears to block or suppress vision.
- Preserve water as passable difficult terrain and non-LOS/LOE-blocking.
- Ensure visible water cells inside the player's LOS and vision mode render as visible in the browser.
- Preserve darkness, wall, Fog Cloud, and printed legend blocking semantics.

### Steps
- [x] Record the vision correction scope.
- [x] Reproduce current live water visibility around the player.
- [x] Trace whether the cause is water terrain, darkness/darkvision, wall LOS, or projection.
- [x] Add a failing regression for visible non-blocking water.
- [x] Implement the minimal fix.
- [x] Restart the live Cragmaw map server.
- [x] Verify live browser/API visibility and document the result.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m py_compile encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke for water cells around the active player.

### Review
- Root cause: the water terrain and LOS flags were correct, but the manual fixture set `actor.darkvision_radius_ft = 60` directly. Spell casts and movement run the rules-kernel derived-state recomputation, which derives senses from active effects and reset the ad-hoc darkvision value to `0`. In darkness, transparent water then projected as `vision_mode=none`.
- Added red/green regression `test_manual_vision_fixture_keeps_dark_water_visible_after_movement`. Red failed with `0 != 60`; green passes after the fixture grants darkvision through a real active effect.
- Updated `user-test/cragmaw_map_demo_server.py` so the `light-fog-crate` fixture applies `Manual Vision Fixture Darkvision` as an `ActiveEffectState` with a 60 ft darkvision radius. This keeps darkvision stable after typed actions while preserving server-authoritative vision projection.
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` / `ws://127.0.0.1:8768` as PID `25752`.
- Live API smoke passed after `/move player-1 27 7`: `(26,7)`, `(27,6)`, `(24,6)`, and `(27,8)` are `stream_water`, difficult terrain, non-LOS-blocking, `lighting=darkness`, `vision_mode=night`, and `visible=true`; `(1,12)` remains hidden `stone_wall`, and Fog Cloud at `(20,19)` remains heavy obscurement and not visible to the player.
- Browser smoke passed in the in-app browser: the map rendered 630 cells with background image, 67 visible cells, 47 night-vision cells, 26 visible water cells, and the token at `(27,7,0)`. Representative cells render as `terrain-stream_water lighting-darkness vision-night visible difficult`.
- Saved browser artifacts at `tasks/cragmaw-water-vision-fixed.png` and `tasks/cragmaw-water-vision-fixed-centered.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_keeps_dark_water_visible_after_movement -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 14 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile encounter_runtime\vision.py encounter_runtime\visibility.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`
  - `git diff --check -- user-test/cragmaw_map_demo_server.py tests/test_cragmaw_hideout_map.py tasks/TODO.md tasks/LESSONS.md tasks/SUMMARIES.md` exited 0 with only Windows line-ending warnings.

## 2026-06-03 - Cragmaw Partial Edge Walls

### Scope
- Fix the remaining visual/vision artifact around Cragmaw cell `(21,4)`.
- Preserve mixed map-art cells as passable terrain when the playable part of the square is water or floor.
- Use edge-specific wall authoring for partial wall sides instead of converting the whole cell into a wall.
- Block movement across the south edge of `(21,4)` while keeping left/right movement and vision passable.
- Restart the live Cragmaw map server and verify the browser/API projection.

### Steps
- [x] Record the edge-wall correction scope.
- [x] Inspect live/map state around `(21,4)`.
- [x] Trace existing edge movement and LOS behavior.
- [x] Add a failing regression for the partial south-edge wall.
- [x] Author the edge override without changing water LOS.
- [x] Run focused tests and compile/static checks.
- [x] Restart the live Cragmaw map server.
- [x] Verify live API/browser movement and vision around `(21,4)`.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_partial_water_wall_uses_edge_blocker_not_cell_los -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m py_compile rules_engine\battlefield_loader.py encounter_runtime\battlefield.py encounter_runtime\vision.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke for `(21,4)` and adjacent left/right/down movement.

### Review
- Root cause: `(21,4)` is a mixed-art stream square with a wall edge on only part of the tile. Modeling that as full-cell wall would break lateral movement and vision, while modeling it as fully open left a southward movement artifact.
- Added a red/green regression, `test_cragmaw_partial_water_wall_uses_edge_blocker_not_cell_los`. Red failed because the south edge from `(21,4)` to `(21,5)` was still `flat`; green passes after adding the explicit edge override.
- Added `cragmaw_hideout_partial_water_wall_21_4_south` to `data/maps/cragmaw_hideout_map.json`. The cell remains `stream_water`, traversable, difficult terrain, and non-LOS/LOE-blocking; the south edge is `transitionType=blocked`, `traversalRequirement=blocked`, `blocksLOS=false`, and `blocksLOE=false`.
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` / `ws://127.0.0.1:8768` as PID `11036`.
- Live API smoke passed: `/move player-1 21 4`, `/move player-1 20 4`, and `/move player-1 22 4` returned HTTP 200, while `/move player-1 21 5` returned HTTP 400. The live projection reports `(21,4)`, `(20,4)`, and `(22,4)` as visible stream water with `blocks_los=false`; `(21,5)` remains a visible stone-wall edge/cell.
- Browser smoke passed in the in-app browser: 630 cells rendered over the map background, token title `Map Demo Player @ (21,4,0)`, and representative cells `(21,4)`, `(20,4)`, and `(22,4)` render as `terrain-stream_water ... visible difficult`.
- Saved visual artifact at `tasks/cragmaw-21-4-partial-edge-wall-fixed.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_partial_water_wall_uses_edge_blocker_not_cell_los -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 15 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile rules_engine\battlefield_loader.py encounter_runtime\battlefield.py encounter_runtime\vision.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`
  - `git diff --check -- data/maps/cragmaw_hideout_map.json tests/test_cragmaw_hideout_map.py tasks/TODO.md tasks/LESSONS.md tasks/SUMMARIES.md` exited 0 with only Windows line-ending warnings.

## 2026-06-03 - Cragmaw Implicit 3D Structure

### Scope
- Add authored elevation to the Cragmaw Hideout image-backed map while preserving server-authoritative movement and vision.
- Model bridge-connected terrain as elevated, keep under-bridge/stream cells passable, and show the map's meaningful height surfaces visually.
- Treat the `(13,9)` to `(20,5)` approach and the stair below the `(24,11)` shelf as gradual authored elevation changes that plain `/move` can traverse without extra confirmation or explicit climb.
- Treat the steep cliff around `(18,12)` to `(20,12)` as passable by climb, not a wall, while blocking line of sight across the cliff edge from either side.

### Steps
- [x] Inspect the Cragmaw image/overlay around the bridge, left stair, right stair, and cliff.
- [x] Add failing regression tests for Cragmaw tile elevations and under-bridge passability.
- [x] Add failing regression tests for default `/move` over authored gradual ramp/stair edges.
- [x] Add failing regression tests for passable LOS-blocking cliff edges.
- [x] Implement the minimal generic edge support for opt-in normal elevation movement and edge LOS/LOE blocking.
- [x] Author Cragmaw terrain elevations and edge overrides.
- [x] Run focused tests, full Cragmaw/visibility tests, compile/static checks, and diff checks.
- [x] Restart the live Cragmaw map server and verify in API/browser.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_implicit_3d_structure_authors_elevations_and_under_bridge_passability -v`
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_gradual_elevation_edges_allow_plain_move_without_confirmation -v`
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_steep_cliff_is_climbable_and_blocks_los_across_edge -v`
- `python -m unittest tests.test_battlefield_map.BattlefieldMapIntegrationTests.test_ramp_override_supports_slope_preview_and_execution -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m py_compile shared_types\battlefield.py rules_engine\battlefield_loader.py encounter_runtime\battlefield.py encounter_runtime\vision.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py tests\test_battlefield_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke for the bridge approach, under-bridge passability, gradual stair movement, cliff climb/LOS behavior, and rendered elevation labels/inspection.

### Review
- Red phase:
  - `test_cragmaw_implicit_3d_structure_authors_elevations_and_under_bridge_passability` failed on `(13,9)` still being `stone_wall`.
  - `test_cragmaw_gradual_elevation_edges_allow_plain_move_without_confirmation` failed with `unreachable_no_traversable_edge`.
  - `test_cragmaw_steep_cliff_is_climbable_and_blocks_los_across_edge` failed on `(18,12)` still being non-traversable.
- Runtime changes:
  - Added typed `BattlefieldEdge.requires_vertical_confirmation`, defaulting to `true`.
  - Edge overrides can now opt gradual authored elevation changes into normal `/move` traversal without requiring `--allow-elevation`.
  - Omitted `/move` z-coordinates now resolve to the destination tile's authored surface elevation.
  - Battlefield LOS/LOE checks and grid vision now honor edge-level `blocksLOS`/`blocksLOE`.
- Map changes:
  - Authored under-bridge cells at 10 ft while keeping them passable, including water as difficult terrain.
  - Added a raised bridge-deck feature from 15 ft to 20 ft.
  - Authored the left stair/ramp from `(13,9)` to `(20,5)` up to 20 ft.
  - Authored the right stair/shelf with `(23,10)` at 20 ft, stair cells at 25 ft, and `(24,11)`/nearby shelf cells at 30 ft.
  - Authored the steep cliff at `(18,12)` to `(20,12)` as climbable passable edges that block LOS/LOE across their south side.
  - Added normal streambed transition edges around the raised under-bridge water so the continuous river remains passable.
- UI/projection:
  - Visible nonzero-elevation cells now show small `ft` badges on the image-backed map.
  - Cell inspection edge summaries now include LOS state and whether elevation movement is normal or needs confirmation.
- Live server:
  - Restarted `user-test/cragmaw_map_demo_server.py --vision-fixture light-fog-crate` on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` / `ws://127.0.0.1:8768` as PID `37236`.
  - Live API verified representative authored cells: `(13,9)=0 ft`, `(16,6)=15 ft`, `(20,5)=20 ft`, under-bridge water `(15,5)/(16,5)=10 ft`, `(24,11)=30 ft`, and cliff cells `(18,12)=20 ft` / `(18,13)=0 ft`.
  - Live `/move player-1 20 5` succeeded without `--allow-elevation`, placing the token at `(20,5,20)`.
  - Browser smoke verified 630 cells rendered, visible elevated-cell badges displayed, and the active token showed `Map Demo Player @ (20,5,20)` with a visible `20ft` badge.
  - Browser artifacts saved at `tasks/cragmaw-elevation-3d-player.png` and `tasks/cragmaw-elevation-3d-player-centered.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 18 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile shared_types\battlefield.py rules_engine\battlefield_loader.py encounter_runtime\battlefield.py encounter_runtime\vision.py encounter_runtime\kernel.py session_server\web_projection.py user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py tests\test_battlefield_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Side LOS And Fast Vision

### Scope
- Fix remaining Cragmaw visual artifacts caused by missing side-specific LOS blockers.
- Add the wall side between `(17,6)` and `(18,6)` so sight cannot pass across that side from either direction.
- Preserve passable cell terrain and dynamic light/fog behavior while moving repeated vision projection under a 1 ms budget.
- Verify the live Cragmaw Hideout map projection in the browser.

### Steps
- [x] Reproduce the missing `(17,6)` to `(18,6)` side blocker and current slow vision timing.
- [x] Add failing regressions for the side LOS blocker and repeated vision performance.
- [x] Author the Cragmaw edge LOS blocker.
- [x] Cache deterministic map geometry visibility while preserving existing visible-cell answers.
- [x] Run focused tests, compile/static checks, and browser/API smoke.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_wall_side_blocks_sight_between_17_6_and_18_6 -v`
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_actor_grid_vision_cache_keeps_answer_and_runs_under_one_ms -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m unittest tests.test_battlefield_map -v`
- `python -m py_compile encounter_runtime\vision.py encounter_runtime\battlefield.py rules_engine\battlefield_loader.py shared_types\battlefield.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live API/browser smoke for Cragmaw side LOS, light/dim/dark projection, and map rendering.

### Review
- Red phase confirmed two failures: `(17,6)` to `(18,6)` had no side LOS blocker, and repeated Cragmaw actor grid vision averaged about 33 ms.
- Added `cragmaw_hideout_wall_side_17_6_to_18_6` as a flat, movement-passable edge that blocks LOS/LOE from either side without changing either square into a wall.
- Added an actor grid-vision cache keyed by actor position/senses and a conservative signature of tiles, features, edges, active lights, and persistent areas. The cached result keeps the same visible, normal, and night-vision cell sets.
- Benchmark after the fix: first Cragmaw fixture projection was 34.648 ms, repeated cached projections averaged 0.163 ms with max 0.260 ms and 95 visible cells.
- Restarted the Cragmaw map demo server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `11700`.
- Live automation smoke passed: player map had 630 cells, 95 visible cells, 94 normal-vision cells, and 1 night-vision cell. `(13,17)` and `(15,17)` were visible normal vision; `(16,17)` was hidden behind the crate; `(21,4)` remained stream water, difficult terrain, non-LOS-blocking, and not a wall.
- Browser smoke passed in the in-app browser and saved screenshots at `tasks/cragmaw-side-los-fast-vision-player.png` and `tasks/cragmaw-side-los-fast-vision-player-centered.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 20 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m py_compile encounter_runtime\vision.py encounter_runtime\battlefield.py rules_engine\battlefield_loader.py shared_types\battlefield.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Bridge Entrance Height Surfaces

### Scope
- Fix movement into `(20,7)`, which is bridge/approach entrance art and must not be treated as a solid wall.
- Let `/move <actor> x y` choose the actor's current height when the destination square has a supported surface at that height.
- Preserve lower-floor movement into `(20,7)` from `(21,7)` or `(21,8)` while also allowing bridge-height movement into `(20,7)` from `(20,6)`.
- Keep bridge/off-bridge state differentiated by token `z`.

### Steps
- [x] Reproduce the user's route and inspect authored surfaces around `(20,7)`.
- [x] Add failing regressions for lower and upper movement into `(20,7)`.
- [x] Author `(20,7)` as a lower cave-floor square plus an upper bridge/approach surface.
- [x] Update movement resolution/pathfinding to consider supported feature surfaces at the actor's current height.
- [x] Run focused tests, full map/movement tests, compile/static checks, and live browser/API smoke.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_bridge_entrance_20_7_supports_lower_and_upper_surfaces -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_battlefield_map -v`
- `python -m py_compile encounter_runtime\battlefield.py encounter_runtime\kernel.py rules_engine\battlefield_loader.py shared_types\battlefield.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live route smoke: `(21,7,0)->(20,7,0)`, `(21,8,0)->(20,7,0)`, and `(20,6,20)->(20,7,20)`.

### Review
- Root cause: `(20,7)` was still the default `stone_wall`, and movement/path planning only considered tile base elevation as a walkable surface. That meant a bridge entrance square could not be lower floor and upper bridge approach at the same x/y coordinate.
- Red phase: `test_cragmaw_bridge_entrance_20_7_supports_lower_and_upper_surfaces` failed because `(20,7)` was `stone_wall`.
- Map changes: added `cragmaw_hideout_bridge_entrance_lower_20_7` as cave floor at 0 ft and `cragmaw_hideout_bridge_approach_20_7` as a traversable/occupiable 20 ft bridge-approach feature.
- Runtime changes: added supported ground-surface enumeration, made omitted movement destinations prefer the actor's current z when available at the destination, derived edge height changes from chosen positions, and recorded movement segments at the chosen surface z.
- Local route smoke matched the user's failure path for the bridge entrance: `/move player-1 20 7` from lower-side movement lands at `(20,7,0)`, while from `(20,6,20)` it lands at `(20,7,20)`. `/move player-1 19 7` remains rejected because that cell is still authored as non-entrance wall/edge art.
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `19248`.
- Live automation smoke passed: `/move player-1 21 8` -> `(21,8,0)`, `/move player-1 20 7` -> `(20,7,0)`, `/move player-1 20 6` -> `(20,6,20)`, and `/move player-1 20 7` -> `(20,7,20)`.
- Browser smoke passed in the in-app browser. Screenshot saved at `tasks/cragmaw-20-7-bridge-height-fixed.png`; token title reported `Map Demo Player @ (20,7,20)`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 21 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile encounter_runtime\battlefield.py encounter_runtime\kernel.py rules_engine\battlefield_loader.py shared_types\battlefield.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Upper Tunnel Full Passability

### Scope
- Fix the remaining elevated bridge/tunnel run, not only `(20,7)`.
- Author the whole 20 ft upper tunnel route the user named: `(19,7)`, `(18,7)`, `(17,6)`, `(16,5)`, and `(15,4)`.
- Verify both omitted-z and explicit `z=20` movement into the tunnel.
- Restart the live server and test the browser-facing route.

### Steps
- [x] Add failing regression for the named 20 ft tunnel coordinates.
- [x] Author the missing upper tunnel cells/surfaces.
- [x] Run focused and full movement/map verification.
- [x] Restart live server and smoke the route visually.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_upper_tunnel_bridge_run_is_passable_at_20ft -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_battlefield_map -v`
- `python -m py_compile encounter_runtime\battlefield.py encounter_runtime\kernel.py tests\test_cragmaw_hideout_map.py`
- Live route smoke: `(20,7,20)->(19,7,20)->(18,7,20)->(17,6,20)->(16,5,20)->(15,4,20)`.

### Review
- Root cause: I only fixed `(20,7)` as a bridge entrance. The adjacent elevated tunnel cells `(18,7)` and `(19,7)` were still default wall cells and had no supported 20 ft surface, so both omitted-z and explicit `z=20` moves into `(19,7)` failed.
- Red phase: `test_cragmaw_upper_tunnel_bridge_run_is_passable_at_20ft` failed because `(19,7,20)` was not a supported surface.
- Map fix: added `cragmaw_hideout_upper_tunnel_20ft` for `(18,7)` and `(19,7)` as traversable/occupiable cave floor at 20 ft. Existing 20 ft surfaces for `(17,6)`, `(16,5)`, and `(15,4)` are now covered by the regression.
- Local smoke passed:
  - `/move player-1 19 7` -> `(19,7,20)`
  - `/move player-1 19 7 20` -> `(19,7,20)`
  - `/move player-1 18 7` -> `(18,7,20)`
  - `/move player-1 17 6` -> `(17,6,20)`
  - `/move player-1 16 5` -> `(16,5,20)`
  - `/move player-1 15 4` -> `(15,4,20)`
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `24308`.
- Live automation smoke passed the same upper tunnel route, including the two commands the user reported as failing.
- Browser smoke passed and saved `tasks/cragmaw-upper-tunnel-20ft-fixed.png`; token title reported `Map Demo Player @ (15,4,20)`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 22 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile encounter_runtime\battlefield.py encounter_runtime\kernel.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Ground Surface Height Resolution

### Scope
- Fix explicit-height `/move` commands so non-flying actors cannot walk below or between authored supported surfaces.
- Reproduce the user's sequence around `(16,5)`, where the square has lower water/floor at 10 ft and upper bridge/tunnel at 20 ft.
- Make ground movement commit the same resolved surface that preview and pathfinding use.
- Keep `/fly` able to target true 3D airspace.

### Steps
- [x] Reproduce the exact command sequence and inspect supported surfaces at the named coordinates.
- [x] Add failing regressions for explicit `z=0` and `z=-10` at `(16,5)`.
- [x] Resolve unsupported ground destination heights to an authored supported surface before validation and event commit.
- [x] Ensure pending/readied movement uses the same resolved destination.
- [x] Run focused and full movement/map verification.
- [x] Restart live server and smoke the corrected command sequence.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_explicit_under_bridge_heights_resolve_to_supported_surface -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_battlefield_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m py_compile encounter_runtime\battlefield.py encounter_runtime\kernel.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live route smoke for the exact `/move player-1 16 5 20/10/0/-10/20` sequence.

### Review
- Root cause: explicit z on ground `/move` bypassed supported-surface destination resolution, and movement events committed the raw requested coordinate even when preview had resolved a supported surface. That allowed impossible walking positions such as `(16,5,0)` and `(16,5,-10)` below the authored 10 ft under-bridge surface.
- Red phase: `test_cragmaw_explicit_under_bridge_heights_resolve_to_supported_surface` failed because `/move player-1 16 5 0` left the actor at `(16,5,0)` instead of `(16,5,10)`.
- Runtime fix: `resolve_ground_destination` now handles explicit unsupported ground heights by choosing an authored supported surface in the destination square. `/fly` remains the explicit airspace path. `preview_move`, normal movement, and readied movement now use and commit `preview.destination`.
- Local smoke for the user's sequence:
  - `/move player-1 16 5` -> `(16,5,10)`
  - `/move player-1 16 5 20` -> `(16,5,20)`
  - `/move player-1 16 5 10` -> `(16,5,10)`
  - `/move player-1 16 5 0` -> `(16,5,10)`
  - `/move player-1 16 5 -10` -> `(16,5,10)`
  - `/move player-1 16 5 20` -> `(16,5,20)`
- Restarted the live Cragmaw map server on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `39292`.
- Live automation smoke passed the full command chain from the user's report, including the earlier route into `(16,5)`: `0` and `-10` both stayed on `(16,5,10)`, and the final explicit `20` reached `(16,5,20)`.
- Browser smoke reloaded the in-app browser against the restarted server and saved `tasks/cragmaw-height-surface-fixed.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_explicit_under_bridge_heights_resolve_to_supported_surface -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 23 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile encounter_runtime\battlefield.py encounter_runtime\kernel.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`
  - `git diff --check -- encounter_runtime/battlefield.py encounter_runtime/kernel.py tests/test_cragmaw_hideout_map.py tasks/TODO.md` exited 0 with only Windows line-ending warnings.

## 2026-06-03 - Cragmaw Fog Cloud Grass Projection

### Scope
- Apply/check Fog Cloud in the lower exterior-looking grass area of the Cragmaw map.
- Fix the player map overlay if the fog's heavy obscurement hides its own persistent-area feature.
- Preserve the rule that fogged cells are not visible/inspectable inside the cloud.

### Steps
- [x] Inspect the live lower-area Fog Cloud projection.
- [x] Add a failing regression that the player map includes the Fog Cloud feature at `(20,19)`.
- [x] Update persistent area projection so obvious non-apparent area effects draw from awareness, not cell inspection.
- [x] Run focused and full map/visibility verification.
- [x] Restart live server and capture the browser view.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_projects_light_fog_and_crate -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m py_compile session_server\web_projection.py tests\test_cragmaw_hideout_map.py`
- `node --check web_frontend\app.js`
- Live automation smoke: Fog Cloud feature appears in player map features while `(20,19)` remains `obscurement=heavy`, `visible=false`.

### Review
- Root cause: player persistent-area projection required at least one area cell to be inspectable. Fog Cloud makes its own cells heavily obscured, so its cells were correctly hidden but the cloud overlay also disappeared from the player map.
- Red phase: `test_manual_vision_fixture_projects_light_fog_and_crate` failed because the player projection had zero `Fog Cloud` features even though the DM projection had the area.
- Runtime fix: non-apparent persistent area effects now project to players when at least one affected cell is in the player's map awareness. Apparent-only areas still require normal inspection visibility.
- Live server restarted on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `37880` with the `light-fog-crate` fixture.
- Live smoke confirmed one player-visible `Fog Cloud` feature covering `(20,19)`, while cells inside the cloud such as `(20,19)` remain `obscurement=heavy`, `visible=false`, `vision=none`.
- Browser smoke reloaded the in-app browser, scrolled to the lower exterior/grass-looking area, and saved `tasks/cragmaw-fog-cloud-grass-fixed.png` plus the inspected-cell screenshot `tasks/cragmaw-fog-cloud-grass-inspection.png`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_projects_light_fog_and_crate -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 23 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile session_server\web_projection.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Cragmaw Fog Cloud Fixture Placement

### Scope
- Move the manual vision fixture's Fog Cloud from `(20,19)` to `(12,14)` because the lower-right placement looks poor in the browser.
- Verify that the player and DM projections both use the new Fog Cloud center.
- Restart the local server and capture a fresh browser screenshot.

### Steps
- [x] Update the regression expectation to `(12,14)` and verify it fails before the fixture moves.
- [x] Move the manual fixture cast to `(12,14)`.
- [x] Run focused and relevant map/visibility verification.
- [x] Restart the live server and capture the browser view.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_projects_light_fog_and_crate -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m py_compile user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
- Live automation smoke: Fog Cloud feature covers `(12,14)` and no longer covers `(20,19)`.
- Browser smoke: capture the player map with the relocated cloud visible in the grass area.

### Review
- Red phase: after changing the regression expectation to `(12,14)`, `test_manual_vision_fixture_projects_light_fog_and_crate` failed because the live fixture still cast Fog Cloud at `(20,19)`.
- Fixture change: `user-test/cragmaw_map_demo_server.py` now casts `/cast player-1 fog-cloud 12 14` for the `light-fog-crate` visual fixture.
- Live server restarted on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `26516`.
- Live automation smoke confirmed one player-visible `Fog Cloud` feature, `fogContains12_14=true`, `fogContains20_19=false`, and 49 feature cells.
- Important visual note: `(12,14)` is authored as `stream_water`, not grass; in the browser it sits near the stream/printed legend edge. The request was applied exactly, but the image still may not read as a clean grass placement.
- Browser smoke selected `(12,14)` and saved `tasks/cragmaw-fog-cloud-12-14.png`. The selected title was `(12,14,0) | stream_water | light bright | obscurement heavy | vision none | visible false`.
- Verification passed:
  - Red check before fixture move: focused test failed with `(12,14) not found` in old Fog Cloud cells.
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_projects_light_fog_and_crate -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 23 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m py_compile user-test\cragmaw_map_demo_server.py tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-03 - Monster Token Icons From Catalog

### Scope
- Link monster runtime actors back to their exact bestiary/catalog record.
- Project monster token icon URLs to the web map for visible monsters.
- Render token icons in the browser while preserving hidden/unseen token privacy.
- Serve local 5e mirror token images through the session server so browser pages can load them over HTTP.

### Steps
- [x] Add a failing regression for visible monster token image URLs and redacted unseen contacts.
- [x] Add token-image metadata to monster catalog records and preserve monster record ids on runtime actors.
- [x] Project token image URLs only when the token identity is visible to the viewer.
- [x] Add local mirror image serving for `/mirror/...` paths.
- [x] Render token images in map badges with initials fallback for non-image/redacted tokens.
- [x] Run tests, restart the live server, and capture a browser/API smoke.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_web_server.SessionWebServerTests.test_monster_map_tokens_include_visible_catalog_icon_urls -v`
- `python -m unittest tests.test_web_server.SessionWebServerTests.test_websocket_join_separates_dm_and_player_views -v`
- `python -m unittest tests.test_monster_pipeline -v`
- `python -m py_compile shared_types\encounter_models.py shared_types\web_ui.py rules_engine\monster_loader.py monster_runtime\compiler.py session_server\web_projection.py session_server\web_server.py`
- `node --check web_frontend\app.js`
- Live automation/API smoke: visible monster tokens have `/mirror/img/bestiary/tokens/XMM/Skeleton.webp` and `/mirror/img/bestiary/tokens/XMM/Mage.webp`; the Goblin Warrior catalog token path is covered in the monster pipeline regression.

### Review
- Red phase: `MonsterRecord` lacked `token_image_path`, `RuntimeActorState` lacked a preserved monster record id, and `WebTokenView` lacked `token_image_url`, causing the new regressions to fail before implementation.
- Catalog/runtime: `rules_engine.monster_loader` now derives local 5e mirror token image paths from `hasToken`, and `monster_runtime.compiler` preserves the exact monster record id on monster actors.
- Projection/privacy: map tokens now include `token_image_url` only for visible/known monster identities. Hidden tokens are omitted as before, and unseen contacts keep `token_image_url=None`.
- Serving/rendering: `SessionWebServer` serves safe local mirror assets under `/mirror/...`, manual web launchers pass the configured mirror base URL through, and `web_frontend/app.js` renders token images in stable circular badges with initials fallback.
- Live servers: restarted Cragmaw on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `17020`; started monster-icon smoke map on `http://127.0.0.1:8002/?portal=dm&autoconnect=1` as PID `35704`.
- Browser/API smoke: DM projection on `8002` showed Skeleton and Mage token URLs; browser DOM confirmed both image badges loaded complete 512x512 WEBP assets. Screenshots saved to `tasks/monster-token-icons-smoke.png`, `tasks/monster-token-icon-crop-skeleton.png`, and `tasks/monster-token-icon-crop-mage.png`.
- Verification passed:
  - `python -m unittest tests.test_monster_pipeline -v`
  - `python -m unittest tests.test_web_server.SessionWebServerTests.test_websocket_join_separates_dm_and_player_views tests.test_web_server.SessionWebServerTests.test_monster_map_tokens_include_visible_catalog_icon_urls -v`
  - `python -m unittest tests.test_visibility_system -v`
  - `python -m unittest tests.test_web_server -v` passed 25 tests.
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_projects_light_fog_and_crate -v`
  - `python -m py_compile shared_types\encounter_models.py shared_types\web_ui.py rules_engine\monster_loader.py monster_runtime\compiler.py session_server\web_projection.py session_server\web_server.py user-test\cragmaw_map_demo_server.py user-test\web_story_demo_server.py tests\test_monster_pipeline.py tests\test_web_server.py tests\test_visibility_system.py`
  - `node --check web_frontend\app.js`

## 2026-06-04 - Fog Cloud Blocks Sight And Fast Movement Projection

### Scope
- Fix Cragmaw Fog Cloud so it blocks LOS like a wall, preventing cells behind the cloud such as `(12,9)` and `(12,8)` from remaining visible/lighted to Player 1.
- Preserve the visible Fog Cloud overlay itself.
- Prove repeated movement/view projection latency remains under 1 ms.

### Steps
- [x] Reproduce the current player projection leak at `(12,9)` and `(12,8)`.
- [x] Add a failing regression for Fog Cloud blocking sight through its area.
- [x] Add or update the focused movement/projection latency regression.
- [x] Implement the smallest LOS/runtime fix.
- [x] Run focused and broader map/visibility verification.
- [x] Restart the live Cragmaw server and capture API/browser smoke.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_fog_cloud_blocks_sight_beyond_cloud -v`
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_actor_grid_vision_cache_keeps_answer_and_runs_under_one_ms -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m unittest tests.test_visibility_system -v`
- `python -m unittest tests.xphb_level1_spells.fog_cloud.test_fog_cloud -v`
- `python -m py_compile encounter_runtime\vision.py encounter_runtime\battlefield.py encounter_runtime\persistent_effects.py encounter_runtime\kernel.py tests\test_cragmaw_hideout_map.py tests\xphb_level1_spells\fog_cloud\test_fog_cloud.py`
- `node --check web_frontend\app.js`
- Live automation/API smoke: player projection after movement has Fog Cloud visible, `(12,9)` and `(12,8)` not visible, and repeated movement/projection timing under 1 ms.

### Review
- Root cause: dynamic persistent areas such as Fog Cloud contributed heavy obscurement to target cells, but they were not treated as ray blockers in the actor grid-vision path. A second endpoint bug remained because line traces skip origin/target cells; when the player stood inside the cloud at `(12,10)`, adjacent cells `(12,9)` and `(12,8)` leaked as visible.
- Red phase: `test_manual_vision_fixture_fog_cloud_blocks_sight_beyond_cloud` failed with `(12,9)` unexpectedly visible before the blocker fix. After live smoke found the origin-inside-cloud case, `test_manual_vision_fixture_observer_inside_fog_cloud_cannot_see_out` failed with `(12,9)` in the visible set.
- Runtime fix: actor grid vision now precomputes dynamic blocking cells/edges and blocks sight through persistent areas that set `blocks_vision`. If the observer's own cell is a blocking cloud cell, outgoing visual sight stops at the observer's square. Authoritative battlefield LOS uses endpoint-aware persistent-area logic: seeing into a cloud remains a heavy-obscurement target case, but seeing out of a cloud or through a cloud is blocked.
- Performance fix: movement now warms actor grid-vision traces after the final `PositionChangedEvent`, so the first post-move projection uses the final committed position. Local timing over `/move player-1 14 17`, `/move player-1 13 17`, `/move player-1 12 17`, and `/move player-1 12 10` measured first calls at `0.0060-0.0083 ms`, averages at `0.1525-0.2786 ms`, and max at `0.3245 ms`.
- Live server restarted on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `35796` with the `light-fog-crate` fixture.
- Live API smoke after `/move player-1 12 10` confirmed `(12,10)` visible/normal/heavy, `(12,9)` visible false / `vision_mode=none`, `(12,8)` visible false / `vision_mode=none`, and one projected `Fog Cloud` feature.
- Browser smoke reloaded the player portal, panned to the map cells, and saved `tasks/cragmaw-fog-cloud-blocks-sight-cells.png`. Rendered DOM classes matched the API: `(12,9)` and `(12,8)` are `vision-none not-visible`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 26 tests.
  - `python -m unittest tests.xphb_level1_spells.fog_cloud.test_fog_cloud -v` passed 7 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_observer_inside_fog_cloud_cannot_see_out tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_manual_vision_fixture_fog_cloud_blocks_sight_beyond_cloud tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_actor_grid_vision_after_movement_runs_under_one_ms -v`
  - `python -m py_compile encounter_runtime\vision.py encounter_runtime\battlefield.py encounter_runtime\persistent_effects.py encounter_runtime\kernel.py tests\test_cragmaw_hideout_map.py tests\xphb_level1_spells\fog_cloud\test_fog_cloud.py`
  - `node --check web_frontend\app.js`

## 2026-06-04 - Cragmaw Lower River And Trees

### Scope
- Fix the lower Cragmaw river segment so `(11,15)` and all lower visible river cells remain passable difficult terrain in actual movement, not just in metadata.
- Check/author the visible tree/briar terrain as difficult terrain where it is playable, without turning it into walls.
- Preserve the printed legend wall region.

### Steps
- [x] Reproduce movement failures around `(11,15)` and lower river cells.
- [x] Inspect tree/briar-looking cells against authored terrain.
- [x] Add failing regressions for lower river movement and tree difficult terrain.
- [x] Patch map terrain regions minimally.
- [x] Run focused and broader map/visibility verification.
- [x] Restart live Cragmaw server and capture API/browser smoke.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_visible_water_is_passable_difficult_terrain -v`
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_lower_river_cells_are_reachable_by_move_command -v`
- `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_tree_cells_are_passable_difficult_terrain -v`
- `python -m unittest tests.test_cragmaw_hideout_map -v`
- `python -m py_compile tests\test_cragmaw_hideout_map.py`
- Live automation/API smoke: representative lower river and tree cells are traversable, occupiable, difficult terrain and `/move` succeeds into representative coordinates.

### Review
- Root cause: the image-backed river continuation was under-authored at the bottom: `(11,19)` remained `cave_floor` and `(11,20)` was default `stone_wall`, so movement down the visible right side of the lower stream failed. The visible tree/briar patches around the lower entrance were also plain `cave_floor`, so they were not difficult terrain.
- Red phase: the focused terrain tests failed on `(11,19)` being `cave_floor`, `(11,20)` being unreachable, and `(6,14)` being `cave_floor` instead of `briars`.
- Map fix: added a `briars` terrain type that is traversable/occupiable, costs 10 ft per 5 ft, is lightly obscured, grants half cover, and does not block LOS/LOE. Authored representative visible briar cells around the lower-left and right-bank thickets. Extended `cragmaw_hideout_stream_water` to include `(11,19)` and `(11,20)`.
- Movement impact: the old path-cost assertion to `(10,17)` increased from 25 ft to 30 ft because the route now correctly crosses difficult briars at `(12,17)`.
- Live server restarted on `http://127.0.0.1:8001/?portal=player-1-controller&autoconnect=1` as PID `9728`.
- Live API smoke confirmed `(11,15)`, `(11,18)`, `(11,19)`, and `(11,20)` are `stream_water`, traversable, occupiable, difficult terrain, cost 10, and `/move player-1 11 19` plus `/move player-1 11 20` both succeeded. Tree cells such as `(6,14)`, `(12,17)`, and `(12,19)` are `briars`, traversable, occupiable, difficult terrain, cost 10.
- Browser smoke saved `tasks/cragmaw-lower-river-briars-fixed.png`. Rendered classes confirmed `(11,19)` and `(11,20)` as `terrain-stream_water ... difficult`, and `(6,14)`, `(12,17)`, `(12,19)` as `terrain-briars ... difficult`.
- Verification passed:
  - `python -m unittest tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_visible_water_is_passable_difficult_terrain tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_tree_cells_are_passable_difficult_terrain tests.test_cragmaw_hideout_map.CragmawHideoutMapTests.test_cragmaw_lower_river_cells_are_reachable_by_move_command -v`
  - `python -m unittest tests.test_cragmaw_hideout_map -v` passed 28 tests.
  - `python -m unittest tests.test_visibility_system -v` passed 5 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 18 tests.
  - `python -m py_compile tests\test_cragmaw_hideout_map.py`
  - `node --check web_frontend\app.js`

## 2026-06-04 - PaBTSO Player Hex Region And Triboar Trail Assets

### Scope
- Replace the semantic-only main travel hex display with the PaBTSO / 5e.tools player-region hex map image and official hex grid metadata.
- Preserve server-authoritative axial travel routing while adding source-grid placement data for visual alignment.
- Implement Triboar Trail using PaBTSO / 5e.tools assets: the gridded Goblin Ambush player map for tactical combat, and the Shattered Obelisk Triboar Trail scene image as source metadata.
- Keep player/DM visibility split for travel landmarks and pending battlefield ids.

### Steps
- [x] Add failing regressions for PaBTSO travel-map background metadata and per-hex render grid placement.
- [x] Add failing projection/websocket regressions for travel background and rendered hex placement reaching the browser contract.
- [x] Add PaBTSO source metadata/background support to travel map types and loader.
- [x] Update the LMOP travel map fixture with PaBTSO player map metadata and render-grid positions.
- [x] Update the Triboar Trail goblin ambush map metadata/background to the PaBTSO player map asset.
- [x] Render travel maps on the official hex background using `hexColsOdd` alignment.
- [x] Run unit, compile, frontend syntax, and browser/API smoke verification.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_travel_system.TravelSystemTests.test_lmop_fixture_loads_pabtso_player_region_background_and_render_grid -v`
- `python -m unittest tests.test_web_server.SessionWebServerTests.test_story_websocket_projects_travel_map_with_player_dm_visibility_split -v`
- `python -m unittest tests.test_battlefield_map.BattlefieldMapTests.test_goblin_ambush_map_uses_pabtso_player_background -v`
- `python -m unittest tests.test_travel_system -v`
- `python -m unittest tests.test_web_server -v`
- `python -m unittest tests.test_battlefield_map -v`
- `python -m py_compile shared_types\travel.py shared_types\web_ui.py rules_engine\hexmap_loader.py session_server\web_projection.py`
- `node --check web_frontend\app.js`
- Live/browser smoke: the story travel map exposes `assets/maps/pabtso-phandalin-region-player.webp`, rendered hexes have source-grid placements, and the Triboar Trail combat map exposes `assets/maps/pabtso-goblin-ambush-player.webp`.

### Review
- Red phase: travel map tests failed because `HexMapDefinition` had no `background_image`; the web projection test failed because serialized travel views had no `background`; the tactical-map test failed because Goblin Ambush had no background image.
- Source data: local 5e.tools PaBTSO metadata identified the player region map as `adventure/PaBTSO/004-map-0.01-phandalin-region-player.webp` with `hexColsOdd`, `size=240`, `offset=(17,-35)`, `scale=3`; Goblin Ambush player map is `010-map-1.01-goblin-ambush-player.webp` with square `size=150`, `offset=(84,31)`, `scale=3`; the scenic Triboar Trail asset `035-03-002.triboar-trail.webp` was copied for local static use.
- Travel schema/projection: added `TravelMapImageSpec`, `HexRenderCoord`, `WebTravelMapBackgroundView`, and per-hex `render_coord` so routing remains axial while browser placement follows the source map grid.
- Fixture/rendering: `campaigns/lmop/maps/high-road-region-hex.json` now uses the PaBTSO player-region map, 5-mile hex scale, and source-grid placements along the visible road/trail. The frontend renders background travel maps with `hexColsOdd` placement and compact flat-top controls.
- Tactical map: `data/maps/goblin_ambush_triboar_trail_map.json` now uses the PaBTSO Goblin Ambush player background, rendered with the effective 50 px grid size and offset `(28,10)`.
- Assets copied:
  - `web_frontend/assets/maps/pabtso-phandalin-region-player.webp`
  - `web_frontend/assets/maps/pabtso-goblin-ambush-player.webp`
  - `web_frontend/assets/maps/pabtso-triboar-trail-scene.webp`
- Live server: started story demo at `http://127.0.0.1:8004/?portal=player-1-controller&autoconnect=1` as PID `45928`; API projection confirmed the PaBTSO background, effective grid size 80, and route render coordinates.
- Browser smoke: in-app browser confirmed `.travel-hexmap.has-background`, PaBTSO background loading from `assets/maps/pabtso-phandalin-region-player.webp`, seven player-visible travel hexes, and overlays on the visible road/trail. Screenshots saved to `tasks/pabtso-travel-map-player-region.png`, `tasks/pabtso-travel-map-player-route.png`, and `tasks/pabtso-travel-map-player-route-current.png`.
- Verification passed:
  - `python -m unittest tests.test_travel_system.TravelSystemTests.test_lmop_fixture_loads_pabtso_player_region_background_and_render_grid -v`
  - `python -m unittest tests.test_web_server.SessionWebServerTests.test_story_websocket_projects_travel_map_with_player_dm_visibility_split -v`
  - `python -m unittest tests.test_battlefield_map.BattlefieldMapIntegrationTests.test_goblin_ambush_map_uses_pabtso_player_background -v`
  - `python -m unittest tests.test_travel_system -v` passed 5 tests.
  - `python -m unittest tests.test_battlefield_map -v` passed 19 tests.
  - `python -m unittest tests.test_web_server -v` passed 25 tests after rerunning with a 180s timeout; the first 60s timeout was a harness limit, not a test failure.
  - `python -m py_compile shared_types\travel.py shared_types\web_ui.py rules_engine\hexmap_loader.py session_server\web_projection.py`
  - `node --check web_frontend\app.js`
  - Live tactical projection smoke confirmed `assets/maps/pabtso-goblin-ambush-player.webp`, source path `adventure/PaBTSO/010-map-1.01-goblin-ambush-player.webp`, grid size 50, offset `(28,10)`, and 18 x 26 map grid.

## 2026-06-04 - PaBTSO Full Travel Hex Grid Coverage

### Scope
- Fix the player-region travel map so the official hex overlay covers the whole PaBTSO player map, not just the authored route cells.
- Keep full-grid visual coverage separate from the rules-owned travel graph so pathfinding and discovery are not polluted by fake nodes.
- Preserve the semantic route/landmark overlays on top of the full-grid visual layer.

### Steps
- [x] Add failing regressions for travel background grid bounds and websocket projection.
- [x] Add travel background grid-bound metadata to shared types, loader, and projection.
- [x] Update the PaBTSO travel fixture with official source-grid bounds covering the full player map.
- [x] Render a non-interactive full-map hex overlay under authored travel buttons.
- [x] Run focused and broader verification plus browser/API smoke.
- [x] Update lessons and summary notes.

### Verification Plan
- `python -m unittest tests.test_travel_system.TravelSystemTests.test_lmop_fixture_loads_pabtso_player_region_background_and_render_grid -v`
- `python -m unittest tests.test_web_server.SessionWebServerTests.test_story_websocket_projects_travel_map_with_player_dm_visibility_split -v`
- `python -m unittest tests.test_travel_system -v`
- `python -m unittest tests.test_web_server.SessionWebServerTests.test_story_websocket_projects_travel_map_with_player_dm_visibility_split tests.test_web_server.SessionWebServerTests.test_story_websocket_supports_travel_inspection_route_preview_and_advancement -v`
- `python -m py_compile shared_types\travel.py shared_types\web_ui.py rules_engine\hexmap_loader.py session_server\web_projection.py`
- `node --check web_frontend\app.js`
- Live/browser smoke: player portal has hundreds of `.travel-grid-hex` overlay cells covering the PaBTSO map and the semantic route buttons still work.

### Review
- Root cause: the previous PaBTSO travel-map change used the official image as a background, but only rendered the seven player-visible authored route cells. That aligned the route strip but did not make the app's hex overlay cover the whole official player map.
- Red phase: focused travel and websocket regressions failed because `TravelMapImageSpec` had no `grid_bounds`, and serialized travel backgrounds had no `grid_bounds` or `grid_cell_count`.
- Backend fix: added `TravelMapGridBounds`, loader validation, web projection serialization, and a derived `grid_cell_count`. The PaBTSO player-region fixture now declares source-grid bounds `col 0..28`, `row 0..27`, yielding 812 visual cells.
- Frontend fix: `web_frontend/app.js` now renders a non-interactive `.travel-grid-layer` beneath the semantic route buttons. The layer uses the same scaled `hexColsOdd` placement as authored travel cells, so the visual hex overlay spans the whole player-region image without changing travel pathfinding.
- Live server: started corrected story demo on `http://127.0.0.1:8005/?portal=player-1-controller&autoconnect=1` as PID `41416`; stopped the older `8004` smoke server PID `45928`.
- Live API/browser smoke: API returned `grid_bounds={'min_col': 0, 'min_row': 0, 'max_col': 28, 'max_row': 27}`, `grid_cell_count=812`, and 7 semantic travel hexes. Browser DOM confirmed `.travel-grid-layer` present, `.travel-grid-hex` count 812, and `.travel-hex` route button count 7.
- Browser artifact: `tasks/pabtso-travel-map-full-grid-route.png`.
- Verification passed:
  - `python -m unittest tests.test_travel_system.TravelSystemTests.test_lmop_fixture_loads_pabtso_player_region_background_and_render_grid -v`
  - `python -m unittest tests.test_web_server.SessionWebServerTests.test_story_websocket_projects_travel_map_with_player_dm_visibility_split -v`
  - `python -m unittest tests.test_travel_system -v` passed 5 tests.
  - `python -m unittest tests.test_web_server.SessionWebServerTests.test_story_websocket_projects_travel_map_with_player_dm_visibility_split tests.test_web_server.SessionWebServerTests.test_story_websocket_supports_travel_inspection_route_preview_and_advancement -v` passed 2 tests.
  - `python -m py_compile shared_types\travel.py shared_types\web_ui.py rules_engine\hexmap_loader.py session_server\web_projection.py`
  - `node --check web_frontend\app.js`
  - Targeted `git diff --check` passed with only LF/CRLF warnings.
