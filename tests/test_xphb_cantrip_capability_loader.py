from __future__ import annotations

import json
from pathlib import Path
import unittest

from rules_engine.capability_loader import build_spell_capability_definition
from shared_types.capabilities import (
    AttackRollGateEffect,
    ChosenDamageReductionEffectDef,
    ChosenSkillBonusEffectDef,
    ChosenWeaponEnchantmentEffectDef,
    FriendsEffectDef,
    HeldConjurationEffectDef,
    InstantWeaponStrikeEffectDef,
    ParameterizedIllusionEffectDef,
    RecursiveSpellAttackEffectDef,
    SaveGateEffect,
    StabilizeEffectDef,
    StartActiveEffectDef,
)

MIRROR_ROOT = Path('D:/5etools-mirror-2.github.io')


def _load_spell(name: str) -> dict[str, object]:
    payload = json.loads((MIRROR_ROOT / 'data' / 'spells' / 'spells-xphb.json').read_text(encoding='utf-8-sig'))
    for record in payload['spell']:
        english_name = record.get('ENG_name') or record.get('name')
        if english_name == name:
            return record
    raise AssertionError(f'Missing local XPHB spell record for {name}.')


class XphbCantripCapabilityLoaderTests(unittest.TestCase):
    def test_direct_attack_and_save_cantrips_build_deterministic_capabilities(self) -> None:
        for name in (
            'Acid Splash',
            'Eldritch Blast',
            'Fire Bolt',
            'Poison Spray',
            'Sacred Flame',
            'Thunderclap',
            'Word of Radiance',
            'Toll the Dead',
        ):
            capability = build_spell_capability_definition(_load_spell(name))
            self.assertIsNotNone(capability, name)
            self.assertIn(type(capability.effect), {AttackRollGateEffect, SaveGateEffect})

    def test_rider_cantrips_build_active_effect_hooks(self) -> None:
        expected = {
            'Blade Ward': 'incoming_attack_roll_penalty',
            'Chill Touch': 'healing_blocked',
            'Mind Sliver': 'next_saving_throw_penalty',
            'Ray of Frost': 'speed_penalty_ft',
            'Shocking Grasp': 'blocks_opportunity_attacks',
            'Starry Wisp': 'suppress_invisible_benefits',
            'Vicious Mockery': 'next_attack_roll_disadvantage',
        }
        for name, field_name in expected.items():
            capability = build_spell_capability_definition(_load_spell(name))
            self.assertIsNotNone(capability, name)
            if isinstance(capability.effect, StartActiveEffectDef):
                active = capability.effect.active_effect
            else:
                gate = capability.effect
                self.assertIn(type(gate), {AttackRollGateEffect, SaveGateEffect})
                branch = gate.on_hit if isinstance(gate, AttackRollGateEffect) else gate.on_failure
                active = next(effect.active_effect for effect in branch if isinstance(effect, StartActiveEffectDef))
            value = getattr(active, field_name)
            self.assertTrue(value, f'{name} missing {field_name}')

    def test_guidance_light_and_minor_illusion_use_exact_runtime_definitions(self) -> None:
        guidance = build_spell_capability_definition(_load_spell('Guidance'))
        self.assertIsNotNone(guidance)
        self.assertIsInstance(guidance.effect, ChosenSkillBonusEffectDef)
        self.assertIn('Arcana', guidance.effect.allowed_skill_names)

        light = build_spell_capability_definition(_load_spell('Light'))
        self.assertIsNotNone(light)
        self.assertIsInstance(light.effect, StartActiveEffectDef)
        self.assertEqual(light.effect.active_effect.persistent_areas[0].bright_light_radius_ft, 20)

        illusion = build_spell_capability_definition(_load_spell('Minor Illusion'))
        self.assertIsNotNone(illusion)
        self.assertIsInstance(illusion.effect, ParameterizedIllusionEffectDef)

    def test_spare_the_dying_uses_stabilize_effect(self) -> None:
        capability = build_spell_capability_definition(_load_spell('Spare the Dying'))
        self.assertIsNotNone(capability)
        self.assertIsInstance(capability.effect, StabilizeEffectDef)

    def test_remaining_cantrips_have_runtime_support_modes_matching_the_loader(self) -> None:
        expected_types = {
            'Dancing Lights': (HeldConjurationEffectDef,),
            'Friends': (FriendsEffectDef,),
            'Mage Hand': (HeldConjurationEffectDef,),
            'Produce Flame': (HeldConjurationEffectDef,),
            'Resistance': (ChosenDamageReductionEffectDef,),
            'Shillelagh': (ChosenWeaponEnchantmentEffectDef,),
            'Sorcerous Burst': (RecursiveSpellAttackEffectDef,),
            'True Strike': (InstantWeaponStrikeEffectDef,),
        }
        for name, expected in expected_types.items():
            capability = build_spell_capability_definition(_load_spell(name))
            self.assertIsNotNone(capability, name)
            self.assertIsInstance(capability.effect, expected)

    def test_story_adjudicated_cantrips_remain_unbound_to_direct_capabilities(self) -> None:
        for name in (
            'Druidcraft',
            'Elementalism',
            'Mending',
            'Message',
            'Prestidigitation',
            'Thaumaturgy',
        ):
            capability = build_spell_capability_definition(_load_spell(name))
            self.assertIsNone(capability, name)
