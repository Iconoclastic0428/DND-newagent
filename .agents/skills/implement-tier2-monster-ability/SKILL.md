# Implement Tier-2 Monster Ability

Follow `../implement-tier2-content-item/SKILL.md` first.

## Additional monster-ability rules
1. Validate the ability against local official monster data.
2. Reuse shared attack / save / active-effect / recharge primitives rather than bespoke command logic.
3. Add parity coverage tests that prove the ability can execute through the encounter runtime.
4. Update the Tier-2 monster-ability manifest and support matrix.
