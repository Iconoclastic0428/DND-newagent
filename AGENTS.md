# DND Agent

## Project goal
Build a multiplayer D&D 5e 2024 agent platform with:
1. a DM agent for campaign narration and check requests,
2. a deterministic rules simulator,
3. a player interface supporting natural language and slash commands,
4. server-authoritative multiplayer synchronization.

## Architectural invariants
- The DM agent is NOT the source of truth for mechanics or state mutation.
- The rules engine is the sole authority for combat legality, action economy, movement, targeting, HP, conditions, spell slots, concentration, and turn order.
- All state mutations must occur through typed intents -> validation -> resolution -> event log -> state commit.
- Natural-language player input may be interpreted by LLMs, but final executable actions must be converted into typed intents.
- Slash commands must bypass freeform interpretation whenever possible and go directly to typed intents.
- Multiplayer is server-authoritative. Clients never mutate canonical state directly.
- Public state, private player knowledge, and GM-only hidden state must be separated.
- Campaign content ingestion must support official module text plus user overrides/homebrew patches.

## Required top-level modules
- campaign-ingestion
- dm-agent
- rules-engine
- player-interface
- session-server
- shared-types

## Module responsibilities
### dm-agent
- Reads campaign graph and visible game state.
- Produces narration, NPC dialogue, hidden-scene reasoning, and typed check requests.
- May propose actions but may not directly commit mechanical state.

### rules-engine
- Owns initiative, rounds, turns, movement, actions, bonus actions, reactions, attacks, saves, spell resolution, conditions, concentration, death rules, and resource tracking.
- Resolves all typed intents deterministically.
- Emits append-only events.
- All randomness must be originated from the rules engine, and they must be seedable from a single deterministic seed that is unique and recorded in an .env file.
- If a natural langauge input maps to multiple legal intents or missing parameters, the system must reject with a typed clarification request, NEVER guess a parameter.

### campaign-ingestion
- Converts adventure text into a structured campaign graph.
- Supports location nodes, triggers, checks, encounters, boxed text, hidden notes, and homebrew overrides.

### player-interface
- Supports both natural language and slash commands.
- Must expose deterministic commands such as /move, /attack, /cast, /spellbook, /slots, /conditions, /initiative, /inventory.

### session-server
- Manages multiplayer sessions, permissions, turn prompts, reaction windows, private whispers, fog of war, and per-player overlays.

## State model
Maintain separate stores for:
- canonical world state
- combat state
- per-player private knowledge
- campaign hidden state
- append-only event log

## Communication rules
- DM agent may request checks and propose interpretations.
- Rules engine validates and resolves.
- Broadcast layer decides public vs private visibility.

## Implementation constraints
- Prefer strongly typed intent and event schemas.
- Keep campaign-specific logic out of the generic rules engine.
- Keep 5e rules data and campaign text ingestion decoupled.
- Every implemented rule should have unit tests.
- Every combat flow should have replayable event-log fixtures.
- NEVER add fallback code logic, return error when there is an error.
- When you need to search for a DND-related information, ALWAYS first query 5e.tools for English and 5e.kiwee.top for Chinese.

## Done when
A change is complete only if:
- types compile,
- relevant tests pass,
- state transitions are covered,
- no module violates the DM-vs-simulator authority boundary,
- public/private visibility rules are preserved.

## Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps for architectural decision)
- If somethjing goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

## Self-improvement loop
- When the user corrects you, always write docs/LESSONS.md with the pattern.
- Write rules in LESSONS.md to make sure you do not make the same mistake again.
- Always review LESSONS.md at the start of each session to make sure you understand the rules.

## Verification before done
- NEVER mark a task as complete before you prove it works.
- Always ask yourself: Will a staff engineer approve this?
- Run tests, check logs, demonstrate correctness.

## Demand Elegance
- For non-trivial changes, pause and ask: "is there a more elegant way?"
- If a fix or an implementation feels hacky, knowing everything I know now, implement the elegant solution.
- Skip this for simple, chvious fixes - don't over-engineer.
- Challenge your own work before presenting it.

## Task management
1. **Plan First**: Write plan to tasks/TODO.md with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**" Add review section to tasks/TODO.md
6. **Capture Lessons**: Update `tasks/LESSONS.md` after corrections
7. **Write Summary**: Write the summarization of each request that captures all the important points and the solution to `tasks/SUMMARIES.md`

## Core Principles
1. **Simplicity First**: Make every change as simple as possible. Impact minimal code.
2. **No Laziness**" Find root causes. No temporary fixes. Senior developer standards.