from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations, permutations
import re

from .equipment import ArmorCategory


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    characters: list[str] = []
    last_was_separator = False
    for char in lowered:
        if char.isalnum() or char == "_":
            characters.append(char)
            last_was_separator = False
            continue
        if not last_was_separator:
            characters.append("-")
            last_was_separator = True
    return "".join(characters).strip("-")


def cp_to_display(value_cp: int) -> str:
    gp = value_cp // 100
    remainder = value_cp % 100
    if remainder == 0:
        return f"{gp} gp"
    return f"{gp}.{remainder:02d} gp"


class Ability(str, Enum):
    STR = "STR"
    DEX = "DEX"
    CON = "CON"
    INT = "INT"
    WIS = "WIS"
    CHA = "CHA"


ABILITY_ORDER: tuple[Ability, ...] = (
    Ability.STR,
    Ability.DEX,
    Ability.CON,
    Ability.INT,
    Ability.WIS,
    Ability.CHA,
)


class AbilityGenerationMode(str, Enum):
    ROLL_ONLY = "roll-only"
    POINT_BUY_ONLY = "point-buy-only"
    ROLL_OR_POINT_BUY = "roll-or-point-buy"
    COMPARE_ROLL_AND_POINT_BUY_HIGHER_TOTAL = "compare-roll-and-point-buy-higher-total"


class AbilityMethod(str, Enum):
    ROLLED = "rolled"
    POINT_BUY = "point-buy"


class EquipmentSelectionMode(str, Enum):
    PACKAGE = "package"
    GOLD = "gold"
    WEALTH = "wealth"


class CreationPhase(str, Enum):
    NOT_STARTED = "not-started"
    CHOOSE_SPECIES = "choose-species"
    CHOOSE_CLASS = "choose-class"
    CHOOSE_CLASS_SKILLS = "choose-class-skills"
    CHOOSE_BACKGROUND = "choose-background"
    CHOOSE_CREATION_CHOICES = "choose-creation-choices"
    GENERATE_ABILITIES = "generate-abilities"
    CHOOSE_ABILITY_ARRAY = "choose-ability-array"
    ASSIGN_ABILITIES = "assign-abilities"
    CHOOSE_BACKGROUND_ASI = "choose-background-asi"
    CHOOSE_ORIGIN_FEAT = "choose-origin-feat"
    CHOOSE_BACKGROUND_EQUIPMENT = "choose-background-equipment"
    CHOOSE_CLASS_EQUIPMENT = "choose-class-equipment"
    REVIEW = "review"
    COMPLETE = "complete"


class ContentKind(str, Enum):
    SPECIES = "species"
    CLASS = "class"
    BACKGROUND = "background"
    FEAT = "feat"
    ITEM = "item"
    SKILL = "skill"
    TOOL = "tool"
    SPELL = "spell"


class CreationChoiceCategory(str, Enum):
    CLASS_SKILL = "class-skill"
    CLASS_FEATURE = "class-feature"
    BACKGROUND_SKILL = "background-skill"
    ORIGIN_FEAT = "origin-feat"
    SPELL_LIST = "spell-list"
    SPELLCASTING_ABILITY = "spellcasting-ability"
    CANTRIP = "cantrip"
    SPELL = "spell"
    TOOL = "tool"
    SKILL_OR_TOOL = "skill-or-tool"


class ChoiceSourceKind(str, Enum):
    CLASS = "class"
    BACKGROUND = "background"
    FEAT = "feat"
    SPECIES = "species"


class ChoiceResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"


class ProficiencyCategory(str, Enum):
    SKILL = "skill"
    TOOL = "tool"


class SpellSelectionKind(str, Enum):
    CANTRIP = "cantrip"
    KNOWN = "known"
    PREPARED = "prepared"
    ALWAYS_PREPARED = "always-prepared"
    INNATE = "innate"


@dataclass(frozen=True)
class SourcePolicy:
    allowed_sources: frozenset[str]
    ability_generation_mode: AbilityGenerationMode
    allow_homebrew: bool = False
    allow_class_wealth: bool = False
    allowed_item_sources: frozenset[str] = frozenset()
    allowed_background_sources: frozenset[str] = frozenset()
    allowed_origin_feat_sources: frozenset[str] = frozenset()
    allow_first_party_background_extensions: bool = True
    allow_first_party_origin_feat_extensions: bool = True

    def allows_source(self, source: str, *, homebrew: bool, edition: str, official: bool) -> bool:
        if homebrew and not self.allow_homebrew:
            return False
        if edition != "2024":
            return False
        if not official:
            return False
        return source in self.allowed_sources

    def allows_item_source(self, source: str, *, homebrew: bool, edition: str, official: bool) -> bool:
        allowed_item_sources = self.allowed_item_sources or self.allowed_sources
        if homebrew and not self.allow_homebrew:
            return False
        if edition != "2024":
            return False
        if not official:
            return False
        return source in allowed_item_sources

    def allows_background_source(self, source: str, *, homebrew: bool, official: bool, first_party: bool) -> bool:
        if homebrew and not self.allow_homebrew:
            return False
        if not official:
            return False
        if self.allowed_background_sources:
            return source in self.allowed_background_sources
        if source == "PHB":
            return False
        if source in self.allowed_sources:
            return True
        return self.allow_first_party_background_extensions and first_party

    def allows_origin_feat_source(self, source: str, *, homebrew: bool, official: bool, first_party: bool) -> bool:
        if homebrew and not self.allow_homebrew:
            return False
        if not official:
            return False
        if self.allowed_origin_feat_sources:
            return source in self.allowed_origin_feat_sources
        if source == "PHB":
            return False
        if source in self.allowed_sources:
            return True
        return self.allow_first_party_origin_feat_extensions and first_party


@dataclass(frozen=True)
class ItemGrant:
    item_id: str
    quantity: int


@dataclass(frozen=True)
class EquipmentPackage:
    package_id: str
    label: str
    item_grants: tuple[ItemGrant, ...]
    currency_cp: int = 0


@dataclass(frozen=True)
class CurrencyRoll:
    die_count: int
    die_faces: int
    multiplier_cp: int
    label: str


@dataclass(frozen=True)
class ChoiceSource:
    source_kind: ChoiceSourceKind
    source_id: str
    source_name: str


@dataclass(frozen=True)
class SelectionConstraint:
    required_count: int
    allow_duplicates: bool = False


@dataclass(frozen=True)
class ChoiceOption:
    option_id: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class ChoiceGroup:
    choice_id: str
    label: str
    prompt: str
    options: tuple[ChoiceOption, ...]
    constraint: SelectionConstraint


@dataclass(frozen=True)
class PendingChoice:
    group: ChoiceGroup
    source: ChoiceSource
    category: CreationChoiceCategory
    resolution_status: ChoiceResolutionStatus
    blocks_finalization: bool = True
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SpeciesRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    size_options: tuple[str, ...]
    speed: int
    traits: tuple[str, ...]
    hit_point_bonus_per_level: int = 0
    bonus_origin_feat_count: int = 0


@dataclass(frozen=True)
class SkillRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    ability: Ability


@dataclass(frozen=True)
class ToolRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    category: str


@dataclass(frozen=True)
class CreationSpellRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    level: int
    school: str
    class_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProficiencyChoiceGroup:
    choice_id: str
    label: str
    category: CreationChoiceCategory
    allowed_categories: tuple[ProficiencyCategory, ...]
    option_ids: tuple[str, ...]
    count: int
    allow_duplicates: bool = False


@dataclass(frozen=True)
class ClassSpellcastingRecord:
    spellcasting_ability: Ability
    cantrip_choice_count: int = 0
    spell_choice_count: int = 0
    spell_selection_kind: SpellSelectionKind = SpellSelectionKind.PREPARED
    spell_slot_progression: tuple[tuple[int, ...], ...] = ()
    cantrip_choice_progression: tuple[int, ...] = ()
    spell_choice_progression: tuple[int, ...] = ()


@dataclass(frozen=True)
class MulticlassRequirementSet:
    minimum_scores: dict[Ability, int]


@dataclass(frozen=True)
class MulticlassProficiencyGrant:
    armor_training: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    skill_proficiency_ids: tuple[str, ...] = ()
    tool_proficiency_ids: tuple[str, ...] = ()
    skill_option_ids: tuple[str, ...] = ()
    skill_choice_count: int = 0


@dataclass(frozen=True)
class ClassLevelFeatureGrant:
    level: int
    feature_name: str
    feature_reference: str | None = None
    grants_subclass_choice: bool = False


@dataclass(frozen=True)
class SubclassRecord:
    record_id: str
    class_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    feature_grants: tuple[ClassLevelFeatureGrant, ...] = ()


@dataclass(frozen=True)
class FeatSpellChoiceBundle:
    choice_id: str
    label: str
    spell_list_class_ids: tuple[str, ...]
    spellcasting_ability_options: tuple[Ability, ...]
    cantrip_count: int
    spell_count: int
    spell_level: int
    spell_selection_kind: SpellSelectionKind


@dataclass(frozen=True)
class ClassFeatureSpellChoiceBundle:
    choice_id: str
    label: str
    spell_list_class_ids: tuple[str, ...]
    cantrip_count: int = 0
    spell_count: int = 0
    spell_level: int = 0
    spell_selection_kind: SpellSelectionKind = SpellSelectionKind.KNOWN


@dataclass(frozen=True)
class ClassFeatureGrantedSpell:
    spell_id: str
    selection_kind: SpellSelectionKind


@dataclass(frozen=True)
class ClassFeatureChoiceOption:
    option_id: str
    label: str
    detail: str = ""
    armor_training_grants: tuple[str, ...] = ()
    weapon_proficiency_grants: tuple[str, ...] = ()
    spell_choice_bundles: tuple[ClassFeatureSpellChoiceBundle, ...] = ()
    granted_spells: tuple[ClassFeatureGrantedSpell, ...] = ()


@dataclass(frozen=True)
class ClassFeatureChoiceGroup:
    choice_id: str
    label: str
    prompt: str
    options: tuple[ClassFeatureChoiceOption, ...]
    constraint: SelectionConstraint
    level: int = 1
    source_feature_name: str | None = None


@dataclass(frozen=True)
class FeatGrantOption:
    option_id: str
    feat_id: str
    label: str
    fixed_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ClassRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    primary_abilities: tuple[Ability, ...]
    hit_die: int
    saving_throw_proficiencies: tuple[Ability, ...]
    skill_choices: tuple[str, ...]
    skill_choice_count: int
    armor_training: tuple[str, ...]
    weapon_proficiencies: tuple[str, ...]
    tool_proficiencies: tuple[str, ...]
    package_options: tuple[EquipmentPackage, ...]
    wealth_option: CurrencyRoll | None
    spellcasting: ClassSpellcastingRecord | None = None
    class_feature_choice_groups: tuple[ClassFeatureChoiceGroup, ...] = ()
    class_feature_grants: tuple[ClassLevelFeatureGrant, ...] = ()
    subclasses: tuple[SubclassRecord, ...] = ()
    multiclass_requirement_sets: tuple[MulticlassRequirementSet, ...] = ()
    multiclass_proficiency_grant: MulticlassProficiencyGrant | None = None
    class_skill_option_ids: tuple[str, ...] = ()
    tool_proficiency_ids: tuple[str, ...] = ()
    class_tool_option_ids: tuple[str, ...] = ()
    class_tool_choice_count: int = 0


@dataclass(frozen=True)
class FeatRecord:
    record_id: str
    name: str
    source: str
    official: bool
    homebrew: bool
    category: str
    prerequisite: str | None = None
    selectable_for_custom_origin: bool = False
    repeatable: bool = False
    proficiency_choice_groups: tuple[ProficiencyChoiceGroup, ...] = ()
    spell_choice_bundles: tuple[FeatSpellChoiceBundle, ...] = ()


@dataclass(frozen=True)
class AbilityIncreaseOption:
    option_id: str
    label: str
    bonuses: dict[Ability, int]


@dataclass(frozen=True)
class BackgroundRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    allowed_asi_abilities: tuple[Ability, ...]
    flexible_asi: bool
    origin_feat_options: tuple[FeatGrantOption, ...]
    skill_proficiencies: tuple[str, ...]
    tool_proficiencies: tuple[str, ...]
    package_options: tuple[EquipmentPackage, ...]
    gold_option_cp: int | None
    skill_proficiency_ids: tuple[str, ...] = ()
    tool_proficiency_ids: tuple[str, ...] = ()
    background_skill_option_ids: tuple[str, ...] = ()
    background_skill_choice_count: int = 0
    background_tool_option_ids: tuple[str, ...] = ()
    background_tool_choice_count: int = 0

    def ability_increase_options(self) -> tuple[AbilityIncreaseOption, ...]:
        options: list[AbilityIncreaseOption] = []
        if self.flexible_asi:
            for primary, secondary in permutations(ABILITY_ORDER, 2):
                options.append(
                    AbilityIncreaseOption(
                        option_id=f"{self.record_id}-{primary.value.lower()}2-{secondary.value.lower()}1",
                        label=f"{primary.value} +2, {secondary.value} +1",
                        bonuses={primary: 2, secondary: 1},
                    )
                )
            for trio in combinations(ABILITY_ORDER, 3):
                label = ", ".join(f"{ability.value} +1" for ability in trio)
                option_id = f"{self.record_id}-plus1-{'-'.join(ability.value.lower() for ability in trio)}"
                options.append(
                    AbilityIncreaseOption(
                        option_id=option_id,
                        label=label,
                        bonuses={ability: 1 for ability in trio},
                    )
                )
            return tuple(options)

        first, second, third = self.allowed_asi_abilities
        options.extend(
            [
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-{first.value.lower()}2-{second.value.lower()}1",
                    label=f"{first.value} +2, {second.value} +1",
                    bonuses={first: 2, second: 1},
                ),
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-{first.value.lower()}2-{third.value.lower()}1",
                    label=f"{first.value} +2, {third.value} +1",
                    bonuses={first: 2, third: 1},
                ),
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-{second.value.lower()}2-{first.value.lower()}1",
                    label=f"{second.value} +2, {first.value} +1",
                    bonuses={second: 2, first: 1},
                ),
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-{second.value.lower()}2-{third.value.lower()}1",
                    label=f"{second.value} +2, {third.value} +1",
                    bonuses={second: 2, third: 1},
                ),
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-{third.value.lower()}2-{first.value.lower()}1",
                    label=f"{third.value} +2, {first.value} +1",
                    bonuses={third: 2, first: 1},
                ),
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-{third.value.lower()}2-{second.value.lower()}1",
                    label=f"{third.value} +2, {second.value} +1",
                    bonuses={third: 2, second: 1},
                ),
                AbilityIncreaseOption(
                    option_id=f"{self.record_id}-plus1-all",
                    label=f"{first.value} +1, {second.value} +1, {third.value} +1",
                    bonuses={first: 1, second: 1, third: 1},
                ),
            ]
        )
        return tuple(options)


@dataclass(frozen=True)
class ItemRecord:
    record_id: str
    name: str
    source: str
    edition: str
    official: bool
    homebrew: bool
    cost_cp: int
    weight_lb: float | None = None
    is_magical: bool = False
    tags: tuple[str, ...] = ()
    weapon_category: str | None = None
    weapon_kind: str | None = None
    weapon_damage_dice_count: int | None = None
    weapon_damage_die_faces: int | None = None
    weapon_versatile_damage_dice_count: int | None = None
    weapon_versatile_damage_die_faces: int | None = None
    weapon_damage_type: str | None = None
    weapon_range_ft: int | None = None
    weapon_long_range_ft: int | None = None
    weapon_properties: tuple[str, ...] = ()
    weapon_mastery: str | None = None
    weapon_ammunition_type: str | None = None
    weapon_notes: tuple[str, ...] = ()
    armor_category: ArmorCategory | None = None
    armor_base_ac: int | None = None
    armor_dex_cap: int | None = None
    armor_strength_requirement: int | None = None
    armor_stealth_disadvantage: bool = False
    armor_don_time_seconds: int | None = None
    armor_doff_time_seconds: int | None = None
    shield_ac_bonus: int | None = None


@dataclass
class AbilityDraft:
    rolled_scores: tuple[int, ...] | None = None
    roll_breakdown: tuple[tuple[int, int, int, int], ...] | None = None
    point_buy_scores: tuple[int, ...] | None = None
    chosen_method: AbilityMethod | None = None

    def chosen_scores(self) -> tuple[int, ...] | None:
        if self.chosen_method == AbilityMethod.ROLLED:
            return self.rolled_scores
        if self.chosen_method == AbilityMethod.POINT_BUY:
            return self.point_buy_scores
        return None


@dataclass(frozen=True)
class CharacterProficiencySelection:
    record_id: str
    name: str
    category: ProficiencyCategory
    source: ChoiceSource


@dataclass(frozen=True)
class CharacterSpellSelection:
    spell_id: str
    spell_name: str
    spell_level: int
    selection_kind: SpellSelectionKind
    source: ChoiceSource
    spellcasting_ability: Ability | None = None
    spell_list_class_id: str | None = None


@dataclass(frozen=True)
class CharacterFeatGrant:
    feat_id: str
    feat_name: str
    source: ChoiceSource
    fixed_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResolvedCreationChoice:
    choice_id: str
    category: CreationChoiceCategory
    source: ChoiceSource
    selected_option_ids: tuple[str, ...]
    selected_option_labels: tuple[str, ...]


@dataclass(frozen=True)
class CharacterClassLevel:
    class_id: str
    level: int


@dataclass(frozen=True)
class CharacterSubclassSelection:
    class_id: str
    subclass_id: str
    subclass_name: str


@dataclass(frozen=True)
class ResolvedAdvancementChoiceRecord:
    choice_id: str
    category: str
    selected_option_ids: tuple[str, ...]
    selected_option_labels: tuple[str, ...]


@dataclass
class CharacterRecord:
    record_id: str
    level: int
    species_id: str
    class_id: str
    background_id: str
    source_refs: tuple[str, ...]
    ability_scores: dict[Ability, int]
    ability_modifiers: dict[Ability, int]
    base_ability_array: tuple[int, ...]
    chosen_ability_method: AbilityMethod
    max_hit_points: int
    proficiency_bonus: int
    saving_throw_proficiencies: tuple[Ability, ...]
    class_skill_proficiencies: tuple[str, ...]
    background_skill_proficiencies: tuple[str, ...]
    tool_proficiencies: tuple[str, ...]
    armor_training: tuple[str, ...]
    weapon_proficiencies: tuple[str, ...]
    traits: tuple[str, ...]
    origin_feats: tuple[str, ...]
    inventory: dict[str, int]
    currency_cp: int
    proficiency_selections: tuple[CharacterProficiencySelection, ...] = ()
    spell_selections: tuple[CharacterSpellSelection, ...] = ()
    feat_grants: tuple[CharacterFeatGrant, ...] = ()
    resolved_creation_choices: tuple[ResolvedCreationChoice, ...] = ()
    class_levels: tuple[CharacterClassLevel, ...] = ()
    subclass_selections: tuple[CharacterSubclassSelection, ...] = ()
    resolved_advancement_choices: tuple[ResolvedAdvancementChoiceRecord, ...] = ()
    expertise_skill_ids: tuple[str, ...] = ()
    expertise_tool_ids: tuple[str, ...] = ()
    fighting_style_names: tuple[str, ...] = ()
    weapon_mastery_item_ids: tuple[str, ...] = ()
    class_feature_names: tuple[str, ...] = ()


def normalized_class_levels(record: CharacterRecord) -> tuple[CharacterClassLevel, ...]:
    if record.class_levels:
        return tuple(record.class_levels)
    return (CharacterClassLevel(class_id=record.class_id, level=record.level),)


def class_level_for(record: CharacterRecord, class_id: str) -> int:
    for allocation in normalized_class_levels(record):
        if allocation.class_id == class_id:
            return allocation.level
    return 0


def total_character_level(record: CharacterRecord) -> int:
    allocations = normalized_class_levels(record)
    total = sum(allocation.level for allocation in allocations)
    return total or record.level


def has_subclass_selection(record: CharacterRecord, class_id: str) -> bool:
    return any(selection.class_id == class_id for selection in record.subclass_selections)


def subclass_selection_for(record: CharacterRecord, class_id: str) -> CharacterSubclassSelection | None:
    for selection in record.subclass_selections:
        if selection.class_id == class_id:
            return selection
    return None


@dataclass
class ContentCatalog:
    species: dict[str, SpeciesRecord]
    classes: dict[str, ClassRecord]
    backgrounds: dict[str, BackgroundRecord]
    feats: dict[str, FeatRecord]
    items: dict[str, ItemRecord]
    skills: dict[str, SkillRecord] = field(default_factory=dict)
    tools: dict[str, ToolRecord] = field(default_factory=dict)
    spells: dict[str, CreationSpellRecord] = field(default_factory=dict)


@dataclass
class CreationState:
    started: bool = False
    random_counter: int = 0
    species_id: str | None = None
    class_id: str | None = None
    class_skill_ids: tuple[str, ...] = ()
    background_id: str | None = None
    ability_draft: AbilityDraft = field(default_factory=AbilityDraft)
    assigned_abilities: dict[Ability, int] = field(default_factory=dict)
    background_asi_option_id: str | None = None
    background_asi_bonuses: dict[Ability, int] = field(default_factory=dict)
    selected_origin_feat_ids: tuple[str, ...] = ()
    resolved_creation_choices: dict[str, tuple[str, ...]] = field(default_factory=dict)
    background_equipment_mode: EquipmentSelectionMode | None = None
    background_package_id: str | None = None
    class_equipment_mode: EquipmentSelectionMode | None = None
    class_package_id: str | None = None
    inventory: dict[str, int] = field(default_factory=dict)
    currency_cp: int = 0
    character_record: CharacterRecord | None = None
    event_log: list[object] = field(default_factory=list)

    def final_ability_scores(self) -> dict[Ability, int]:
        if not self.assigned_abilities:
            return {}
        result = dict(self.assigned_abilities)
        for ability, bonus in self.background_asi_bonuses.items():
            result[ability] = result.get(ability, 0) + bonus
        return result


@dataclass(frozen=True)
class ChoiceView:
    option_id: str
    label: str
    detail: str


@dataclass(frozen=True)
class InspectionView:
    kind: ContentKind
    record_id: str
    name: str
    source: str
    detail_lines: tuple[str, ...]


@dataclass(frozen=True)
class CreationSnapshot:
    phase: CreationPhase
    summary_lines: tuple[str, ...]
    available_choices: dict[str, tuple[ChoiceView, ...]]




