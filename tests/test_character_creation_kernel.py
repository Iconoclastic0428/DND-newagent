from __future__ import annotations

from pathlib import Path
import unittest

from character_creation import build_default_kernel
from player_interface import SlashCommandInterface
from shared_types.errors import ValidationError
from shared_types.models import Ability, ChoiceSourceKind, ContentKind, CreationChoiceCategory, CreationPhase, SpellSelectionKind


LOCAL_MIRROR_BASE_URL = (Path(__file__).resolve().parents[1] / "5etools-mirror-2.github.io").resolve().as_uri().rstrip("/") + "/"


class CharacterCreationKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kernel = build_default_kernel(base_url=LOCAL_MIRROR_BASE_URL)
        self.ui = SlashCommandInterface(self.kernel)

    def _background_id(self, *, name: str, source: str) -> str:
        for record_id, record in self.kernel.catalog.backgrounds.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f"Background not found: {name} [{source}]")

    def _feat_id(self, *, name: str, source: str = "XPHB") -> str:
        for record_id, record in self.kernel.catalog.feats.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f"Feat not found: {name} [{source}]")

    def _asi_option_id(self, background_id: str, label: str) -> str:
        background = self.kernel.catalog.backgrounds[background_id]
        for option in background.ability_increase_options():
            if option.label == label:
                return option.option_id
        raise AssertionError(f"ASI option not found: {label}")

    def _tool_id(self, *, name: str) -> str:
        for record_id, record in self.kernel.catalog.tools.items():
            if record.name == name:
                return record_id
        raise AssertionError(f"Tool not found: {name}")

    def _class_skill_tokens_for(self, class_id: str) -> tuple[str, ...]:
        class_record = self.kernel.catalog.classes[class_id]
        if class_record.skill_choice_count <= 0:
            raise AssertionError(f"Class {class_record.name} does not expose any class skill choices.")
        if len(class_record.class_skill_option_ids) < class_record.skill_choice_count:
            raise AssertionError(
                f"Class {class_record.name} exposes only {len(class_record.class_skill_option_ids)} class skill option ids for {class_record.skill_choice_count} choices."
            )
        return tuple(class_record.class_skill_option_ids[: class_record.skill_choice_count])


    def _resolve_pending_choice_with_first_options(self, state):
        pending_choice = self.kernel._next_pending_creation_choice(state)
        if pending_choice is None:
            raise AssertionError('Expected a pending creation choice.')
        option_ids = tuple(option.option_id for option in pending_choice.group.options[: pending_choice.group.constraint.required_count])
        if len(option_ids) != pending_choice.group.constraint.required_count:
            raise AssertionError(f"Pending choice {pending_choice.group.choice_id} does not expose enough options.")
        return self.ui.execute(state, f"/create choose choice {pending_choice.group.choice_id} {' '.join(option_ids)}")

    def _resolve_all_pending_choices(self, state):
        output = ''
        while self.kernel.phase(state) == CreationPhase.CHOOSE_CREATION_CHOICES:
            state, output = self._resolve_pending_choice_with_first_options(state)
        return state, output

    def _complete_review_and_confirm(self, state):
        output = ''
        background = self.kernel.catalog.backgrounds[state.background_id]
        class_record = self.kernel.catalog.classes[state.class_id]
        commands = [
            '/create ability generate point-buy 15 14 13 12 10 8',
            '/create ability assign 15 14 13 12 10 8',
            f"/create background-asi choose {background.ability_increase_options()[0].option_id}",
        ]
        if background.package_options:
            commands.append(f"/create equipment background package {background.package_options[0].package_id}")
        elif background.gold_option_cp is not None:
            commands.append('/create equipment background gold')
        else:
            raise AssertionError('Background does not expose creation equipment choices.')
        if class_record.package_options:
            commands.append(f"/create equipment class package {class_record.package_options[0].package_id}")
        elif class_record.wealth_option is not None:
            commands.append('/create equipment class wealth')
        else:
            raise AssertionError('Class does not expose creation equipment choices.')
        commands.append('/create confirm')
        for command in commands:
            state, output = self.ui.execute(state, command)
        return state, output

    def _start(self, *, species_id: str = "aasimar", class_id: str = "wizard", class_skill_tokens: tuple[str, ...] = ("Arcana", "History")):
        state = self.kernel.new_state()
        last_output = ""
        for command in (
            "/create begin",
            f"/create choose species {species_id}",
            f"/create choose class {class_id}",
            "/create choose class-skills " + " ".join(class_skill_tokens),
        ):
            state, last_output = self.ui.execute(state, command)
        return state, last_output

    def _complete_wizard_acolyte(self):
        background_id = self._background_id(name="Acolyte", source="XPHB")
        state, _ = self._start()
        commands = (
            f"/create choose background {background_id}",
            "/create choose choice class:wizard:cantrips fire-bolt mage-hand light",
            "/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person",
            "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS",
            "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance",
            "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds",
            "/create ability generate point-buy 15 14 13 12 10 8",
            "/create ability assign 8 14 13 15 12 10",
            f"/create background-asi choose {self._asi_option_id(background_id, 'WIS +2, CHA +1')}",
            f"/create equipment background package {self.kernel.catalog.backgrounds[background_id].package_options[0].package_id}",
            "/create equipment class package wizard-package-1",
            "/create confirm",
        )
        output = ""
        for command in commands:
            state, output = self.ui.execute(state, command)
        return state, output

    def test_local_loader_exposes_extension_backgrounds_and_filters_creation_catalog_to_2024_skills_and_spells(self) -> None:
        fisher_id = self._background_id(name="Fisher", source="GOS")
        anthropologist_id = self._background_id(name="Anthropologist", source="TOA")
        self.assertIn(fisher_id, self.kernel.catalog.backgrounds)
        self.assertIn(anthropologist_id, self.kernel.catalog.backgrounds)
        self.assertTrue(all(record.source != "PHB" for record in self.kernel.catalog.backgrounds.values()))
        self.assertTrue(all(record.source == "XPHB" for record in self.kernel.catalog.skills.values()))
        self.assertTrue(all(record.source == "XPHB" for record in self.kernel.catalog.spells.values()))

        background_view = self.kernel.inspect(ContentKind.BACKGROUND, fisher_id)
        self.assertEqual(background_view.name, "Fisher")
        self.assertIn("Origin feat: choose custom origin feat", background_view.detail_lines)

    def test_wizard_and_magic_initiate_choices_block_ability_generation_until_resolved(self) -> None:
        background_id = self._background_id(name="Acolyte", source="XPHB")
        state, _ = self._start()
        state, output = self.ui.execute(state, f"/create choose background {background_id}")
        self.assertEqual(self.kernel.phase(state), CreationPhase.CHOOSE_CREATION_CHOICES)
        self.assertIn("Pending creation choice: Choose 3 cantrip(s).", output)
        self.assertIn("choice:class:wizard:cantrips:", output)

        with self.assertRaises(ValidationError):
            self.ui.execute(state, "/create ability generate roll")

        state, output = self.ui.execute(state, "/create choose choice class:wizard:cantrips fire-bolt mage-hand light")
        self.assertIn("Pending creation choice: Choose 4 level-1 spell(s).", output)
        state, output = self.ui.execute(state, "/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person")
        self.assertIn("Pending creation choice: Choose the spellcasting ability for Magic Initiate.", output)
        state, output = self.ui.execute(state, "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS")
        self.assertIn("Pending creation choice: Choose 2 cantrip(s) for Magic Initiate.", output)
        state, output = self.ui.execute(state, "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance")
        self.assertIn("Pending creation choice: Choose 1 level-1 spell(s) for Magic Initiate.", output)
        state, output = self.ui.execute(state, "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds")
        self.assertEqual(self.kernel.phase(state), CreationPhase.GENERATE_ABILITIES)
        self.assertIn("Phase: generate-abilities", output)


    def test_creation_snapshot_prompts_choice_counts_assignment_order_and_confirm_command(self) -> None:
        background_id = self._background_id(name="Acolyte", source="XPHB")
        state = self.kernel.new_state()
        for command in (
            "/create begin",
            "/create choose species human",
            "/create choose class bard",
        ):
            state, _ = self.ui.execute(state, command)

        snapshot = self.kernel.snapshot(state)
        summary = "\n".join(snapshot.summary_lines)
        self.assertIn("Class skill choices: Choose exactly 3 option(s).", summary)
        self.assertIn("Command: /create choose class-skills <skill-id ...>", summary)
        self.assertIn("Choose exactly 3 option(s).", snapshot.available_choices['class-skills'][0].detail)

        state, _ = self._start()
        state, _ = self.ui.execute(state, f"/create choose background {background_id}")
        snapshot = self.kernel.snapshot(state)
        summary = "\n".join(snapshot.summary_lines)
        self.assertIn("Pending creation choice: Choose 3 cantrip(s).", summary)
        self.assertIn("Choose exactly 3 option(s).", summary)
        self.assertIn("Command: /create choose choice class:wizard:cantrips <option-id ...>", summary)
        cantrip_group = snapshot.available_choices['choice:class:wizard:cantrips']
        self.assertIn("Choose exactly 3 option(s).", cantrip_group[0].detail)

        state, _ = self._resolve_all_pending_choices(state)
        state, _ = self.ui.execute(state, "/create ability generate point-buy 15 14 13 12 10 8")
        snapshot = self.kernel.snapshot(state)
        summary = "\n".join(snapshot.summary_lines)
        self.assertIn("Ability order: STR DEX CON INT WIS CHA", summary)
        self.assertIn("Command: /create ability assign 15 14 13 12 10 8", summary)
        assignment_choice = snapshot.available_choices['ability-assignment'][0]
        self.assertEqual(assignment_choice.option_id, '15 14 13 12 10 8')
        self.assertIn("STR DEX CON INT WIS CHA", assignment_choice.detail)

        state, _ = self.ui.execute(state, "/create ability assign 15 14 13 12 10 8")
        background = self.kernel.catalog.backgrounds[background_id]
        class_record = self.kernel.catalog.classes[state.class_id]
        state, _ = self.ui.execute(state, f"/create background-asi choose {background.ability_increase_options()[0].option_id}")
        state, _ = self.ui.execute(state, f"/create equipment background package {background.package_options[0].package_id}")
        state, _ = self.ui.execute(state, f"/create equipment class package {class_record.package_options[0].package_id}")
        snapshot = self.kernel.snapshot(state)
        self.assertEqual(snapshot.phase, CreationPhase.REVIEW)
        self.assertIn("Command: /create confirm", "\n".join(snapshot.summary_lines))
        self.assertIn('confirm', snapshot.available_choices)

    def test_bard_class_skill_pool_supports_any_three_skills(self) -> None:
        state = self.kernel.new_state()
        for command in (
            '/create begin',
            '/create choose species human',
            '/create choose class bard',
        ):
            state, _ = self.ui.execute(state, command)
        bard = self.kernel.catalog.classes['bard']
        self.assertEqual(bard.skill_choice_count, 3)
        self.assertEqual(len(bard.class_skill_option_ids), len(self.kernel.catalog.skills))
        state, output = self.ui.execute(state, '/create choose class-skills ' + ' '.join(self._class_skill_tokens_for('bard')))
        self.assertEqual(self.kernel.phase(state), CreationPhase.CHOOSE_BACKGROUND)
        self.assertIn('Phase: choose-background', output)

    def test_human_can_choose_class_skills_for_every_loaded_class(self) -> None:
        for class_id, class_record in sorted(self.kernel.catalog.classes.items()):
            with self.subTest(class_id=class_id):
                state = self.kernel.new_state()
                for command in (
                    '/create begin',
                    '/create choose species human',
                    f'/create choose class {class_id}',
                ):
                    state, _ = self.ui.execute(state, command)
                self.assertEqual(self.kernel.phase(state), CreationPhase.CHOOSE_CLASS_SKILLS)
                state, output = self.ui.execute(state, '/create choose class-skills ' + ' '.join(self._class_skill_tokens_for(class_id)))
                self.assertEqual(self.kernel.phase(state), CreationPhase.CHOOSE_BACKGROUND)
                self.assertIn('Phase: choose-background', output)


    def test_fighter_fighting_style_uses_all_xphb_level_one_style_feats(self) -> None:
        state, _ = self._start(species_id='human', class_id='fighter', class_skill_tokens=('acrobatics', 'athletics'))
        background_id = self._background_id(name='Acolyte', source='XPHB')
        state, output = self.ui.execute(state, f'/create choose background {background_id}')
        self.assertIn('choice:class:fighter:fighting-style:', output)
        expected_style_ids = tuple(sorted(feat.record_id for feat in self.kernel.catalog.feats.values() if feat.category == 'FS'))
        actual_style_ids = tuple(sorted(option.option_id for option in self.kernel._fighter_fighting_style_choice(state).group.options))
        self.assertEqual(actual_style_ids, expected_style_ids)

    def test_rogue_expertise_and_weapon_mastery_compile_into_character_record(self) -> None:
        background_id = self._background_id(name='Acolyte', source='XPHB')
        state, _ = self._start(species_id='human', class_id='rogue', class_skill_tokens=('acrobatics', 'deception', 'insight', 'stealth'))
        state, _ = self.ui.execute(state, f'/create choose background {background_id}')
        state, _ = self.ui.execute(state, '/create choose choice class:rogue:expertise acrobatics thieves-tools')
        state, _ = self.ui.execute(state, '/create choose choice class:rogue:weapon-mastery dagger shortbow')
        state, _ = self._resolve_all_pending_choices(state)
        state, _ = self._complete_review_and_confirm(state)
        record = state.character_record
        assert record is not None
        self.assertEqual(record.expertise_skill_ids, ('acrobatics',))
        self.assertEqual(record.expertise_tool_ids, ('thieves-tools',))
        self.assertEqual(record.weapon_mastery_item_ids, ('dagger', 'shortbow'))
        self.assertIn('Sneak Attack', record.class_feature_names)
        self.assertIn("Thieves' Cant", record.class_feature_names)

    def test_ranger_favored_enemy_adds_hunters_mark_to_level_one_spell_selections(self) -> None:
        background_id = self._background_id(name='Acolyte', source='XPHB')
        state, _ = self._start(species_id='human', class_id='ranger', class_skill_tokens=('athletics', 'perception', 'survival'))
        state, _ = self.ui.execute(state, f'/create choose background {background_id}')
        state, _ = self._resolve_all_pending_choices(state)
        state, _ = self._complete_review_and_confirm(state)
        record = state.character_record
        assert record is not None
        hunter_mark = [selection for selection in record.spell_selections if selection.spell_name == "Hunter's Mark" and selection.source.source_kind == ChoiceSourceKind.CLASS]
        self.assertTrue(hunter_mark)
        self.assertIn(SpellSelectionKind.ALWAYS_PREPARED, {selection.selection_kind for selection in hunter_mark})
        self.assertIn('Favored Enemy', record.class_feature_names)

    def test_human_can_reach_generate_abilities_for_every_loaded_class_after_required_level_one_choices(self) -> None:
        background_id = self._background_id(name='Acolyte', source='XPHB')
        for class_id, class_record in sorted(self.kernel.catalog.classes.items()):
            with self.subTest(class_id=class_id):
                state = self.kernel.new_state()
                for command in (
                    '/create begin',
                    '/create choose species human',
                    f'/create choose class {class_id}',
                    '/create choose class-skills ' + ' '.join(self._class_skill_tokens_for(class_id)),
                    f'/create choose background {background_id}',
                ):
                    state, _ = self.ui.execute(state, command)
                state, output = self._resolve_all_pending_choices(state)
                self.assertEqual(self.kernel.phase(state), CreationPhase.GENERATE_ABILITIES)
                self.assertIn('Phase: generate-abilities', output)

    def test_cleric_divine_order_blocks_creation_and_applies_protector_grants(self) -> None:
        background_id = self._background_id(name='Acolyte', source='XPHB')
        state, _ = self._start(species_id='human', class_id='cleric', class_skill_tokens=('history', 'insight'))
        state, output = self.ui.execute(state, f'/create choose background {background_id}')
        self.assertIn('choice:class:cleric:feature:divine-order:', output)
        with self.assertRaises(ValidationError):
            self.ui.execute(state, '/create ability generate point-buy 15 14 13 12 10 8')
        state, output = self.ui.execute(state, '/create choose choice class:cleric:feature:divine-order protector')
        self.assertIn('Pending creation choice: Choose 3 cantrip(s).', output)
        state, _ = self._resolve_all_pending_choices(state)
        state, output = self._complete_review_and_confirm(state)
        self.assertEqual(self.kernel.phase(state), CreationPhase.COMPLETE)
        record = state.character_record
        assert record is not None
        self.assertIn('heavy', record.armor_training)
        self.assertIn('martial', record.weapon_proficiencies)
        self.assertIn('Divine Order: Protector', record.traits)
        self.assertIn(CreationChoiceCategory.CLASS_FEATURE, {choice.category for choice in record.resolved_creation_choices})

    def test_druid_primal_order_magician_adds_bonus_cantrip_choice(self) -> None:
        background_id = self._background_id(name='Acolyte', source='XPHB')
        state, _ = self._start(species_id='human', class_id='druid', class_skill_tokens=('arcana', 'animal-handling'))
        state, output = self.ui.execute(state, f'/create choose background {background_id}')
        self.assertIn('choice:class:druid:feature:primal-order:', output)
        state, _ = self.ui.execute(state, '/create choose choice class:druid:feature:primal-order magician')
        state, _ = self.ui.execute(state, '/create choose choice class:druid:cantrips druidcraft guidance')
        state, output = self.ui.execute(state, '/create choose choice class:druid:spells cure-wounds detect-magic faerie-fire healing-word')
        self.assertIn('choice:class:druid:feature:primal-order:magician-cantrip:', output)
        self.assertIn('mending', output)

    def test_warlock_invocation_choice_filters_illegal_options_and_supports_pact_of_the_tome_followups(self) -> None:
        background_id = self._background_id(name='Acolyte', source='XPHB')
        state, _ = self._start(species_id='human', class_id='warlock', class_skill_tokens=('arcana', 'deception'))
        state, output = self.ui.execute(state, f'/create choose background {background_id}')
        self.assertIn('choice:class:warlock:feature:eldritch-invocation-options:', output)
        self.assertIn('armor-of-shadows', output)
        self.assertIn('pact-of-the-tome', output)
        self.assertNotIn('agonizing-blast', output)
        self.assertNotIn('repelling-blast', output)
        state, _ = self.ui.execute(state, '/create choose choice class:warlock:feature:eldritch-invocation-options pact-of-the-tome')
        state, _ = self.ui.execute(state, '/create choose choice class:warlock:cantrips eldritch-blast mage-hand')
        state, _ = self.ui.execute(state, '/create choose choice class:warlock:spells charm-person hex')
        state, output = self.ui.execute(state, '/create choose choice class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-cantrips guidance light mending')
        self.assertIn('choice:class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-rituals:', output)
        state, _ = self.ui.execute(state, '/create choose choice class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-rituals detect-magic unseen-servant')
        state, _ = self._resolve_all_pending_choices(state)
        state, _ = self._complete_review_and_confirm(state)
        record = state.character_record
        assert record is not None
        spell_names = {selection.spell_name for selection in record.spell_selections}
        self.assertIn('Detect Magic', spell_names)
        self.assertIn('Unseen Servant', spell_names)
        self.assertIn('Guidance', spell_names)
        self.assertIn('Pact of the Tome', ' '.join(record.traits))

    def test_selectable_background_skills_come_from_local_skill_catalog(self) -> None:
        investigator_id = self._background_id(name="Investigator", source="VRGR")
        state, _ = self._start(class_id="monk", class_skill_tokens=("Acrobatics", "Athletics"))
        state, output = self.ui.execute(state, f"/create choose background {investigator_id}")
        while "choice:background:investigator:skills:" not in output:
            state, output = self._resolve_pending_choice_with_first_options(state)
        self.assertIn("choice:background:investigator:skills:", output)
        self.assertIn("insight", output)
        self.assertIn("investigation", output)
        self.assertIn("perception", output)
        alert_id = self._feat_id(name="Alert")
        state, output = self.ui.execute(state, "/create choose choice background:investigator:skills insight investigation")
        while "choice:background:investigator:origin-feat:" not in output:
            state, output = self._resolve_pending_choice_with_first_options(state)
        self.assertIn("choice:background:investigator:origin-feat:", output)
        state, output = self.ui.execute(state, f"/create choose choice background:investigator:origin-feat {alert_id}")
        self.assertIn("Phase: generate-abilities", output)

    def test_human_custom_origin_feat_chains_into_skilled_and_musician_subchoices(self) -> None:
        fisher_id = self._background_id(name="Fisher", source="GOS")
        skilled_id = self._feat_id(name="Skilled")
        musician_id = self._feat_id(name="Musician")
        state, _ = self._start(species_id="human", class_id="monk", class_skill_tokens=("Acrobatics", "Athletics"))
        state, output = self.ui.execute(state, f"/create choose background {fisher_id}")
        while "choice:background:fisher:origin-feat:" not in output:
            state, output = self._resolve_pending_choice_with_first_options(state)
        self.assertIn("choice:background:fisher:origin-feat:", output)
        state, output = self.ui.execute(state, f"/create choose origin-feat {skilled_id}")
        self.assertIn("choice:background:fisher:origin-feat:skilled-skill-or-tool:", output)
        flute_id = self._tool_id(name="Flute")
        state, output = self.ui.execute(state, f"/create choose choice background:fisher:origin-feat:skilled-skill-or-tool arcana investigation {flute_id}")
        self.assertIn("choice:species:human:origin-feat-1:", output)
        state, output = self.ui.execute(state, f"/create choose choice species:human:origin-feat-1 {musician_id}")
        self.assertIn("choice:species:human:origin-feat-1:musician-tools:", output)
        bagpipes_id = self._tool_id(name="Bagpipes")
        drum_id = self._tool_id(name="Drum")
        horn_id = self._tool_id(name="Horn")
        state, output = self.ui.execute(state, f"/create choose choice species:human:origin-feat-1:musician-tools {bagpipes_id} {drum_id} {horn_id}")
        self.assertEqual(self.kernel.phase(state), CreationPhase.GENERATE_ABILITIES)

    def test_confirm_is_blocked_while_creation_choices_are_unresolved(self) -> None:
        background_id = self._background_id(name="Acolyte", source="XPHB")
        state, _ = self._start()
        state, _ = self.ui.execute(state, f"/create choose background {background_id}")
        with self.assertRaises(ValidationError):
            self.ui.execute(state, "/create confirm")

    def test_final_character_record_contains_spells_feat_grants_and_choice_metadata(self) -> None:
        state, output = self._complete_wizard_acolyte()
        self.assertEqual(self.kernel.phase(state), CreationPhase.COMPLETE)
        self.assertIn("Phase: complete", output)

        record = state.character_record
        assert record is not None
        self.assertEqual(record.class_skill_proficiencies, ("Arcana", "History"))
        self.assertEqual(record.background_skill_proficiencies, ("Insight", "Religion"))
        self.assertIn("Calligrapher's Supplies", record.tool_proficiencies)
        self.assertEqual(record.origin_feats, ("Magic Initiate",))

        class_spell_names = {selection.spell_name for selection in record.spell_selections if selection.source.source_kind == ChoiceSourceKind.CLASS}
        feat_spell_names = {selection.spell_name for selection in record.spell_selections if selection.source.source_kind == ChoiceSourceKind.FEAT}
        self.assertEqual(class_spell_names, {"Fire Bolt", "Mage Hand", "Light", "Magic Missile", "Shield", "Detect Magic", "Charm Person"})
        self.assertEqual(feat_spell_names, {"Guidance", "Resistance", "Cure Wounds"})
        self.assertIn(SpellSelectionKind.PREPARED, {selection.selection_kind for selection in record.spell_selections})
        self.assertIn(SpellSelectionKind.INNATE, {selection.selection_kind for selection in record.spell_selections})
        self.assertEqual(record.feat_grants[0].feat_name, "Magic Initiate")
        self.assertEqual(dict(record.feat_grants[0].fixed_metadata)["spell_list_class_id"], "cleric")

        choice_categories = {choice.category for choice in record.resolved_creation_choices}
        self.assertIn(CreationChoiceCategory.CANTRIP, choice_categories)
        self.assertIn(CreationChoiceCategory.SPELL, choice_categories)
        self.assertIn(CreationChoiceCategory.SPELLCASTING_ABILITY, choice_categories)


if __name__ == "__main__":
    unittest.main()


