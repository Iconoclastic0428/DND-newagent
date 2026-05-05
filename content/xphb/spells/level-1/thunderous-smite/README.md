# Thunderous Smite

XPHB level-1 spell rollout entry. Runtime support mode: `story-adjudicated`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/attack player-1 <melee-weapon> monster-skeleton-1, then choose the shown option with /react player-1 thunderous-smite:player-1:thunderous-smite`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
- Reaction note: use the concrete option id shown by the active reaction prompt when it differs from the illustrative id above.
