# DnD Agents Simulation

This branch contains a new D&D simulation built from the core idea of the original project: a party of player controllers, an AI-assisted DM, and an authoritative rules engine sharing one evolving tabletop state. It is not a direct continuation of the original prototype. The new version rebuilds the simulation around deterministic state transitions, explicit controller actions, browser-based multi-user play, local 5e rules data, and cleaner boundaries between rules, campaign content, and LLM narration.

The bundled demo uses Lost Mine of Phandelver because it is a familiar starter adventure with useful social, exploration, and combat beats. The simulation is intended to support many plots, not only LMOP. To run a different plot, the system needs campaign content, scene data, maps or fallback encounter plans, NPC/context memory, and an appropriate bootstrap script. The rules engine and character/monster content are deliberately kept separate from the LMOP campaign layer so future campaigns can reuse the same simulation core.

## Requirements

- Windows PowerShell or another terminal that can run Python commands
- Python 3.12 or newer
- The `websockets` Python package:

```powershell
python -m pip install websockets
```

Run all commands below from the repository root.

## 1. Download The Resource Pack

Download the resource pack from Google Drive:

https://drive.google.com/file/d/1RZ6Vc5TtxdXETBc-8vO-KNNxDurkV3FC/view?usp=sharing

Unzip it into the repository root. After unzipping, this folder should exist next to `user-test`, `character_creation`, and `session_server`:

```text
5etools-mirror-2.github.io/
```

If the zip creates an extra wrapper directory, move `5etools-mirror-2.github.io` up to the repository root.

## 2. Create `.env`

Create a `.env` file in the repository root. The mirror path can be relative to the repository root; keep the trailing slash.

```env
DND_DETERMINISTIC_SEED=20260401-character-creation-kernel
FIVEETOOLS_MIRROR_BASE_URL=5etools-mirror-2.github.io/
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_RESPONSES_MODEL=deepseek-v4-flash
OPENAI_API_FORMAT=chat_completions
```

Adjust `FIVEETOOLS_MIRROR_BASE_URL` only if you unzip the mirror somewhere else. Plain relative paths, absolute Windows paths, and `file://` URLs are supported. Do not commit `.env`; it contains your API key and is ignored by git.

## 3. Start The Web Demo

Start the server from the repository root:

```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767 --env-path .env --start-in-character-creation --save-characters user-test\saved-characters\lmop-party.json
```

Keep this terminal open while using the demo. The server prints the HTTP URL, WebSocket URL, and join tokens. By default, the browser app is available at:

```text
http://127.0.0.1:8000
```

Stop the server with `Ctrl+C`.

### Loading Saved Characters

For training runs, create the party once and save it with `--save-characters`. The file is updated as players confirm characters, and the parent folder is created automatically.

After the party has been saved, future runs can skip character creation and start the story immediately:

```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767 --env-path .env --load-characters user-test\saved-characters\lmop-party.json
```

Saved party files are keyed by controller id, so the same `player-1-controller` through `player-4-controller` slots are restored every time. The suggested `user-test/saved-characters/` folder is ignored by git.

### Mixing Human And LLM Players

The web server can let some player controllers be driven by LLMs while the rest remain normal browser-controlled human players. Each LLM player uses its own env file, so different player slots can use different providers or models.

Create one env file per LLM player, for example:

```env
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_RESPONSES_MODEL=deepseek-v4-flash
OPENAI_API_FORMAT=chat_completions
```

Then assign env files to player controllers with repeated `--llm-player` flags:

```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767 --env-path .env --load-characters user-test\saved-characters\lmop-party.json --llm-player player-1-controller=user-test\llm-players\deepseek.env --llm-player player-2-controller=user-test\llm-players\chatgpt.env
```

In that example, `player-1-controller` and `player-2-controller` are LLM-driven, while `player-3-controller` and `player-4-controller` can still be opened by humans in the browser. LLM players submit commands through the same action path as human players. In storytelling they use `/say`, `/do`, `/story`, or `/check`; in combat they can use visible slash-command actions and fall back to ending their turn if uncertain.

By default, the server lets at most one LLM player action run after each web input. Increase that for more autonomous training runs:

```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767 --env-path .env --load-characters user-test\saved-characters\lmop-party.json --llm-player player-1-controller=user-test\llm-players\deepseek.env --llm-player-max-actions-per-pump 4
```

Use `--disable-llm-player-autopump` if you want to configure LLM players without automatically submitting their actions. Env files are ignored by git, but keep API keys out of committed docs and scripts.

## 4. Open The Web UIs

Open `http://127.0.0.1:8000` in a browser. The page lists quick portal links for each controller:

- `dm`
- `player-1-controller`
- `player-2-controller`
- `player-3-controller`
- `player-4-controller`

Click a portal link to auto-connect as that controller. If you connect manually, use the matching token printed by the server. The default token format is `<controller-id>-token`, for example `player-1-controller-token`.

## 5. Character Creation Flow

Because the server was started with `--start-in-character-creation`, all four player controllers begin in character creation. The DM controller can watch progress, but does not create a character.

Each player should use the command box to send `/create ...` commands. The right-side action panel shows the available option ids for the current step. For most options, click `Insert command` to put the correct command into the command box, then send it. For multi-choice steps, keep inserting option ids until the command contains the required number of choices, then send it.

The summary panel tells you the current phase and the next command shape. It also shows important prompts such as:

- how many options to choose for multi-choice steps
- the ability assignment order: `STR DEX CON INT WIS CHA`
- the ability assignment command, such as `/create ability assign 8 14 13 15 12 10`
- the final confirmation command: `/create confirm`

A compact example character creation sequence is:

```text
/create begin
/create choose species aasimar
/create choose class wizard
/create choose class-skills Arcana History
/create choose background acolyte
/create choose choice class:wizard:cantrips fire-bolt mage-hand light
/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person
/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS
/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance
/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds
/create ability generate point-buy 15 14 13 12 10 8
/create ability assign 8 14 13 15 12 10
/create background-asi choose acolyte-wis2-cha1
/create equipment background gold
/create equipment class package wizard-package-1
/create confirm
```

The exact available choices depend on the selected species, class, background, and feature choices. Prefer the action panel ids over copying this example blindly.

## 6. Story And Combat UI

After all four players confirm characters, the session moves into the story demo.

Use the command box for normal play. Players can type natural language directly, or use commands such as:

```text
/say We ask Gundren what he needs delivered.
/do I inspect the wagon and check the cargo list.
/story We accept the job and prepare to leave Waterdeep.
```

When the DM requests a story check, the owning player sees a prompt. Click the `/check` button or type:

```text
/check
```

If the story enters combat, the combat map and action panel become active. Use action buttons to insert or propose attacks, movement, spells, features, and turn-ending commands. Some actions require choosing a target on the map after selecting the action.

## Troubleshooting

- If startup fails while loading rules data, check that `FIVEETOOLS_MIRROR_BASE_URL` points to the unzipped `5etools-mirror-2.github.io/` folder and ends with `/`.
- If the browser cannot connect, make sure the server terminal is still running and that the page uses `ws://127.0.0.1:8767`.
- If an LLM call fails, confirm `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_RESPONSES_MODEL`, and `OPENAI_API_FORMAT` in `.env`.
- If port `8000` or `8767` is already in use, restart with different `--http-port` or `--ws-port` values.
