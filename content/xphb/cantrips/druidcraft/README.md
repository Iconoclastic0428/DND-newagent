# Druidcraft

XPHB cantrip rollout entry.
Runtime support mode: `story-adjudicated`.
Example cast: `/cast player-1 druidcraft --effect weather-sensor --description Predict tomorrow rain`

Use case: Story-mode nature utility spell; the DM/runtime verifies the declared effect.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 druidcraft --effect weather-sensor --description Predict tomorrow rain`
- Support: story-mode spell command. The runtime records the typed cast and validates/adjudicates the declared effect through the story spell path.
