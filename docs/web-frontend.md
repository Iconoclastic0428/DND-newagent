# Web Frontend

## Overview
- The Python backend remains authoritative for rules, legality, randomness, initiative, movement, HP, conditions, prompts, and DM runtime decisions.
- The browser client is only a synchronized view and interaction surface.
- No `.env` LLM secrets are exposed to the frontend bundle.
- The browser demo now reuses the manual full-story-demo harness, so play starts in four-player character creation and then hands off automatically into the LMOP story and ambush.

## Package Structure
- `session_server/web_server.py`: authoritative HTTP + WebSocket server for browser clients.
- `session_server/web_projection.py`: explicit backend-to-frontend projection layer.
- `shared_types/web_ui.py`: typed browser-safe view models.
- `web_frontend/index.html`: browser shell.
- `web_frontend/app.js`: realtime client logic and semantic map interactions.
- `web_frontend/styles.css`: semantic map and UI styling.
- `user-test/web_story_demo_server.py`: manual full-story-demo web launcher.
- `user-test/story_demo_system_server.py`: authoritative manual demo wrapper that owns character creation before story handoff.

## Run The Web Demo
1. Start the backend web demo server:

```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767
```

2. Open the browser at:

```text
http://127.0.0.1:8000
```

3. Join manually from the main page, or use one of the quick portal URLs:
- DM: `http://127.0.0.1:8000/?portal=dm&autoconnect=1`
- Player 1: `http://127.0.0.1:8000/?portal=player-1-controller&autoconnect=1`
- Player 2: `http://127.0.0.1:8000/?portal=player-2-controller&autoconnect=1`
- Player 3: `http://127.0.0.1:8000/?portal=player-3-controller&autoconnect=1`
- Player 4: `http://127.0.0.1:8000/?portal=player-4-controller&autoconnect=1`

4. The default controller tokens are still:
- `dm` -> `dm-token`
- `player-1-controller` -> `player-1-controller-token`
- `player-2-controller` -> `player-2-controller-token`
- `player-3-controller` -> `player-3-controller-token`
- `player-4-controller` -> `player-4-controller-token`

## Live Script Injection
- The user-test browser launcher now also exposes a local automation API on the same HTTP port.
- `user-test/web_story_demo_live_runner.py` can drive a running browser session through that API without replacing the browser websocket for any controller.
- `user-test/web_story_demo_party_connector.py` can use that same API to run four autonomous player agents after character creation while the browser remains the visible UI.
- This is the path to use when you want the web UI to show a scripted full-story run while the DM runtime still uses the live `.env` model configuration instead of queued fake LLM payloads.

Example:
```powershell
python user-test\web_story_demo_live_runner.py --base-url http://127.0.0.1:8000 --script user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json --verbose
```

If a real DM turn can take longer than expected, raise `--request-timeout-seconds` or set it to `0` to disable the HTTP timeout for injected live-web commands.

Four-player agent example:
```powershell
python user-test\web_story_demo_party_connector.py --base-url http://127.0.0.1:8000 --env-path .env --verbose
```

The party connector keeps one player voice per controller, feeds each player only its visible history/check context, answers player-owned prompts through the automation API, and prevents immediate topic duplication across sequential story turns.

## What The Frontend Shows
- Realtime mode badge: `character-creation`, `storytelling`, `combat`, or the final demo-complete state.
- Semantic map: either the combat battlefield or the LMOP exploration hex map, depending on the current authoritative mode.
- Inspection panel: coordinates, terrain semantics, traversability, cover, blockers, movement previews, and teleport legality.
- Chat/narration log: DM narration, story transcript, combat log, and system feedback.
- Character card sidebar: controller-aware player card projection with core stats, abilities, skills, attacks, spellcasting, resources, conditions, active effects, and explicit `main hand` / `off hand` / `armor` slot lines.
- Action panel: backend-projected legal actions during combat, plus creation-time choice pools when the current `/create` step exposes option ids. During character creation, each option now offers both `Insert id` and `Insert command` helpers.
- Prompt panel: reaction prompts and story-check prompts.

## Semantic Map Layers
- In combat, the map uses the battlefield semantic grid: terrain class, blockers, difficult terrain, elevation, features, and token positions.
- In storytelling travel, the map switches to the exploration hex map: discovered hexes, current party position, known landmarks, pace-aware route preview, and the currently planned route.
- Player controllers see only discovered travel hexes and revealed landmarks; the DM sees the full travel map and hidden LMOP hooks.
- Clicking a cell or hex opens semantic inspection. In combat, owned active actors also get path preview. In travel, the clicked hex also requests a route preview to that destination.
- If the map is larger than the viewport, hold the right mouse button and drag to pan the map viewport.

## Character Card Sidebar
- The backend projects a typed `character_cards` view model from authoritative runtime actor state plus the compiled `CharacterRecord`.
- Players receive full card detail only for the actor ids they own.
- The DM receives inspection cards for all player characters.
- The browser never becomes the source of truth for HP, conditions, resources, spells, or action economy.
- In storytelling mode the card stays visible for identity, abilities, skills, equipment, spellcasting, and current effects.
- The equipment section now shows explicit `main hand`, `off hand`, and `armor` slot lines, and the displayed AC comes from that authoritative equipped state.
- In combat mode the same card additionally surfaces movement remaining, action/bonus/reaction availability, active-turn state, attacks, and live combat resources.
- Card updates arrive through the same websocket view push used for the map, prompts, and chat, so HP, conditions, concentration, spell slots, and limited-use resources update without refresh.

## Access Control
- Player clients do not receive another player's full private character card payload.
- DM inspection is projection-based; it does not change the underlying authority boundary.
- Hidden backend-only state and `.env` secrets remain server-side and are never included in the browser config or card payloads.

## Interaction Model
- Character creation uses the same command box as the terminal demo. Enter deterministic `/create ...` commands until all four players confirm.
- Freeform declarations and slash commands go through the chat box after character creation hands off into storytelling.
- In storytelling travel, click a known hex to inspect it and preview a route. Use the map toolbar to change pace, advance one step, resume after an interruption, or engage a pending hook as the DM.
- In combat, clicking a tile inspects it, and reachable tiles also get a movement preview for the active owned actor.
- Clicking an action with targeting enters target-selection mode; the browser submits a proposal, and the backend validates it.
- The map never mutates state directly; only backend-approved results are rendered.

## Authority Boundary
- Backend only:
  - rules execution
  - legality checks
  - initiative and turn order
  - HP/resource mutation
  - prompts and reactions
  - LLM calls and `.env` secrets
- Frontend only:
  - rendering
  - local selection state
  - command/declaration submission
  - prompt responses

## Current Scope
- The web launcher now follows the same manual demo path as `user-test/full-story-demo`: four players create characters first, then the campaign begins automatically.
- The first exploration travel fixture is LMOP-specific and covers Waterdeep -> High Road -> Triboar Trail -> Phandalin, including the goblin ambush interruption hook and the hidden Cragmaw trail reveal hook.
- The frontend is semantic-first and intentionally uses backend-derived map data instead of client-only art logic.
- Browser UI is static HTML/CSS/JS served by Python. No Node or frontend build step is required in the current repo.
