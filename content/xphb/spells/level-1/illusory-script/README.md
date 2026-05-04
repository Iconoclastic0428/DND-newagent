# Illusory Script

XPHB level-1 spell rollout entry. Runtime support mode: `story-adjudicated`.

Cast syntax: `/cast <actor-id> illusory-script --readers <comma-separated actor ids> --description <requested use>`

Local XPHB notes:
- 1 minute, touch, consumed ink worth 10+ gp.
- The spell lasts 10 days.
- Chosen readers see the intended text and meaning; everyone else sees unreadable or magical script, and the readers metadata should identify the intended readers.
- The text can appear in another language or handwriting if you know that language.
- Dispel Magic removes both the illusion and the original text.
- True sight reveals the hidden message.

Test coverage: [tests/xphb_level1_spells/illusory_script/test_illusory_script.py](../../../../../tests/xphb_level1_spells/illusory_script/test_illusory_script.py)

Use cases and exact local text notes live in [docs/xphb-level1-spell-use-cases.md](../../../../../docs/xphb-level1-spell-use-cases.md).
