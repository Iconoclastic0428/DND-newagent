from __future__ import annotations

import unittest

from training.rewards import action_reward_components


class RewardSignalTests(unittest.TestCase):
    def test_support_rewards_are_computed_from_state_deltas(self) -> None:
        rewards = action_reward_components(
            error=None,
            state_before={
                'party_hp_current': 10,
                'monster_hp_current': 20,
                'party_temp_hp': 0,
                'monster_temp_hp': 0,
                'party_buff_effect_count': 0,
            },
            state_after={
                'party_hp_current': 15,
                'monster_hp_current': 20,
                'party_temp_hp': 4,
                'monster_temp_hp': 0,
                'party_buff_effect_count': 1,
            },
        )

        self.assertEqual(rewards['ally_healing'], 0.15)
        self.assertEqual(rewards['ally_temp_hp_gained'], 0.08)
        self.assertEqual(rewards['ally_buff_applied'], 0.1)
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
                'party_control_debuff_count': 0,
            },
            state_after={
                'monster_hp_current': 14,
                'monster_temp_hp': 3,
                'monster_buff_effect_count': 1,
                'party_control_debuff_count': 1,
            },
        )

        self.assertEqual(rewards['enemy_healing'], -0.12)
        self.assertEqual(rewards['enemy_temp_hp_gained'], -0.06)
        self.assertEqual(rewards['enemy_buff_applied'], -0.1)
        self.assertEqual(rewards['ally_control_debuffed'], -0.2)


if __name__ == '__main__':
    unittest.main()
