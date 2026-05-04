# Mind Spike

Status: blocked

Blocker contract:
- Exact Mind Spike needs an authoritative tracking payload that can reveal location while suppressing stealth in the way the spell text specifies.
- The executor intentionally returns `None` until the shared observer-tracking primitive exists.

Cast syntax:
- `/cast player-1 mind-spike monster-skeleton-1`

Summary:
- Blocked: the current runtime does not have an exact location-reveal and hidden-state suppression primitive for Mind Spike.

See `IMPLEMENTATION.md` for the exact local-text classification and blockers.
