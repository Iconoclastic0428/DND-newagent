# XPHB Cantrip Batch Report

## Deterministic Cantrips
- `Dancing Lights`: `/cast player-1 dancing-lights 3 4 --form lights` or `/cast player-1 dancing-lights 4 4 --mode move --form humanoid`
  - Tests: `tests.xphb_cantrips.dancing_lights.test_dancing_lights`
  - Blockers: none
- `Friends`: `/cast player-1 friends monster-mage-1`
  - Tests: `tests.xphb_cantrips.friends.test_friends`
  - Blockers: none
- `Mage Hand`: `/cast player-1 mage-hand 3 4`, then `/cast player-1 mage-hand 4 4 --mode command --object door-1 --action open`
  - Tests: `tests.xphb_cantrips.mage_hand.test_mage_hand`
  - Blockers: none
- `Produce Flame`: `/cast player-1 produce-flame`, then `/cast player-1 produce-flame monster-skeleton-1 --mode throw`
  - Tests: `tests.xphb_cantrips.produce_flame.test_produce_flame`
  - Blockers: none
- `Resistance`: `/cast player-1 resistance player-1 --damage-type fire`
  - Tests: `tests.xphb_cantrips.resistance.test_resistance`
  - Blockers: none
- `Shillelagh`: `/cast player-1 shillelagh quarterstaff`
  - Tests: `tests.xphb_cantrips.shillelagh.test_shillelagh`
  - Blockers: none
- `Sorcerous Burst`: `/cast player-1 sorcerous-burst monster-skeleton-1 --damage-type fire`
  - Tests: `tests.xphb_cantrips.sorcerous_burst.test_sorcerous_burst`
  - Blockers: none
- `True Strike`: `/cast player-1 true-strike monster-skeleton-1 --item dagger --damage-type radiant`
  - Tests: `tests.xphb_cantrips.true_strike.test_true_strike`
  - Blockers: none

## Story-Adjudicated Cantrips
- `Druidcraft`: `/cast player-1 druidcraft --effect bloom`
  - Tests: `tests.xphb_cantrips.druidcraft.test_druidcraft`
  - Blockers: none
- `Elementalism`: `/cast player-1 elementalism --effect beckon-fire`
  - Tests: `tests.xphb_cantrips.elementalism.test_elementalism`
  - Blockers: none
- `Mending`: `/cast player-1 mending broken-item --description "Repair the snapped strap"`
  - Tests: `tests.xphb_cantrips.mending.test_mending`
  - Blockers: none
- `Message`: `/cast player-1 message player-2 --message "Keep Gundren talking" --reply "I can do that"`
  - Tests: `tests.xphb_cantrips.message.test_message`
  - Blockers: none
- `Prestidigitation`: `/cast player-1 prestidigitation --effect clean-or-soil --description "Clean the muddy cloak"`
  - Tests: `tests.xphb_cantrips.prestidigitation.test_prestidigitation`
  - Blockers: none
- `Thaumaturgy`: `/cast player-1 thaumaturgy --effect booming-voice`
  - Tests: `tests.xphb_cantrips.thaumaturgy.test_thaumaturgy`
  - Blockers: none
