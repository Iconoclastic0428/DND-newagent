# Detect Poison and Disease

XPHB level-1 spell rollout entry. Runtime support mode: `story-adjudicated`.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 detect-poison-and-disease`
- Example: `/cast player-1 detect-poison-and-disease --mode inspect`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
