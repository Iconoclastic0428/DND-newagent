# Full Story Demo

This demo runs one authoritative `system` process plus five controller terminals:
- `dm`
- `player-1-controller`
- `player-2-controller`
- `player-3-controller`
- `player-4-controller`

The updated flow starts in deterministic character creation for all four players. After all four characters are confirmed, the session automatically hands off into the LMOP story demo in Waterdeep. The demo ends when the goblin ambush is resolved: either the party survives the ambush or all player characters are defeated.
This creation-to-campaign orchestration lives in the manual harness at `user-test/story_demo_system_server.py`, so you can launch and test it directly through the `user-test/full-story-demo` scripts.

## Start The Demo

Open six PowerShell terminals from repo root.

Terminal 1:
```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-system.ps1
```

Terminal 2:
```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-dm.ps1
```

Terminal 3:
```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-player1.ps1
```

Terminal 4:
```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-player2.ps1
```

Terminal 5:
```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-player3.ps1
```

Terminal 6:
```powershell
powershell -ExecutionPolicy Bypass -File .\user-test\full-story-demo\start-player4.ps1
```

Default port is `8766` for the story demo so it does not collide with the older combat-only demo. Use `-Port <n>` on every launcher if you want a different port.

## Phase 1: Character Creation

During setup, each player must complete deterministic character creation with `/create ...` commands. The DM watches progress but does not create a character.

A compact working example for each player is:
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
/create background-asi choose acolyte-int2-wis1
/create equipment background gold
/create equipment class package wizard-package-1
/create confirm
```

Important rules:
- the campaign does not start until all four players have confirmed characters
- the DM terminal only observes during creation
- `/view` or `/status` refreshes the synced creation summary at any time

## Phase 2: Storytelling Mode

After the fourth `/create confirm`, the server automatically starts the campaign in Waterdeep with Gundren Rockseeker. The DM is LLM-driven during storytelling. Players talk in plain text or use `/say ...`, `/story ...`, or `/do ...`.

Examples:
```text
We sit down with Gundren and ask what the job pays.
I ask Sildar how dangerous the road has been.
/do I inspect the cargo list and the route notes.
/story We accept the job and start planning watches for the road.
```

While the LLM DM is reasoning, the acting player sees `[info] DM is thinking...` and the DM terminal receives a live `[thinking]` stream from the model. The final narration still comes back through the typed storytelling runtime before any state is committed.

## Story Checks

If the DM runtime decides a check is required, only the owning player gets a prompt.

Example prompt:
```text
[player-1-controller prompt:story-check] Make a Wisdom (Insight) check to read what Gundren is holding back.
DC: 12.
Type `/check` to resolve the requested check through the rules engine.
```

Resolve it with:
```text
/check
```

Storytelling rule:
- a player can receive at most one DM-issued story check per scene
- after that check resolves, the DM runtime must narrate consequences or move the scene forward instead of issuing another story check to the same actor in that same scene

## Combat Handoff

When the DM runtime decides timing now matters, it enters combat through the authoritative rules engine. Initiative is rolled by the system, not by the LLM.

After that point:
- players can only control their own PCs
- the DM can only control the goblin ambushers
- use the normal combat slash commands such as `/move`, `/attack`, `/cast`, `/feature`, `/use`, `/stand`, and `/endturn`

## Demo End Condition

The demo ends automatically when the goblin ambush is resolved.

End states:
- party victory: the party survived the goblin ambush
- party defeat: the goblin ambush defeated the party

After that, all controllers see a final synced `demo-complete` state and the server refuses further play commands until you restart the demo.

## Ownership Rules

- `player-1-controller` can only control `player-1`
- `player-2-controller` can only control `player-2`
- `player-3-controller` can only control `player-3`
- `player-4-controller` can only control `player-4`
- `dm` can only control the goblin ambushers in combat
- all narration, checks, mode switching, initiative start, and demo completion are system/DM-runtime driven

## Replay Scripts

The repo now includes authored end-to-end replay scripts that drive the full manual demo wrapper through character creation, Waterdeep story play, travel, and the goblin ambush.

Available scripts:
- `user-test/full-story-demo/scripts/lmop-friendly-full-run.json`
- `user-test/full-story-demo/scripts/lmop-unfriendly-full-run.json`

Run one with:
```powershell
python user-test/story_demo_replay.py --script user-test/full-story-demo/scripts/lmop-friendly-full-run.json --env-path .env --verbose
```

The replay runner uses queued LLM JSON payloads embedded in the script file, so it exercises the real authoritative session path without depending on a live networked model response.

## Live Web UI Script Driver

If you want the browser UI to show the run as if the players are typing in their own portals, use the browser demo server plus the live web runner instead of the in-memory replay harness. The browser server now precreates the four default characters and starts in Waterdeep story mode by default.

1. Start the browser demo server:
```powershell
python user-test\web_story_demo_server.py --host 127.0.0.1 --http-port 8000 --ws-port 8767 --env-path .env --start-in-character-creation
```

Omit `--start-in-character-creation` for normal browser play, where the four default characters are already created when the portals load.

2. Open the browser portals you want to watch:
- `http://127.0.0.1:8000/?portal=dm&autoconnect=1`
- `http://127.0.0.1:8000/?portal=player-1-controller&autoconnect=1`
- `http://127.0.0.1:8000/?portal=player-2-controller&autoconnect=1`
- `http://127.0.0.1:8000/?portal=player-3-controller&autoconnect=1`
- `http://127.0.0.1:8000/?portal=player-4-controller&autoconnect=1`

3. Run the live browser script driver:
```powershell
python user-test\web_story_demo_live_runner.py --base-url http://127.0.0.1:8000 --script user-test/full-story-demo/scripts/lmop-friendly-live-web-run.json --verbose
```

Behavior:
- the browser remains the active websocket client for each controller
- the live runner injects controller input through the local automation API instead of taking over the controller connection
- the DM narration and `[thinking]` feedback come from the running server's real LLM configuration in `.env`, not from queued script payloads
- the chat log, prompts, and map updates appear in the browser in real time as the script advances
- if your model or network is slow, increase `--request-timeout-seconds` or set `--request-timeout-seconds 0` to disable the HTTP request timeout for injected commands

## Four-Player Agent Connector

If you want four autonomous player agents to take over from the precreated story start, use the party connector against the same browser demo server:

```powershell
python user-test\web_story_demo_party_connector.py --base-url http://127.0.0.1:8000 --env-path .env --verbose
```

Behavior:
- the connector waits until the browser session is out of the character-creation phase before acting
- each player uses a fixed personality and conversational focus instead of sharing one generic voice
- the connector feeds each player only that controller's visible browser snapshot, including recent chat history and prior visible check results
- storytelling turns run one player at a time in round-robin order so players can build on the previous turn without talking over each other
- if a player prompt is active, the connector routes control directly to that player before asking for any new freeform turn
- combat player turns stay player-owned, while DM monster turns can be auto-passed to keep the demo moving

## DeepSeek Web DM + Four Players

For the local DeepSeek setup, the helper scripts in `user-test/full-story-demo/scripts` keep the commands consistent with the checked-in `.env` and `user-test/llm-players/deepseek-v4-flash-player.env`.

Start the web server with DeepSeek as the DM:

```powershell
.\user-test\full-story-demo\scripts\start-deepseek-web-server.ps1
```

Then open:

```text
http://127.0.0.1:8000/?portal=dm&autoconnect=1
```

In a second terminal, start the four autonomous DeepSeek player agents:

```powershell
.\user-test\full-story-demo\scripts\run-deepseek-party-connector.ps1
```

If you want the web server itself to own the four built-in `LLMPlayerAgent` controllers instead of using the external party connector, start it with:

```powershell
.\user-test\full-story-demo\scripts\start-deepseek-web-server.ps1 -ServerSidePlayers
```

Use either the external party connector or `-ServerSidePlayers` for a run, not both, unless you are deliberately testing duplicate player drivers. Both paths use DeepSeek-compatible chat completions through the local env files and write trajectory/transcript artifacts under `C:\tmp\dnd-web-deepseek-demo-20260514` by default.

## One-Command DeepSeek RL Pipeline

To run the real web all-LLM setup and immediately turn the LLM-produced trajectory into RL artifacts, run this from repo root:

```powershell
.\user-test\full-story-demo\scripts\run-deepseek-rl-pipeline.ps1
```

This starts the browser web server with DeepSeek as the DM, runs the four autonomous DeepSeek player agents, stops the server, then writes the same downstream artifacts used by the training pipeline:
- `web-trajectories/**/trajectory.jsonl`: raw turn/event records from the web session
- `deepseek-party-transcript.md`: readable public/player transcript
- `batches/**/batch_report.json`: batch summary for the all-LLM run
- `batches/**/training_transitions.jsonl`: player turns exported for supervised/RL training
- `batches/**/preference_pairs.jsonl`: preference pairs derived from rewards
- `datasets/`: combined dataset collection and quality reports
- `readiness/training_readiness.md`: training readiness summary
- `smoke/`, `recipes/`, `training-runs/`: local smoke, recipe, baseline, and command-head preflight outputs
- `mosaicml-plans/**/mosaicml_training_plan.json`: GPU handoff plan for MosaicML

Preview the exact commands and output folder without making model calls:

```powershell
.\user-test\full-story-demo\scripts\run-deepseek-rl-pipeline.ps1 -DryRun
```

The full run sends the current web demo campaign/runtime context to DeepSeek through `.env` for DM narration and through `user-test/llm-players/deepseek-v4-flash-player.env` for player actions. Increase `-MaxActions` for a longer data-producing run.
When the command prints the web URL, open it to watch the DM and players live; the runner waits five seconds before starting the party connector by default. Use `-PreConnectorDelaySeconds 0` if you do not need that pause.

## Stop The Demo

Close the controller terminals or type `exit`. Stop the system terminal with `Ctrl+C`.
