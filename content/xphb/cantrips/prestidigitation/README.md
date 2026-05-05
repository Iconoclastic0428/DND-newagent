# Prestidigitation

XPHB cantrip rollout entry.
Runtime support mode: `story-adjudicated`.
Example cast: `/cast player-1 prestidigitation --effect clean-or-soil --description Clean the mud from Gundren's map case`

Use case: Story-mode utility spell; the DM/runtime verifies the harmless effect text.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 prestidigitation --effect clean-or-soil --description Clean the mud from Gundren's map case`
- Support: story-mode spell command. The runtime records the typed cast and validates/adjudicates the declared effect through the story spell path.
