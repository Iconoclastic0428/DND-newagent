# Fog Cloud

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast player-1 fog-cloud x y`

Local XPHB use case: Deterministic heavy-obscurement persistent area.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 fog-cloud x y`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources. Metadata blocker status is `mechanical-runtime-missing`; do not invent unsupported parameters or edge-case mechanics beyond the documented command path.
