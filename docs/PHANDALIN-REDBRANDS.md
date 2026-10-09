# Phandalin / Redbrand playable slice

## Where the work lives

- Branch: `codex/phandalin-redbrands`.
- Worktree: `C:/Users/Shengqi Li/.codex/worktrees/workflow-naacl-review/DND-newagent`.
- The original dirty checkout at `D:/DND-newagent` is preserved. Publication history is recorded in `tasks/SUMMARIES.md`; this feature is kept on its own branch rather than merged into the original checkout.
- This implementation builds on the original checkout's local Cragmaw work, not the newer research-audit revision.

## Try the local fixture

The running player portal is [Phandalin demo](http://127.0.0.1:8020/?portal=player-1-controller&autoconnect=1). The [DM portal](http://127.0.0.1:8020/?portal=dm&autoconnect=1) shows the complete dungeon state. Both are local development portals. The smoke-tested session is back in Phandalin with Carp's entrance clue already discovered.

The server uses a copied campaign under `tasks/phandalin-browser-demo`, preserving the campaign's source memory files. Its launch command, from the worktree above, is:

```powershell
python -X utf8 user-test/web_story_demo_server.py --local-llm --story-start phandalin --base-url file:///D:/5etools-mirror-2.github.io/ --http-port 8020 --ws-port 8780 --campaign-root tasks/phandalin-browser-demo/campaign-release --trajectory-dir tasks/phandalin-browser-demo/trajectories
```

Use the already running server rather than starting another process on those ports. For a separate run, copy `campaigns/lmop` to a fresh directory, pass that directory as `--campaign-root`, and choose unused ports. `--local-llm` uses a canned transport, not a live model or an autonomous combat DM. Normal model-backed narration uses the existing `.env` configuration with that flag omitted; live-provider behavior was not tested here.

### Suggested walkthrough

1. Click Stonehill Inn, then **Speak with Toblen** to learn about the Redbrands and missing family.
2. Visit Alderleaf Farm and **Ask Carp about the woods** to discover the concealed entrance. This reveals a choice without moving the party.
3. Visit Tresendar Manor. **Inspect the manor ruins** reveals the main entrance; Carp's clue reveals the concealed woodland tunnel.
4. Choose an entrance explicitly. The tactical map now uses normal movement, visibility, targeting, and controller ownership.
5. Record each character's actual body weight in the provided field before crossing load-sensitive hazards. Equipment weight is added by the rules engine.
6. Explore with the map or `/move <actor-id> <x> <y> [z]`. Doors, searches, negotiations, keys, prisoner rescue, and evidence appear as local choices. Room encounters switch to normal initiative/combat.
7. Gather the party near the same entrance and choose **Return to Phandalin**. Re-entry preserves dungeon damage, doors, discoveries, encounters, and party resources within the session.

Manor movement example: Player 1 begins on the 15-foot landing at `(27,13,15)`. Walk through `(26,13,15)`, `(25,13,15)`, `(25,14,5)`, and `(25,15,0)` to descend. The hall door is beneath the northern landing: approach `(26,14,0)`, then `(26,13,0)`.

## Deterministic interface

- `/visit <place-id>` and `/talk <speaker-id>` select authored town locations and conversations.
- `/site enter <manor|tunnel>` and `/site leave` change maps only after validated prerequisites.
- `/site search here`, `/site open <door-id>`, `/site close <door-id>`, `/site pick-lock <door-id>`, and `/site force <door-id>` resolve local actions.
- `/site open <door-id> utilize` / `close ... utilize` explicitly use an action after the free object interaction is spent. The browser labels and submits that cost explicitly. Picking/forcing consumes the action in combat.
- `/site interact <interaction-id>` and `/site engage <encounter-id>` select projected local choices.
- `/site weight <positive-lb>` records missing character weight once; it is not a way to change established weight during a trap.
- Exact displayed natural-language labels, such as “Visit Stonehill Inn,” resolve to the same typed intents. Ambiguous action language returns typed clarification without a model call or mechanical mutation.

The six town POIs are Barthen's Provisions, Stonehill Inn, Townmaster's Hall, Alderleaf Farm, the Sleeping Giant, and Tresendar Manor. Dungeon content includes twelve rooms, seventeen doors, two entrances, seven scoped encounters, the nothic bargain, Droop's information, prisoner rescue, keys, Glasstaff's identity, and the Black Spider letter.

## Authority and privacy

Authored content is separate from the generic resolver. `CampaignSiteIntent` resolves on copied encounter/site stores, emits typed events, then commits both stores together. Rejected site actions preserve the state and random counter. Seeded checks, attacks, saves, falls, spell slots, and initiative remain in the existing kernel.

The DM model receives site narration constraints. Both top-level and direct scene/mode decision entrypoints validate site authority. The model's text does not move the party, open doors, reveal secrets, defeat enemies, or award rescue flags.

Hidden player cells are opaque and carry unknown terrain rather than room/secret metadata. Player and DM projections are tested separately; discovered door features are filtered in map projection and inspection. Monsters from unengaged rooms neither enter the current initiative order nor block completion or receive opportunity attacks.

## Sources and scope

[5e.tools](https://5e.tools/adventure.html#lmop) was the first rules/adventure source checked. The configured local mirror is `D:/5etools-mirror-2.github.io`. Story/map sources use Lost Mine of Phandelver, matching the existing Cragmaw art; the existing regional travel background remains PaBTSO.

- Town player image: `img/adventure/LMoP/Phandalin (Player).webp`, 4000 × 2788, no tactical grid.
- Hideout player image: `img/adventure/LMoP/Redbrand Hideout (Player).webp`, 4500 × 3136, 150-pixel squares, grid offset `(2,-7)`, five feet per cell.
- Monster records are explicit LMoP/MM identities. Existing XPHB spell implementations power Glasstaff's prepared spells and shared slot pools. Source `@atk` weapon tags, ruffian/nothic multiattack, and Rotting Gaze have executable coverage; this is not a complete generic monster-statblock interpreter.
- The pit triggers at **at least 100 lb**; the rigged bridge triggers **above 50 lb**. Site movement evaluates traversed cells, stops at the trigger, and resumes correctly after a pending reaction. Falls use the existing kernel.

This is a connected Redbrand milestone, not all optional Chapter 2 quests. Scripted reinforcements/retreat/surrender, numeric quest rewards and loot transfer, the pit's narrow-ledge Acrobatics bypass, and trap entry through teleport/forced relocation are not implemented in this slice. Existing simulator limitations, including complete elapsed-time effect lifecycle support, still apply. Persistence here means revisiting within the session plus deterministic event replay, not restart/save-game persistence. Do not interpret this work as full PHB/MM coverage or a balance evaluation.

## Verification and evidence

The executable replay fixture and regression tests are included in Git. The run logs, generated event streams, screenshots, local server directories, and preservation manifests listed below are local verification artifacts; they are deliberately excluded from the feature push.

- An initial 33-test Cragmaw/travel baseline and subsequent 153- and 184-test regression runs passed.
- Final release run: **186 tests passed in 216.034 seconds**; see `tasks/phandalin-release-tests.log`. Python compilation passed for 18 touched files; JavaScript syntax and `git diff --check` passed (line-ending warnings only).
- `tests/fixtures/phandalin_redbrand_arc.json` drives the clue → tunnel → nothic bargain → guards → Glasstaff → prisoners → town sequence. Its test replays the complete generated event stream and compares full encounter/site state. The deliberately boosted test hero and passive enemy turn policy isolate mechanics/progression; they do not assess difficulty or DM strategy.
- The final replay contains **627 events**, and full encounter/site state equality passed. Raw replay evidence: `tasks/phandalin-arc-events.jsonl` and `tasks/phandalin-arc-summary.json`. Re-run `python -X utf8 -m unittest tests.test_campaign_sites.CampaignSiteRulesTests.test_complete_hideout_arc_from_clues_to_rescue_and_return_replays -v` for the executable replay fixture.
- Browser proof: `tasks/phandalin-town-browser.jpg`, `tasks/redbrand-player-browser.jpg`, `tasks/redbrand-dm-browser.jpg`; raw manual inputs and results are retained in `tasks/phandalin-browser-demo/trajectories`.
- Original-source preservation and implementation file inventory: `tasks/phandalin-change-manifest.json`.
