# Witch Bolt

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast player-1 witch-bolt <target>; sustain with /cast player-1 witch-bolt <target> --mode sustain`

Local XPHB use case: Deterministic spell attack with a linked sustain command while concentration remains active.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 witch-bolt <target>; sustain with /cast player-1 witch-bolt <target> --mode sustain`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
