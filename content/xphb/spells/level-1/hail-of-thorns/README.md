# Hail of Thorns

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/attack player-1 <ranged-weapon> <target> then /react player-1 hail-of-thorns:player-1:hail-of-thorns`

Local XPHB use case: Deterministic post-hit bonus-action spell trigger after a ranged weapon hit.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/attack player-1 <ranged-weapon> <target> then /react player-1 hail-of-thorns:player-1:hail-of-thorns`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources. Metadata blocker status is `mechanical-runtime-missing`; do not invent unsupported parameters or edge-case mechanics beyond the documented command path.
- Reaction note: use the concrete option id shown by the active reaction prompt when it differs from the illustrative id above.
