# Mending

XPHB cantrip rollout entry.
Runtime support mode: `story-adjudicated`.
Example cast: `/cast player-1 mending --description Repair the torn wagon harness`

Use case: Story-mode repair spell; the DM/runtime verifies the declared fix.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 mending --description Repair the torn wagon harness`
- Support: story-mode spell command. The runtime records the typed cast and validates/adjudicates the declared effect through the story spell path.
