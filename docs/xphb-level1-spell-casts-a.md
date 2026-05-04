# XPHB Level-1 Spell Casts A

This note records the mechanical cast syntax covered by the current XPHB level-1 rollout slice.

## Bless
`/cast player-1 bless player-1 --target monster-skeleton-1 --target monster-mage-1`
- Applies the persistent Bless effect to up to three creatures.
- Grants the attack-roll and saving-throw d4 bonus while concentration remains active.

## Bane
`/cast player-1 bane monster-skeleton-1 --target monster-mage-1`
- Applies the persistent Bane effect to failed targets.
- Imposes the attack-roll and saving-throw d4 penalty while concentration remains active.

## Chromatic Orb
`/cast player-1 chromatic-orb monster-skeleton-1 --damage-type fire --material diamond`
- Checks for the required costly diamond component.
- Rolls the selected damage type and can chain on the duplicate-dice case.

## Armor of Agathys
`/cast player-1 armor-of-agathys`
- Grants temporary hit points.
- Retaliates with cold damage on melee hits while the temporary hit points remain.

## False Life
`/cast player-1 false-life`
- Grants temporary hit points on the caster.
- Replaces weaker temporary hit points and never lowers a stronger existing pool.
