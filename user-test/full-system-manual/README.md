# Full System Manual Test

This folder is the direct manual-test entrypoint for the current encounter system. The system server boots onto the authored `Triboar Trail - Goblin Ambush` battlefield from `data/maps/goblin_ambush_triboar_trail_map.json`.
Use three separate terminals:
- one for the authoritative system process
- one for the DM controller
- one for the player controller

Current default session
- 1 DM controller: `dm`
- 1 player controller: `player-1-controller`
- 1 player character: `player-1`
- 2 monsters owned by the DM: `monster-skeleton-1`, `monster-mage-1`

What the live view now shows
- battlefield name, map id, grid size, and spawn-zone summary
- public actor positions on the authored map
- tile terrain and elevation on each actor line
- recent public combat events, including resolved reaction attacks
- movement clarification errors when a destination requires explicit elevation intent

## 1. Start the system

From a PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-system.ps1
```

The system starts the encounter automatically and becomes the source of truth for all state changes.
Leave this terminal running.

## 2. Start the DM client

Open a second PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-dm.ps1
```

The DM can control only monster actors.
The DM sees public state plus monster-private state.

## 3. Start the player client

Open a third PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-player1.ps1
```

The player can control only `player-1`.
The player sees public state plus their own private state.

## 4. Interactive commands

Type commands directly at the `>` prompt in the DM or player terminal.
Movement targets use absolute grid coordinates from the authored map.
`/move` means same-plane movement by default. If the destination requires elevation change, the system returns a clarification instead of silently taking a slope, ramp, or climb.

Useful player commands

```text
/move player-1 1 0
/move player-1 11 9 --allow-elevation
/climb player-1 10 13
/attack player-1 quarterstaff monster-skeleton-1
/stand player-1
/endturn player-1
```

Useful DM commands

```text
/move monster-skeleton-1 5 0
/move monster-skeleton-1 11 9 --allow-elevation
/climb monster-skeleton-1 10 13
/attack monster-skeleton-1 shortsword player-1
/endturn monster-skeleton-1
/endturn monster-mage-1
```

## 5. Elevation-aware movement

When movement needs a higher or lower plane:
- `/move actor x y` means stay on the current plane unless the destination is reachable without elevation change
- if elevation change is required, the system tells you whether the path is a slope/ramp traversal or a climb traversal
- use `/move actor x y --allow-elevation` to confirm a slope or ramp route
- use `/move actor x y --allow-climb` or `/climb actor x y` to confirm a climb route
- if the edge is blocked or the movement cost is too high, the system returns an explicit reason instead of guessing

## 6. Reaction prompts

When a reaction prompt appears, type one of:
- `1` for the first legal option
- `1,2` to choose multiple legal options shown in the same prompt
- the full option id shown in brackets
- `0` or `decline`

The client translates numeric selections to the real server option ids.
A single actor can still use only one reaction, but a batch reply can accept reactions from multiple reacting actors in the same window.

## 7. Suggested first test flow

Player/DM/system startup
1. Start `start-system.ps1`
2. Start `start-dm.ps1`
3. Start `start-player1.ps1`

Basic authored-map flow
1. In the DM terminal, if it is the skeleton's turn, type `/endturn monster-skeleton-1`
2. In the DM terminal, type `/endturn monster-mage-1`
3. In the player terminal, type `/move player-1 1 0`
4. In the player terminal, type `/attack player-1 quarterstaff monster-skeleton-1`
5. In the player terminal, type `/endturn player-1`
6. In the DM terminal, continue monster turns

Elevation clarification flow
1. Put `player-1` on the lower road near the shelf
2. In the player terminal, type `/move player-1 10 13`
3. The system should reject the move with a clarification showing that elevation change is required
4. Retry with `/move player-1 10 13 --allow-elevation` if the route is a slope/ramp, or `/climb player-1 10 13` if the route requires a climb

Reaction test flow
1. Advance until `player-1` is adjacent to `monster-skeleton-1`
2. In the player terminal, move away with `/move player-1 3 0`
3. The owning controller receives an opportunity-attack prompt automatically
4. Type `1` to accept, `0` to decline, or a comma-separated selection if multiple reactors are listed
5. Check `Recent events:` in the refreshed view to confirm which attack fired and whether it hit

Map behavior to watch for
- the encounter view should show `Battlefield: Triboar Trail - Goblin Ambush`
- actor lines include tile terrain and elevation, for example `Tile lower_road @ 0 ft`
- `/move player-1 x y` stays on the current plane by default and does not silently climb
- use `--allow-elevation` for the authored ramp/slope route and `/climb` or `--allow-climb` for explicit climb traversal
- movement between the road and upper shelves is not silently climbed; direct embankment traversal requires explicit climb confirmation, while the authored northeast path is the traversable non-climb route
- dead horses block occupancy and tree blockers affect LOS, LOE, and cover

## 8. Alternate ports

If port `8765` is busy, use the same port value in every terminal.

```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-system.ps1 -Port 9000
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-dm.ps1 -Port 9000
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-player1.ps1 -Port 9000
```

## 9. Generic controller launcher

If you later add more controllers to the bootstrap session, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-system-manual\start-controller.ps1 -ControllerId some-controller-id
```


3D update:
- Public positions are now rendered as `(x,y,z)` where `z` is altitude in feet.
- `/move actor x y` still means same-plane movement by default.
- `/move actor x y z --allow-fly` or `/fly actor x y z` explicitly requests a flying destination in airspace.
- `/move actor x y --allow-elevation` and `/climb actor x y` still handle surface/climb traversal on the authored map.
