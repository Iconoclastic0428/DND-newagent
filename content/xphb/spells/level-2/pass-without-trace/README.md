# Pass without Trace

Status: blocked

Blocker contract:
- Exact Pass without Trace needs a no-tracks / trail-suppression consumer; the current runtime has the stealth bonus primitive but no authoritative track suppression primitive.
- The executor intentionally returns `None` until trail suppression is implemented.

Cast syntax:
- `/cast player-1 pass-without-trace`

Summary:
- Exact XPHB Pass without Trace grants +10 Stealth in the aura and suppresses tracks.

See `IMPLEMENTATION.md` for the exact local-text classification and blockers.
