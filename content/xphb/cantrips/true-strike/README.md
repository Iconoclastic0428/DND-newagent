# True Strike

XPHB cantrip rollout entry.
Runtime support mode: `deterministic-capability`.
Example cast: `/cast player-1 true-strike monster-skeleton-1 --item dagger --damage-type radiant`

Use case: Weapon-enchantment attack cantrip that can be pointed at a custom held item.

## Command Usage

- Parser form: `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.
- Example: `/cast player-1 true-strike monster-skeleton-1 --item dagger --damage-type radiant`
- Support: authoritative rules command. The slash command becomes a typed cast intent and resolves through the rules-engine capability path when the caster knows the spell and has the required action/resources.
