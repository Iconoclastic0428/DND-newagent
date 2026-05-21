from __future__ import annotations

import unittest

from training.rewards import action_reward_components


class RewardSignalTests(unittest.TestCase):
    def test_combat_actions_pay_a_small_step_cost(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={'runtime_mode': 'combat', 'event_count': 10},
            state_after={'runtime_mode': 'combat', 'event_count': 11},
        )

        self.assertEqual(rewards['valid_action'], 0.01)
        self.assertEqual(rewards['state_progress'], 0.02)
        self.assertEqual(rewards['combat_step_cost'], -0.04)

    def test_noncombat_actions_do_not_pay_combat_step_cost(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={'runtime_mode': 'storytelling', 'event_count': 10},
            state_after={'runtime_mode': 'storytelling', 'event_count': 11},
        )

        self.assertNotIn('combat_step_cost', rewards)

    def test_support_rewards_are_computed_from_state_deltas(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={
                'party_hp_current': 10,
                'monster_hp_current': 20,
                'party_temp_hp': 0,
                'monster_temp_hp': 0,
                'party_buff_effect_count': 0,
                'party_help_effect_count': 0,
            },
            state_after={
                'party_hp_current': 15,
                'monster_hp_current': 20,
                'party_temp_hp': 4,
                'monster_temp_hp': 0,
                'party_buff_effect_count': 1,
                'party_help_effect_count': 1,
            },
        )

        self.assertEqual(rewards['ally_healing'], 0.15)
        self.assertEqual(rewards['ally_temp_hp_gained'], 0.08)
        self.assertEqual(rewards['ally_buff_applied'], 0.1)
        self.assertEqual(rewards['ally_help_provided'], 0.08)
        self.assertNotIn('enemy_damage', rewards)

    def test_enemy_debuff_rewards_use_specific_non_overlapping_buckets(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={
                'monster_action_debuff_count': 0,
                'monster_control_debuff_count': 0,
                'monster_accuracy_debuff_count': 0,
                'monster_defense_debuff_count': 0,
                'monster_mobility_debuff_count': 0,
                'monster_general_debuff_count': 0,
            },
            state_after={
                'monster_action_debuff_count': 1,
                'monster_control_debuff_count': 1,
                'monster_accuracy_debuff_count': 1,
                'monster_defense_debuff_count': 1,
                'monster_mobility_debuff_count': 1,
                'monster_general_debuff_count': 1,
            },
        )

        self.assertEqual(rewards['enemy_action_debuff_applied'], 0.25)
        self.assertEqual(rewards['enemy_control_applied'], 0.2)
        self.assertEqual(rewards['enemy_accuracy_debuff_applied'], 0.12)
        self.assertEqual(rewards['enemy_defense_debuff_applied'], 0.12)
        self.assertEqual(rewards['enemy_mobility_debuff_applied'], 0.12)
        self.assertEqual(rewards['enemy_general_debuff_applied'], 0.08)
        self.assertNotIn('enemy_debuff_applied', rewards)

    def test_bad_support_outcomes_are_penalized(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={
                'monster_hp_current': 10,
                'monster_temp_hp': 0,
                'monster_buff_effect_count': 0,
                'monster_help_effect_count': 0,
                'party_control_debuff_count': 0,
            },
            state_after={
                'monster_hp_current': 14,
                'monster_temp_hp': 3,
                'monster_buff_effect_count': 1,
                'monster_help_effect_count': 1,
                'party_control_debuff_count': 1,
            },
        )

        self.assertEqual(rewards['enemy_healing'], -0.12)
        self.assertEqual(rewards['enemy_temp_hp_gained'], -0.06)
        self.assertEqual(rewards['enemy_buff_applied'], -0.1)
        self.assertEqual(rewards['enemy_help_provided'], -0.08)
        self.assertEqual(rewards['ally_control_debuffed'], -0.2)

    def test_scene_goal_and_hidden_subgoal_completion_are_rewarded(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
                'party_goal_count': 2,
                'open_loop_count': 3,
                'scene_goal_completion_count': 1,
                'hidden_subgoal_completion_count': 0,
                'known_discovery_count': 0,
                'social_revealed_topic_count': 0,
            },
            state_after={
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
                'party_goal_count': 1,
                'open_loop_count': 2,
                'scene_goal_completion_count': 3,
                'hidden_subgoal_completion_count': 1,
                'known_discovery_count': 1,
                'social_revealed_topic_count': 1,
            },
        )

        self.assertEqual(rewards['party_goal_resolved'], 0.25)
        self.assertEqual(rewards['open_loop_resolved'], 0.2)
        self.assertEqual(rewards['scene_goal_completed'], 0.7)
        self.assertEqual(rewards['hidden_subgoal_completed'], 0.35)
        self.assertEqual(rewards['discovery_made'], 0.12)
        self.assertEqual(rewards['social_topic_revealed'], 0.08)
        self.assertNotIn('stalled_scene_turn', rewards)

    def test_story_turn_without_scene_goal_or_hidden_subgoal_progress_is_penalized(self) -> None:
        rewards = action_reward_components(
            error=None,
            raw_text='Gundren, can you repeat the plan again?',
            state_before={
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
                'transcript_count': 10,
                'party_goal_count': 2,
                'open_loop_count': 3,
                'scene_goal_completion_count': 1,
                'hidden_subgoal_completion_count': 1,
                'known_discovery_count': 0,
                'social_revealed_topic_count': 0,
            },
            state_after={
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
                'transcript_count': 11,
                'party_goal_count': 2,
                'open_loop_count': 3,
                'scene_goal_completion_count': 1,
                'hidden_subgoal_completion_count': 1,
                'known_discovery_count': 0,
                'social_revealed_topic_count': 0,
            },
        )

        self.assertEqual(rewards['story_progress'], 0.05)
        self.assertLess(rewards['stalled_scene_turn'], 0.0)

    def test_repetitive_words_and_repeated_actions_are_penalized(self) -> None:
        rewards = action_reward_components(
            error=None,
            raw_text='Gundren danger danger danger danger road road road road?',
            state_before={
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
                'recent_player_input_texts': (
                    'Gundren danger danger danger danger road road road road?',
                ),
            },
            state_after={
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
            },
        )

        self.assertLess(rewards['repetitive_words'], 0.0)
        self.assertLess(rewards['repetitive_action'], 0.0)


if __name__ == '__main__':
    unittest.main()
