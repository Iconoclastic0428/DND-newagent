# Ice Knife

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> ice-knife <target-id>`

Local XPHB use case: Single-target ice dart with a 5-foot cold burst around the struck point; the test harness uses the shared persistent-area transition hook to model the splash.

Test module: `tests.xphb_level1_spells.ice_knife.test_ice_knife`

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> ice-knife <target-id>`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources. Metadata blocker status is `mechanical-runtime-missing`; do not invent unsupported parameters or edge-case mechanics beyond the documented command path.
