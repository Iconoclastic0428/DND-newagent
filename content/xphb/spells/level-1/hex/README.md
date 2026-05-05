# Hex

XPHB level-1 spell rollout entry. Runtime support mode: `deterministic-capability`.

Cast syntax: `/cast <actor-id> hex <target-id> --ability strength`

Local XPHB use case: Bonus-action curse with concentration; the target takes extra necrotic damage from weapon hits, and the chosen-ability debuff remains a missing runtime hook.

Test module: `tests.xphb_level1_spells.hex.test_hex`

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast <actor-id> hex <target-id> --ability strength`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources. Metadata blocker status is `mechanical-runtime-missing`; do not invent unsupported parameters or edge-case mechanics beyond the documented command path.
