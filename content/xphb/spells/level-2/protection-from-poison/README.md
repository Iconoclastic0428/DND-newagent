# Protection from Poison

Status: blocked

Blocker contract:
- Exact Protection from Poison needs source-aware poison-save advantage plus poison-condition cleanup; the current runtime does not have a poison-specific save hook without guessing.
- The executor intentionally returns `None` until the poison-specific save hook exists.

Cast syntax:
- `/cast player-1 protection-from-poison player-1`

Summary:
- Exact XPHB Protection from Poison ends poisoned, grants advantage on saves to avoid or end poisoned, and gives poison resistance.

See `IMPLEMENTATION.md` for the exact local-text classification and blockers.
