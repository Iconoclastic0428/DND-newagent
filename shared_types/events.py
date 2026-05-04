from __future__ import annotations

from dataclasses import dataclass

from .models import Ability, AbilityMethod, CharacterRecord, EquipmentSelectionMode, ItemGrant


class CreationEvent:
    """Marker base type for append-only state transitions."""


@dataclass(frozen=True)
class CreationStartedEvent(CreationEvent):
    pass


@dataclass(frozen=True)
class SpeciesChosenEvent(CreationEvent):
    species_id: str


@dataclass(frozen=True)
class ClassChosenEvent(CreationEvent):
    class_id: str


@dataclass(frozen=True)
class ClassSkillsChosenEvent(CreationEvent):
    skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class BackgroundChosenEvent(CreationEvent):
    background_id: str


@dataclass(frozen=True)
class RolledAbilityScoresGeneratedEvent(CreationEvent):
    scores: tuple[int, ...]
    roll_breakdown: tuple[tuple[int, int, int, int], ...]
    random_counter_used: int


@dataclass(frozen=True)
class PointBuyScoresSetEvent(CreationEvent):
    scores: tuple[int, ...]
    total_cost: int


@dataclass(frozen=True)
class AbilityArrayChosenEvent(CreationEvent):
    method: AbilityMethod


@dataclass(frozen=True)
class AbilitiesAssignedEvent(CreationEvent):
    assignments: dict[Ability, int]


@dataclass(frozen=True)
class BackgroundAsiAppliedEvent(CreationEvent):
    option_id: str
    bonuses: dict[Ability, int]


@dataclass(frozen=True)
class OriginFeatChosenEvent(CreationEvent):
    feat_id: str


@dataclass(frozen=True)
class CreationChoiceResolvedEvent(CreationEvent):
    choice_id: str
    option_ids: tuple[str, ...]


@dataclass(frozen=True)
class BackgroundEquipmentChosenEvent(CreationEvent):
    mode: EquipmentSelectionMode
    package_id: str | None
    item_grants: tuple[ItemGrant, ...]
    currency_cp_delta: int


@dataclass(frozen=True)
class ClassEquipmentChosenEvent(CreationEvent):
    mode: EquipmentSelectionMode
    package_id: str | None
    item_grants: tuple[ItemGrant, ...]
    currency_cp_delta: int
    random_counter_used: int | None = None
    roll_breakdown: tuple[int, ...] = ()


@dataclass(frozen=True)
class ItemPurchasedEvent(CreationEvent):
    item_id: str
    quantity: int
    total_cost_cp: int


@dataclass(frozen=True)
class CreationConfirmedEvent(CreationEvent):
    record: CharacterRecord
