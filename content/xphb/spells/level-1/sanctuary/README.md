# Sanctuary

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> sanctuary <target-id>`

Local XPHB use case: One-minute ward on a creature; it should force attackers and harmful spellcasters through the Sanctuary save flow, which the current runtime still lacks.

Test module: `tests.xphb_level1_spells.sanctuary.test_sanctuary`

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> sanctuary <target-id>`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources. Metadata blocker status is `mechanical-runtime-missing`; do not invent unsupported parameters or edge-case mechanics beyond the documented command path.
