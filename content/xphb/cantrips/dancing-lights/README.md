# Dancing Lights

XPHB cantrip rollout entry.
Runtime support mode: `deterministic-capability`.
Example cast: `/cast player-1 dancing-lights 1 1 --form lights`

Use case: Creates moving light sources and can be commanded to change form.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 dancing-lights 1 1 --form lights`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
