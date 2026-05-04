# Silent Image

XPHB level-1 spell rollout entry. Runtime support mode: `story-adjudicated`.

Cast syntax: `/cast player-1 silent-image 2 3 --template minor_visual_door --label Door --description "Painted door"`

Local XPHB use case: Visual-only illusion created from a limited template set; study and physical interaction should reveal it to observers.

Test module: `tests.xphb_level1_spells.silent_image.test_silent_image`

Blocker note: The test module exercises the illusion template, observer-state, and reveal flow. Freeform movement/scene-scale illusion motion remains outside the current runtime hook set.
