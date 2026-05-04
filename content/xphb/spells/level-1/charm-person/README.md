# Charm Person

XPHB level-1 story-adjudicated spell rollout entry.

Cast syntax: `/cast <actor-id> charm-person <target-id> --description <requested use>`

Local XPHB notes:
- 1 action, 30-foot point, visible humanoid, Wisdom save.
- The save is made with advantage if you or your allies are fighting the target.
- On failure, the target is charmed for 1 hour or until you or your allies damage it.
- The charmed target becomes friendly to you, and it knows it was charmed when the spell ends.
- Higher-level slots add one additional target per slot above 1st.

Test coverage: [tests/xphb_level1_spells/charm_person/test_charm_person.py](../../../../../tests/xphb_level1_spells/charm_person/test_charm_person.py)

Use cases and exact local text notes live in [docs/xphb-level1-spell-use-cases.md](../../../../../docs/xphb-level1-spell-use-cases.md).
