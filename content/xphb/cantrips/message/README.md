# Message

XPHB cantrip rollout entry.
Runtime support mode: `story-adjudicated`.
Example cast: `/cast player-1 message player-2 --message Keep Gundren talking --reply I can do that`

Use case: Story-mode whisper spell; the backend stores the private message and reply.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 message player-2 --message Keep Gundren talking --reply I can do that`
- Support: story-mode spell command. The runtime records the typed cast and validates/adjudicates the declared effect through the story spell path.
