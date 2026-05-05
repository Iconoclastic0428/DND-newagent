# Resistance

XPHB cantrip rollout entry.
Runtime support mode: `deterministic-capability`.
Example cast: `/cast player-1 resistance player-1 --damage-type fire`

Use case: Chosen-damage reduction effect that applies to the selected damage type.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 resistance player-1 --damage-type fire`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
