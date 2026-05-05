# Thaumaturgy

XPHB cantrip rollout entry.
Runtime support mode: `story-adjudicated`.
Example cast: `/cast player-1 thaumaturgy --effect booming-voice --description Boom my voice through the tavern`

Use case: Story-mode utility spell; the DM/runtime verifies the declared effect.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 thaumaturgy --effect booming-voice --description Boom my voice through the tavern`
- Support: story-mode spell command. The runtime records the typed cast and validates/adjudicates the declared effect through the story spell path.
