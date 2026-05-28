# Encounter Orchestrator Manual Test Guide

## What This Starts

This manual test runs three separate programs:

1. `system`
   - the authoritative encounter orchestrator
   - owns the canonical session state
   - resolves all actions and reactions
   - pushes filtered updates to connected controllers
   - boots the authored `Triboar Trail - Goblin Ambush` battlefield from `data/maps/goblin_ambush_triboar_trail_map.json`

2. `dm`
   - may control only monster actors
   - may end monster turns
   - sees public encounter state plus monster-private state

3. `player-1-controller`
   - may control only `player-1`
   - sees public encounter state plus private state for `player-1`
   - cannot control monsters and cannot see monster-private state

The rules engine remains the sole authority for legality, action economy, movement, reactions, HP, turn state, and battlefield queries.

## Start The System

Open a terminal in the repo root and run:

```powershell
python user-test/encounter_system_server.py --port 8765
```

What this does:
- starts the authoritative server on `127.0.0.1:8765`
- builds the configured-mirror-backed encounter session
- loads the authored goblin ambush battlefield into canonical encounter state
- auto-starts the encounter unless `--no-auto-start` is passed

If you want a different port:

```powershell
python user-test/encounter_system_server.py --port 9000
```

## Start The DM Program

Open a second terminal and run:

```powershell
python user-test/encounter_dm_client.py --port 8765
```

This connects as controller id `dm`.

## Start The Player Program

Open a third terminal and run:

```powershell
python user-test/encounter_player_client.py --port 8765
```

This connects as controller id `player-1-controller`.

## What Each Side Can Do

### DM can do
- control monster actors only
- examples:
  - `/move monster-skeleton-1 1 0`
  - `/move monster-skeleton-1 11 9 --allow-elevation`
  - `/climb monster-skeleton-1 10 13`
  - `/attack monster-skeleton-1 shortsword player-1`
  - `/dash monster-skeleton-1`
  - `/endturn monster-skeleton-1`

### Player can do
- control only `player-1`
- examples:
  - `/move player-1 3 0`
  - `/move player-1 11 9 --allow-elevation`
  - `/climb player-1 10 13`
  - `/attack player-1 unarmed-strike monster-skeleton-1`
  - `/dash player-1`
  - `/stand player-1`
  - `/endturn player-1`

### System does
- starts the encounter
- owns all state mutation
- resolves legality and action results
- sends updates to DM and player programs
- sends reaction prompts only to the controller that owns the reacting actor
- returns movement clarifications when elevation intent is missing

## What Each Side Can See

### Everyone sees public battlefield state
- battlefield name and map id
- turn order and active actor
- public actor names and positions
- tile terrain and elevation in actor summaries
- public recent combat events

### Player additionally sees
- full private details for `player-1`

### Player does not see
- monster HP
- monster AC
- monster action economy details
- monster-only legal action menu

### DM additionally sees
- full private details for monster actors
- monster legal action and attack menus

### DM does not control
- player actors by default

## Basic Interaction Loop

Movement targets use absolute authored-map coordinates.
`/move` is same-plane by default. If the target requires changing elevation, the system returns a clarification instead of silently taking a slope, ramp, or climb.

### DM terminal
After connect, enter commands like:

```text
/move monster-skeleton-1 1 0
/endturn monster-skeleton-1
/endturn monster-mage-1
```

### Player terminal
After the DM ends the monster turns, enter:

```text
/move player-1 3 0
```

If that movement leaves a monster's reach, the owning controller gets a reaction prompt automatically. If the destination is on another elevation plane, the system explains whether the route is a slope/ramp traversal or a climb traversal and waits for an explicit `--allow-elevation`, `--allow-climb`, or `/climb` command.

## Elevation Clarification Examples

- `/move player-1 10 13`
  - same-plane by default
  - if the destination needs elevation change, the system returns a clarification preview instead of moving
- `/move player-1 11 9 --allow-elevation`
  - confirms a slope or ramp route
- `/climb player-1 10 13`
  - confirms a climb route
- `/move player-1 10 13 --allow-climb`
  - explicit climb confirmation using the same move command

## Reaction Prompts

When a reaction window opens, the owning controller sees something like:

```text
[player-1-controller reaction prompt] ...
  1. ...
  2. ...
  0. Decline
```

or on the DM side for a monster reaction.

To answer a prompt:
- type `1` to choose the first option
- type `1,2` to choose multiple legal reactions from the same prompt
- type the explicit option id if you prefer
- type `decline` or `0` to decline

Reaction responses are sent back to the system, and the system continues resolution.
After the response, check the `Recent events:` section in the refreshed view to see which attack or reaction actually resolved.

## Example Three-Terminal Flow

### Terminal 1: system
```powershell
python user-test/encounter_system_server.py --port 8765
```

### Terminal 2: DM
```powershell
python user-test/encounter_dm_client.py --port 8765
```
Then enter:
```text
/move monster-skeleton-1 1 0
/endturn monster-skeleton-1
/endturn monster-mage-1
```

### Terminal 3: player
```powershell
python user-test/encounter_player_client.py --port 8765
```
Then enter:
```text
/move player-1 3 0
```

At that point:
- the player sees their own state plus public monster info
- the DM sees monster-private state
- if an opportunity attack is available, the owning controller receives the reaction prompt
- the system resolves the result after the controller answers
- the refreshed view shows the public attack outcome in `Recent events:`

## Example Ownership Rejection

If the player tries to control a monster:

```text
/dash monster-skeleton-1
```

The server rejects it with an ownership error.

If the DM tries to control the player character:

```text
/endturn player-1
```

The server rejects that too unless DM override is explicitly added and enabled in a future change.

## Non-Interactive Batch Mode

The generic controller client also supports scripted input:

```powershell
python user-test/encounter_controller_client.py --controller-id dm --port 8765 --command "/move monster-skeleton-1 1 0"
```

or:

```powershell
python user-test/encounter_controller_client.py --controller-id player-1-controller --port 8765 --commands-file commands.txt
```

The wrapper entrypoints are:
- `python user-test/encounter_dm_client.py --port 8765`
- `python user-test/encounter_player_client.py --port 8765`

## Stop The Programs

- In the DM or player terminal, type `exit` or `quit`
- In the system terminal, press `Ctrl+C`

## Notes

- This is a localhost manual-test system, not a production multiplayer service.
- It uses the configured local 5etools mirror through the existing bootstrap path.
- The system process is the only authority for encounter resolution.


3D update:
- Public positions are now rendered as `(x,y,z)` where `z` is altitude in feet.
- `/move actor x y` still means same-plane movement by default.
- `/move actor x y z --allow-fly` or `/fly actor x y z` explicitly requests a flying destination in airspace.
- `/move actor x y --allow-elevation` and `/climb actor x y` still handle surface/climb traversal on the authored map.
