# Vicious Mockery

XPHB cantrip rollout entry.
Runtime support mode: `deterministic-capability`.
Example cast: `/cast player-1 vicious-mockery monster-skeleton-1`

Use case: Psychic save cantrip that imposes an attack penalty rider.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 vicious-mockery monster-skeleton-1`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
