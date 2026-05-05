# Hunter's Mark

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> hunter-s-mark <target-id>`

Local XPHB use case: Bonus-action mark with concentration; weapon hits against the marked target deal extra force damage, and the Perception/Survival transfer logic remains a missing runtime hook.

Test module: `tests.xphb_level1_spells.hunter_s_mark.test_hunter_s_mark`

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> hunter-s-mark <target-id>`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources. Metadata blocker status is `mechanical-runtime-missing`; do not invent unsupported parameters or edge-case mechanics beyond the documented command path.
