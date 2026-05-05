# Player Quick Reference

## Scope

This is the current starter guide for the repo as it exists now.
Use it for:
- the browser-based full-story demo
- deterministic character creation
- storytelling, exploration, travel, social, and downtime play
- combat-mode commands
- current XPHB level-1 spell, cantrip, and class-feature coverage

The backend remains authoritative. The web UI is a synchronized view and command surface, not the source of truth.

## What Is Implemented Now

The current repo supports all of these layers in the demo/runtime:
- four-player browser demo with DM and player portals
- deterministic XPHB / PHB'24 level-1 character creation, including required class choices and option sets
- XPHB cantrips: 34 available
  - 28 `deterministic-capability`
  - 6 `story-adjudicated`
- XPHB level-1 spells: 64 available
  - 59 `deterministic-capability`
  - 5 `story-adjudicated`
- XPHB level-1 base class features: 33 implemented, with required option families wired
- story-mode spellcasting with witness perception, magical norms, social reaction, and hostile-escalation handling
- hex travel, marching order, watch order, roles, camp flow, trap/puzzle/search/study procedures, and downtime hooks
- persistent effects, illusions, summons, created objects, detection/divination payloads, and persistent areas
- hostile escalation from story mode into combat, including ad hoc scene synthesis when no authored battle map exists
- persistent social consequences, reputation, faction memory, local magical norms, delayed rumor/report propagation, and LMOP-specific authored social templates

## Run The Web Demo

Start the browser demo server from repo root:

```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767
```

Open:

```text
http://127.0.0.1:8000
```

Quick portals:
- DM: `http://127.0.0.1:8000/?portal=dm&autoconnect=1`
- Player 1: `http://127.0.0.1:8000/?portal=player-1-controller&autoconnect=1`
- Player 2: `http://127.0.0.1:8000/?portal=player-2-controller&autoconnect=1`
- Player 3: `http://127.0.0.1:8000/?portal=player-3-controller&autoconnect=1`
- Player 4: `http://127.0.0.1:8000/?portal=player-4-controller&autoconnect=1`

Default tokens:
- `dm` -> `dm-token`
- `player-1-controller` -> `player-1-controller-token`
- `player-2-controller` -> `player-2-controller-token`
- `player-3-controller` -> `player-3-controller-token`
- `player-4-controller` -> `player-4-controller-token`

## Web UI Flow

### Main Panels

- Semantic map: shows the combat battlefield or the exploration hex map, depending on mode.
- Inspection panel: shows terrain, coordinates, movement, cover, blockers, travel cost, landmarks, and route semantics for the selected tile or hex.
- Chat and narration log: shows DM narration, declarations, check results, combat log entries, and system feedback.
- Character card sidebar: shows player-owned cards, plus DM inspection cards.
- Action panel: shows backend-projected legal actions. During character creation it shows pending choice options and helper buttons.
- Prompt panel: shows reaction prompts, timing windows, and story-check prompts.

### Browser Interaction Notes

- The browser demo now starts in storytelling with four precreated default player characters.
- If you launch with `--start-in-character-creation`, the initial browser action panel offers `Begin character creation` before anyone types `/create begin`.
- During the optional character-creation phase, each projected option offers both `Insert id` and `Insert command` so you can paste either an option id or a full `/create ...` stub into the chat box.
- Left click a combat tile or travel hex to inspect it.
- In travel mode, clicking a reachable known hex previews a route.
- In combat, clicking reachable tiles previews movement for the active owned actor.
- If the map is larger than the viewport, hold the right mouse button and drag to pan.
- The DM sees the full travel map and hidden hooks. Players see only discovered travel hexes and revealed landmarks.

### Mode Flow

The browser demo starts in `storytelling` with all four default player characters already confirmed.
If launched with `--start-in-character-creation`, it starts in `character-creation` and hands off after all four players confirm.
Travel, social scenes, traps, puzzles, and downtime all happen in storytelling mode.
If a hostile action or initiative-sensitive scene occurs, the backend can switch to `combat`.
When combat ends, the session can return to storytelling while keeping story/exploration/social state.

## Character Creation

### Core Flow

Most players will use this order:

```text
/create begin
/create choose species <species-id>
/create choose class <class-id>
/create choose class-skills <skill-id> ...
/create choose background <background-id>
/create choose origin-feat <feat-id>
/create choose choice <choice-id> <option-id...>
/create ability generate point-buy <6 scores>
/create ability choose point-buy
/create ability assign <STR DEX CON INT WIS CHA>
/create background-asi choose <option-id>
/create equipment background gold
/create equipment class package <package-id>
/create summary
/create confirm
```

### Useful Creation Commands

- `/create policy show`
- `/create summary`
- `/create inspect species <species-id>`
- `/create inspect class <class-id>`
- `/create inspect background <background-id>`
- `/create inspect feat <feat-id>`
- `/create inspect item <item-id>`
- `/create ability generate roll`
- `/create ability generate point-buy <6 scores>`
- `/create ability choose rolled`
- `/create ability choose point-buy`
- `/create ability assign <STR DEX CON INT WIS CHA>`
- `/create equipment background package <package-id>`
- `/create equipment background gold`
- `/create equipment class wealth`
- `/create equipment class package <package-id>`
- `/create equipment buy <item-id> <quantity>`

### Creation Notes

Use `/create choose choice ...` for pending creation choices, including:
- class cantrips and class spells
- class-feature option groups
- class skills
- background skill or tool choices
- background or origin-feat subchoices
- Magic Initiate spellcasting ability, cantrips, and spell
- class equipment package branches
- any normalized level-1 XPHB choice surfaced by the mirror

The current XPHB level-1 creation layer includes required class-specific picks such as:
- Cleric `Divine Order`
- Druid `Primal Order`
- Fighter level-1 `Fighting Style`
- Rogue `Expertise`
- Warlock level-1 `Eldritch Invocation` choice
- class spell selection for the relevant spellcasting classes

### Example Start

```text
/create begin
/create choose species human
/create choose class wizard
/create choose class-skills arcana history
/create choose background acolyte
/create choose origin-feat magic-initiate
/create choose choice class:wizard:cantrips fire-bolt light mage-hand
/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person
/create ability generate point-buy 15 14 13 12 10 8
/create ability choose point-buy
/create ability assign 8 14 13 15 12 10
/create background-asi choose acolyte-int2-wis1
/create equipment background gold
/create equipment class package wizard-package-1
/create confirm
```

## Storytelling Mode

### Normal Flow

Use plain text, `/say`, or `/story` for ordinary roleplay declarations.
Use `/do` or `/improvise` when you want the backend to treat the input as an improvised action request.
When the runtime opens a deterministic check prompt, resolve it with `/check`.

Available storytelling commands:
- `/status`
- `/view`
- `/say <message>`
- `/story <message>`
- `/do <freeform improvised action>`
- `/improvise <freeform improvised action>`
- `/check`
- `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`
- `/shortrest <actor-id>`
- `/longrest <actor-id>`
- `/rest resume <actor-id>`
- `/hitdie <actor-id> [count]`
- `/time advance <minutes> [quiet|sleep|light|light-activity|exert|exertion]`
- `/time <quiet|sleep|light|light-activity|exert|exertion> <minutes>`

### Important Storytelling Rules

- Social, trap, and puzzle interactions are declaration-driven. Do not use `/social`, `/trap`, or `/puzzle` as player commands. State what your character says or does, and the backend will either resolve it directly or open a `/check` prompt.
- Story-mode spellcasting is backend-authoritative. Witnesses may perceive the cast, react according to local norms, and create immediate or delayed social fallout.
- Helpful, suspicious, or hostile acts are separated from witness perception and social consequence. An act can happen without everyone noticing it, and a noticed act can be tolerated or punished differently depending on the scene.
- Overt hostile acts can escalate into combat before the harmful action fully resolves.

### Story Declarations That Trigger Procedures

Examples:
- `I bargain with Gundren and ask for partial prepay for supplies.`
- `I search the ambush site for hidden dangers.`
- `I use my thieves' tools to disarm the snare.`
- `I study the tracks and follow the hidden trail.`
- `I examine the door and check for traps before touching it.`

## Travel, Exploration, Camp, And Downtime

### Travel Commands

- `/travel status`
- `/travel pace <cautious|normal|fast>`
- `/travel route <location-id>`
- `/travel route <q> <r>`
- `/travel advance [steps]`
- `/travel resume`
- `/travel engage`

Travel flow:
- Click a known hex to inspect it and preview a route.
- Use `/travel route ...` or the map route-preview flow to plan movement.
- Use `/travel advance` to move one or more steps.
- If travel is interrupted, use `/travel resume` after the interruption resolves.
- `DM only`: `/travel engage` resolves a pending travel hook directly from the toolbar or command box.

### Party Exploration State

- `/march status`
- `/march set <actor-id> <actor-id> ...`
- `/watch status`
- `/watch set <actor-id> <actor-id> ...`
- `/role status`
- `/role set <navigator|scout|lookout|search|study|sneak> [actor-id ...]`
- `/camp status`
- `/camp start`
- `/camp stop`

These states feed trap exposure, discovery order, watch/camp interruption logic, and travel/exploration procedure context.

### Downtime Commands

- `/downtime help`
- `/downtime status`
- `/downtime start <activity-id> [actor-id]`
- `/downtime work <project-id> <hours> [actor-id] [tool=<tool-name>]`
- `/downtime cancel <project-id>`

## Combat Mode

Combat slash commands are only available after the backend enters combat mode.

### Viewing And Turn Flow

- `/encounter start`
- `/encounter summary`
- `/initiative`
- `/view`
- `/status`
- `/endturn <actor-id>`
- `/turn end <actor-id>`

### Movement And Positioning

- `/move <actor-id> <x> <y> [z] [--allow-elevation|--allow-climb|--allow-fly]`
- `/climb <actor-id> <x> <y> [z]`
- `/fly <actor-id> <x> <y> <z>`
- `/stand <actor-id>`
- `/mount <actor-id> <mount-actor-id>`
- `/dismount <actor-id>`
- `/sense <actor-id> <familiar-id|off>`

### Attacks, Spells, Features, And Items

- `/attack <actor-id> <attack-id> <target-id>`
- `/attack <actor-id> <attack-id> <target-id> [--before <spec>] [--after <spec>]`
- `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`
- `/feature <actor-id> <capability-id> [target-id|x y [z]] [--key value ...]`
- `/use <actor-id> <capability-id> [target-id|x y [z]] [--key value ...]`

Attack interaction specs:
- `draw:item-id`
- `stow:item-id`
- `drop:item-id`
- `pickup:ground-item-id`

### Core Combat Actions

- `/dash <actor-id>`
- `/dash <actor-id> --bonus`
- `/disengage <actor-id>`
- `/dodge <actor-id>`
- `/help <actor-id> <target-id>`
- `/hide <actor-id>`
- `/search <actor-id>`
- `/study <actor-id>`
- `/grapple <actor-id> <target-id>`
- `/shove <actor-id> <target-id> <prone|push>`
- `/action dash <actor-id>`
- `/action dodge <actor-id>`

### Ready, Reactions, And Turn-Owned Prompts

- `/ready attack <actor-id> <trigger-actor-id> <attack-id>`
- `/ready cast <actor-id> <trigger-actor-id> <spell-id>`
- `/ready feature <actor-id> <trigger-actor-id> <capability-id>`
- `/ready move <actor-id> <trigger-actor-id> <x> <y> [z] [--allow-elevation|--allow-climb|--allow-fly]`
- `/react <actor-id> <option-id>`

Use `/react` only when the backend has opened a reaction or timing-choice window.
That includes real reactions and non-reaction prompt windows such as `Sneak Attack` application.

### Object Interaction, Equipment, And Improvised Actions

- `/equip <actor-id> <item-id> <main-hand|off-hand|armor>`
- `/interact <actor-id> <draw|stow|drop|pickup|transfer|don-shield|doff-shield|don-armor|doff-armor> <item-id|ground-item-id|source-actor-id>`
- `/interact <actor-id> <open|close|toggle|activate|deactivate> <object-id>`
- `/utilize <actor-id>`
- `/utilize <actor-id> <draw|stow|drop|pickup|transfer|don-shield|doff-shield|don-armor|doff-armor> <item-id|ground-item-id|source-actor-id>`
- `/utilize <actor-id> <open|close|toggle|activate|deactivate> <object-id>`
- `/improvise <actor-id> <target-id> <item:item-id|object:object-id> [--thrown] [--damage type] [--equivalent weapon-id]`

Equipment notes:
- player characters track `main hand`, `off hand`, and `armor` slots on the backend
- compatible carried starter gear is auto-equipped when the runtime actor is compiled
- long rest start clears equipped hand and armor slots
- `/equip ... main-hand|off-hand` does not spend an action in the current slice
- `/equip ... armor` uses the armor's backend equip time, currently 10 minutes for the loaded armor records
- one free object interaction is still tracked per turn for draw/stow/drop/pickup and related interactions
- a second interaction usually requires `Utilize`

### Rest And Time

- `/shortrest <actor-id>`
- `/longrest <actor-id>`
- `/rest resume <actor-id>`
- `/hitdie <actor-id> [count]`
- `/time advance <minutes> [quiet|sleep|light|light-activity|exert|exertion]`
- `/time <quiet|sleep|light|light-activity|exert|exertion> <minutes>`

## Spell And Feature Command Patterns

### Generic Spell Forms

- Self or untargeted cast:
  - `/cast player-1 shield`
  - `/cast player-1 detect-magic`
- Creature target:
  - `/cast player-1 cure-wounds player-1`
- Point target:
  - `/cast player-1 thunderwave 3 0`
- Ritual cast when supported:
  - `/cast player-1 detect-magic --ritual`

### Common Spell Parameters

The runtime uses `--key value` parameters for many spells and features.
Common keys now in use include:
- `--target`
- `--damage-type`
- `--material`
- `--mode`
- `--form`
- `--word`
- `--item`
- `--through`
- `--skill`
- `--effect`
- `--description`
- `--message`
- `--reply`
- `--amount`
- `--remove-condition`
- `--slot-level`
- `--exclude`

### Representative Spell Examples

- Bless or Bane with repeated targets:
  - `/cast player-1 bless player-1 --target player-2 --target player-3`
  - `/cast player-1 bane monster-skeleton-1 --target monster-mage-1`
- Costed material and damage choice:
  - `/cast player-1 chromatic-orb monster-skeleton-1 --damage-type fire --material diamond`
- Point-based area/zone:
  - `/cast player-1 alarm 2 3 --mode mental --form cube --exclude monster-mage-1`
  - `/cast player-1 burning-hands 3 0`
  - `/cast player-1 create-or-destroy-water 2 0 --mode create --container bucket`
  - `/cast player-1 entangle 4 5`
  - `/cast player-1 fog-cloud 4 5`
- Command word or similar spell-specific parameter:
  - `/cast player-1 command monster-skeleton-1 --word flee`
- Item or weapon-linked cantrip/spell:
  - `/cast player-1 shillelagh --item quarterstaff --damage-type force`
  - `/cast player-1 true-strike monster-skeleton-1 --item dagger --damage-type radiant`
- Story utility cantrip:
  - `/cast player-1 prestidigitation --effect clean-or-soil --description Clean the mud from Gundren's map case`
- Familiar and touch delivery:
  - `/cast player-1 find-familiar 1 0 --form owl --type celestial --material incense`
  - `/sense player-1 <familiar-actor-id>`
  - `/cast player-1 cure-wounds player-1 --through <familiar-actor-id>`
- Produce Flame follow-up:
  - `/cast player-1 produce-flame`
  - `/cast player-1 produce-flame monster-skeleton-1 --mode throw`
- Dancing Lights follow-up:
  - `/cast player-1 dancing-lights 1 1 --form lights`
  - `/cast player-1 dancing-lights 2 1 --mode move --form humanoid`
- Witch Bolt sustain:
  - `/cast player-1 witch-bolt monster-skeleton-1`
  - `/cast player-1 witch-bolt monster-skeleton-1 --mode sustain`

### Representative Feature Examples

- `/feature player-1 rage`
- `/feature player-1 second-wind`
- `/feature player-1 bardic-inspiration ally-1`
- `/feature player-1 lay-on-hands player-1 --amount 2`
- `/feature player-1 lay-on-hands player-1 --remove-condition poisoned`
- `/feature player-1 innate-sorcery`
- `/feature player-1 arcane-recovery --slot-level 1`

### Sneak Attack

`Sneak Attack` is not declared with `/feature` at the start of the turn.
Instead, when the rogue scores a qualifying hit, the backend opens a prompt window.
Use `/react <actor-id> <option-id>` to apply it.
It does not spend a reaction, but it is still once per turn and can trigger off-turn.

## Current XPHB Content Coverage

### Cantrips

All 34 XPHB cantrips are available.

`Deterministic-capability` cantrips:
- `Acid Splash`, `Blade Ward`, `Chill Touch`, `Dancing Lights`, `Eldritch Blast`, `Fire Bolt`, `Friends`, `Guidance`, `Light`, `Mage Hand`, `Mind Sliver`, `Minor Illusion`, `Poison Spray`, `Produce Flame`, `Ray of Frost`, `Resistance`, `Sacred Flame`, `Shillelagh`, `Shocking Grasp`, `Sorcerous Burst`, `Spare the Dying`, `Starry Wisp`, `Thorn Whip`, `Thunderclap`, `Toll the Dead`, `True Strike`, `Vicious Mockery`, `Word of Radiance`

`Story-adjudicated` cantrips:
- `Druidcraft`, `Elementalism`, `Mending`, `Message`, `Prestidigitation`, `Thaumaturgy`

### Level-1 Spells

All 64 XPHB level-1 spells are available.

`Story-adjudicated` level-1 spells:
- `Animal Friendship`, `Charm Person`, `Disguise Self`, `Illusory Script`, `Silent Image`

All other XPHB level-1 spells in the local manifests are currently `deterministic-capability`.

### Level-1 Class Features

All 33 XPHB base class features at level 1 are implemented, with required level-1 option families wired.

By class:
- Barbarian: `Rage`, `Unarmored Defense`, `Weapon Mastery`
- Bard: `Bardic Inspiration`, `Spellcasting`
- Cleric: `Spellcasting`, `Divine Order`
- Druid: `Druidic`, `Primal Order`, `Spellcasting`
- Fighter: `Fighting Style`, `Second Wind`, `Weapon Mastery`
- Monk: `Martial Arts`, `Unarmored Defense`
- Paladin: `Lay on Hands`, `Spellcasting`, `Weapon Mastery`
- Ranger: `Spellcasting`, `Favored Enemy`, `Weapon Mastery`
- Rogue: `Expertise`, `Sneak Attack`, `Thieves' Cant`, `Weapon Mastery`
- Sorcerer: `Spellcasting`, `Innate Sorcery`
- Warlock: `Eldritch Invocations`, `Pact Magic`, `Eldritch Invocation Options`
- Wizard: `Spellcasting`, `Ritual Adept`, `Arcane Recovery`

## Social Consequences And Campaign-Aware Story Fallout

The current story runtime now tracks more than immediate scene dialogue.
Concrete authored social content is active for the current Waterdeep / LMOP slice, including Gundren and Sildar scenes.

That means the runtime now tracks:
- who saw an act
- what they actually perceived
- how they interpreted it socially
- immediate suspicion, trust, fear, respect, gratitude, and attitude changes
- faction and authority memory
- delayed rumor/report propagation
- location-specific magical norms and decorum

Practical effect:
- helpful public magic can be tolerated or appreciated
- suspicious or manipulative magic can lower willingness in later conversations
- hostile public acts can schedule guard or authority follow-up
- delayed consequences can remain DM-only until the party learns about them

## Authority And Visibility Rules

The backend remains authoritative for:
- legality, randomness, action economy, and state transitions
- hidden information, witness knowledge, and social consequence state
- travel discovery, trap state, puzzle state, and downtime state
- spell/resource resolution, effects, concentration, and cleanup
- combat start, initiative, and encounter synthesis

Projection rules:
- DM sees full incident, witness, norm, and delayed-consequence state
- players see only what their characters should know
- hidden witnesses, quiet reports, and delayed authority attention do not leak early
- travel map projection remains DM-full and player-discovered only

## Notes On What To Use

For the current repo, the fastest reliable player workflow is:
1. Use the web UI action panel during character creation.
2. Use plain declarations in storytelling mode for social/trap/puzzle scenes.
3. Use `/travel ...` plus the hex map during overland movement.
4. Use deterministic slash commands in combat.
5. Use `/cast`, `/feature`, and `/use` with `--key value` parameters whenever the spell or feature needs extra detail.

