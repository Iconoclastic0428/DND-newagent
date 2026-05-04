from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProgressionMode(str, Enum):
    XP = 'xp'
    MILESTONE = 'milestone'


class XPDistributionPolicy(str, Enum):
    PARTY_WIDE = 'party_wide'
    EQUAL_SHARE = 'equal_share'
    INDIVIDUAL = 'individual'


class MilestoneDistributionPolicy(str, Enum):
    PARTY_WIDE = 'party_wide'
    SUBSET = 'subset'


class ProgressionRecipientScope(str, Enum):
    PARTY = 'party'
    SUBSET = 'subset'
    INDIVIDUAL = 'individual'


class XPRewardSourceType(str, Enum):
    COMBAT_ENCOUNTER_COMPLETION = 'combat_encounter_completion'
    STORY_ENCOUNTER_RESOLUTION = 'story_encounter_resolution'
    HAZARD = 'hazard'
    TRAP = 'trap'
    EXPLORATION_DISCOVERY = 'exploration_discovery'
    QUEST_OBJECTIVE = 'quest_objective'
    SOCIAL_RESOLUTION = 'social_resolution'
    DM_MANUAL = 'dm_manual'


class MilestoneSourceType(str, Enum):
    QUEST_COMPLETED = 'quest_completed'
    CHAPTER_BEAT_REACHED = 'chapter_beat_reached'
    DUNGEON_REGION_CLEAR = 'dungeon_region_clear'
    MAJOR_NPC_FACTION_OUTCOME = 'major_npc_faction_outcome'
    STORY_SCENE_COMPLETION = 'story_scene_completion'
    BOSS_VILLAIN_RESOLUTION = 'boss_villain_resolution'
    DM_MANUAL_MILESTONE = 'dm_manual_milestone'
    CAMPAIGN_AUTHORED_TRIGGER = 'campaign_authored_trigger'


class MilestoneCompletionState(str, Enum):
    COMPLETED = 'completed'


XP_LEVEL_THRESHOLDS: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}
MAX_CHARACTER_LEVEL = 20


@dataclass(frozen=True)
class ProgressionPolicy:
    xp_distribution: XPDistributionPolicy = XPDistributionPolicy.EQUAL_SHARE
    milestone_distribution: MilestoneDistributionPolicy = MilestoneDistributionPolicy.PARTY_WIDE
    show_xp_to_players: bool = True
    reveal_milestone_progress_to_players: bool = False
    allow_multiple_pending_level_ups: bool = True


@dataclass(frozen=True)
class XPRecipientAward:
    actor_id: str
    actor_label: str
    xp_amount: int


@dataclass(frozen=True)
class MilestoneRecipientAward:
    actor_id: str
    actor_label: str
    advancement_steps: int = 1


@dataclass(frozen=True)
class XPRewardRecord:
    reward_id: str
    source_type: XPRewardSourceType
    source_id: str
    campaign_id: str
    session_id: str
    scene_id: str | None
    location_id: str | None
    recipients: tuple[XPRecipientAward, ...]
    recipient_scope: ProgressionRecipientScope
    configured_xp_amount: int
    award_reason: str
    timestamp_seconds: int
    dedupe_key: str
    applied: bool = True


@dataclass(frozen=True)
class MilestoneRecord:
    milestone_id: str
    source_type: MilestoneSourceType
    source_id: str
    campaign_id: str
    session_id: str
    scene_id: str | None
    location_id: str | None
    recipients: tuple[MilestoneRecipientAward, ...]
    recipient_scope: ProgressionRecipientScope
    completion_state: MilestoneCompletionState
    advancement_granted: bool
    award_reason: str
    timestamp_seconds: int
    dedupe_key: str


@dataclass(frozen=True)
class PendingLevelUpRecord:
    pending_id: str
    actor_id: str
    actor_label: str
    target_new_total_level: int
    source_mode: ProgressionMode
    source_reward_ids: tuple[str, ...] = ()
    source_milestone_ids: tuple[str, ...] = ()
    created_timestamp_seconds: int = 0
    applied: bool = False
    blocked_by_unresolved_upgrade_choices: bool = True


@dataclass(frozen=True)
class ActorProgressState:
    actor_id: str
    actor_label: str
    current_level: int
    xp_total: int = 0
    completed_milestone_ids: tuple[str, ...] = ()
    granted_milestone_advancements: int = 0
    eligible_level: int = 1
    next_level_xp_threshold: int | None = None
    pending_level_up_ids: tuple[str, ...] = ()
    last_reward_id: str | None = None
    last_milestone_id: str | None = None


@dataclass
class CampaignProgressionState:
    mode: ProgressionMode = ProgressionMode.XP
    policy: ProgressionPolicy = field(default_factory=ProgressionPolicy)
    actor_progress: dict[str, ActorProgressState] = field(default_factory=dict)
    xp_rewards: dict[str, XPRewardRecord] = field(default_factory=dict)
    milestone_records: dict[str, MilestoneRecord] = field(default_factory=dict)
    pending_level_ups: dict[str, PendingLevelUpRecord] = field(default_factory=dict)
    xp_dedupe: dict[str, str] = field(default_factory=dict)
    milestone_dedupe: dict[str, str] = field(default_factory=dict)
