# Minor Illusion

XPHB cantrip rollout entry.
Runtime support mode: `deterministic-capability`.
Example cast: `/cast player-1 minor-illusion 3 4 --template minor_visual_door --label Door --description Painted door`

Use case: Creates a localized visual or auditory illusion with observer-relative state.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 minor-illusion 3 4 --template minor_visual_door --label Door --description Painted door`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
