# Shocking Grasp

XPHB cantrip rollout entry.
Runtime support mode: `deterministic-capability`.
Example cast: `/cast player-1 shocking-grasp monster-skeleton-1`

Use case: Melee spell attack that deals lightning damage and blocks opportunity attacks on a hit.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 shocking-grasp monster-skeleton-1`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
