# XPHB Level-1 Spell Use Cases

This note records the current story-adjudicated contract for the owned spell batch.
These spells have per-spell tests and folder metadata, but the shared runtime still lacks the deterministic mechanics needed for full battle-map effect application.

## Bane
- Cast: `/cast player-1 bane monster-mage-1 --target monster-goblin-1 --target monster-goblin-2`
- Local text focus: up to three creatures you can see within 30 feet must make a Charisma saving throw.
- Blocker: Shared runtime still needs the authoritative ongoing penalty effect for a full mechanical Bane implementation.

## Bless
- Cast: `/cast player-1 bless player-1 --target player-2 --target player-3`
- Local text focus: up to three creatures of your choice within 30 feet add 1d4 to attack rolls and saving throws.
- Blocker: Shared runtime still needs the authoritative ongoing bonus effect for a full mechanical Bless implementation.

## Chromatic Orb
- Cast: `/cast player-1 chromatic-orb monster-mage-1 --damage-type fire --material diamond-50-gp`
- Local text focus: choose a damage type and supply the costly diamond component.
- Blocker: Shared runtime still needs costed material validation and a deterministic attack/save damage branch for Chromatic Orb.

## Hail of Thorns
- Cast: `/cast player-1 hail-of-thorns monster-mage-1 --weapon longbow`
- Local text focus: the next time you hit with a ranged weapon attack before the spell ends.
- Blocker: Shared runtime still needs a true post-hit burst trigger for Hail of Thorns.

## Hellish Rebuke
- Cast: `/cast player-1 hellish-rebuke monster-mage-1`
- Local text focus: when you take damage from a creature you can see within 60 feet.
- Blocker: Shared runtime still needs the full reaction-window trigger path for Hellish Rebuke.

## Entangle
- Cast: `/cast player-1 entangle 4 5`
- Local text focus: a 20-foot-square area of ground sprouts grasping weeds and vines.
- Blocker: Shared runtime still needs persistent restrained-area handling for Entangle.

## Fog Cloud
- Cast: `/cast player-1 fog-cloud 4 5`
- Local text focus: a 20-foot-radius sphere of fog centered on the chosen point.
- Blocker: Shared runtime still needs a persistent obscuring-area implementation for Fog Cloud.

## Divine Smite
- Cast: `/cast player-1 divine-smite monster-mage-1 --weapon longsword`
- Local text focus: immediately after you hit a target with a melee weapon attack or unarmed strike.
- Blocker: Shared runtime still needs the on-hit bonus-action spell trigger for Divine Smite.

## Worker A Addendum
- `Armor of Agathys`: `/cast player-1 armor-of-agathys`
  - `/cast player-1 armor-of-agathys --description Frost armor flares around the caster`
- `False Life`: `/cast player-1 false-life`
  - `/cast player-1 false-life --description Harden your constitution with necromantic vigor`
- `Divine Favor`: `/cast player-1 divine-favor`
  - `/cast player-1 divine-favor --description Invoke divine aid for radiant weapon strikes`
- `Heroism`: `/cast player-1 heroism player-1`
  - `/cast player-1 heroism player-1 --description Steel the caster against fear`
- `Jump`: `/cast player-1 jump player-1`
  - `/cast player-1 jump player-1 --description Leap over the wagon rail`
- `Longstrider`: `/cast player-1 longstrider player-1`
  - `/cast player-1 longstrider player-1 --description Increase the caster's pace`
- `Mage Armor`: `/cast player-1 mage-armor player-1`
  - `/cast player-1 mage-armor player-1 --description Wards the caster in conjured armor`
- `Protection from Evil and Good`: `/cast player-1 protection-from-evil-and-good player-1`
  - `/cast player-1 protection-from-evil-and-good player-1 --description Ward the caster from fiends and undead`
- `Witch Bolt`: `/cast player-1 witch-bolt gundren-rockseeker`
  - `/cast player-1 witch-bolt gundren-rockseeker --description Maintain the lightning arc`
  - Current blocker: story-mode spell resolution still requires runtime actor targets unless the cast escalates into combat.

