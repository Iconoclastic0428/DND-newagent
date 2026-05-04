from __future__ import annotations

from dataclasses import dataclass

from .battlefield import MovementIntentMode
from .capabilities import IllusionInteractionKind
from .equipment import AttackInteractionSpec, EnvironmentObjectAction, EquipmentSlot, ObjectInteractionCostMode, ObjectInteractionKind
from .encounter_models import CombatActionType, ReadyResponseKind, ReadyTriggerKind, ShoveOutcome
from .rest import RestActivityType
from .spellcasting import SpellParameter


class EncounterIntent:
    """Marker base type for encounter runtime intents."""


@dataclass(frozen=True)
class StartEncounterIntent(EncounterIntent):
    participant_actor_ids: tuple[str, ...] | None = None
    surprised_actor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MoveActorIntent(EncounterIntent):
    actor_id: str
    x: int
    y: int
    z: int | None = None
    movement_intent_mode: MovementIntentMode = MovementIntentMode.SAME_PLANE


@dataclass(frozen=True)
class MountActorIntent(EncounterIntent):
    actor_id: str
    mount_actor_id: str


@dataclass(frozen=True)
class DismountActorIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class ShareFamiliarSensesIntent(EncounterIntent):
    actor_id: str
    familiar_actor_id: str | None = None


@dataclass(frozen=True)
class StandFromProneIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class TakeCombatActionIntent(EncounterIntent):
    actor_id: str
    action_type: CombatActionType
    target_id: str | None = None
    attack_id: str | None = None
    resource_mode: str = 'action'


@dataclass(frozen=True)
class ReadyIntent(EncounterIntent):
    actor_id: str
    trigger_kind: ReadyTriggerKind
    trigger_actor_id: str
    response_kind: ReadyResponseKind
    attack_id: str | None = None
    spell_id: str | None = None
    capability_id: str | None = None
    target_id: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    movement_intent_mode: MovementIntentMode = MovementIntentMode.SAME_PLANE


@dataclass(frozen=True)
class AttackIntent(EncounterIntent):
    actor_id: str
    attack_id: str
    target_id: str
    attack_interaction: AttackInteractionSpec | None = None


@dataclass(frozen=True)
class CastSpellIntent(EncounterIntent):
    actor_id: str
    spell_id: str
    target_id: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    ritual_cast: bool = False
    parameters: tuple[SpellParameter, ...] = ()


@dataclass(frozen=True)
class UseCapabilityIntent(EncounterIntent):
    actor_id: str
    capability_id: str
    target_id: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    parameters: tuple[SpellParameter, ...] = ()


@dataclass(frozen=True)
class ObjectInteractionIntent(EncounterIntent):
    actor_id: str
    interaction_kind: ObjectInteractionKind
    cost_mode: ObjectInteractionCostMode
    item_id: str | None = None
    ground_item_id: str | None = None
    object_id: str | None = None
    object_action: EnvironmentObjectAction | None = None
    source_actor_id: str | None = None


@dataclass(frozen=True)
class EquipItemIntent(EncounterIntent):
    actor_id: str
    item_id: str
    slot: EquipmentSlot


@dataclass(frozen=True)
class UseImprovisedWeaponIntent(EncounterIntent):
    actor_id: str
    target_id: str
    item_id: str | None = None
    ground_item_id: str | None = None
    object_id: str | None = None
    thrown: bool = False
    equivalent_weapon_item_id: str | None = None
    damage_type: str = 'bludgeoning'


@dataclass(frozen=True)
class GrappleIntent(EncounterIntent):
    actor_id: str
    target_id: str


@dataclass(frozen=True)
class ShoveIntent(EncounterIntent):
    actor_id: str
    target_id: str
    outcome: ShoveOutcome


@dataclass(frozen=True)
class ChooseReactionIntent(EncounterIntent):
    actor_id: str
    option_id: str


@dataclass(frozen=True)
class ChooseTimingOrderIntent(EncounterIntent):
    actor_id: str
    entry_id: str


@dataclass(frozen=True)
class ContinueTimingIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class ResolveIllusionInteractionIntent(EncounterIntent):
    actor_id: str
    illusion_id: str
    interaction_kind: IllusionInteractionKind


@dataclass(frozen=True)
class StartRitualCastIntent(EncounterIntent):
    actor_id: str
    capability_id: str
    spell_id: str | None = None


@dataclass(frozen=True)
class EndTurnIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class StartShortRestIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class StartLongRestIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class ResumeRestIntent(EncounterIntent):
    actor_id: str


@dataclass(frozen=True)
class SpendHitPointDieIntent(EncounterIntent):
    actor_id: str
    count: int = 1


@dataclass(frozen=True)
class AdvanceTimeIntent(EncounterIntent):
    minutes: int
    activity_type: RestActivityType = RestActivityType.LIGHT_ACTIVITY

