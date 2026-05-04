# Disguise Self

XPHB level-1 spell rollout entry. Runtime support mode: `story-adjudicated`.

Cast syntax: `/cast <actor-id> disguise-self --form <chosen form> --description <requested use>`

Local XPHB notes:
- 1 action, self, 1 hour.
- Changes your appearance and the appearance of worn gear; the chosen form metadata should describe the intended disguise.
- Height can vary by 1 foot up or down; body shape can be fat or thin.
- The chosen form must match your limb arrangement.
- Physical inspection reveals the illusion; Study against your spell save DC can identify it.

Test coverage: [tests/xphb_level1_spells/disguise_self/test_disguise_self.py](../../../../../tests/xphb_level1_spells/disguise_self/test_disguise_self.py)

Use cases and exact local text notes live in [docs/xphb-level1-spell-use-cases.md](../../../../../docs/xphb-level1-spell-use-cases.md).
