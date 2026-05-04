from __future__ import annotations

import unittest

from tests.xphb_cantrips.support import StoryCantripTestCase


class ComprehendLanguagesLevel1SpellTests(StoryCantripTestCase):
    SPELL_NAME = 'Comprehend Languages'
    SPELL_SLUG = 'comprehend-languages'

    def _setup_session(self):
        session, _ = self.build_story_session([])
        self.grant_spell(session, self.SPELL_NAME)
        return session

    def _apply_story_spell(self, session):
        actor = session.state.actors['player-1']
        spell = actor.spells[self.SPELL_SLUG]
        events = session.encounter_session.control_runtime.kernel.effect_executor.execute_spell(session.state, actor=actor, spell=spell)
        for event in events:
            session.state.event_log.append(event)
            session._apply_runtime_event(event)
        return events

    def test_story_cast_intent_uses_self_targetless_syntax(self) -> None:
        session = self._setup_session()
        intent = session._story_mode_cast_intent('/cast player-1 comprehend-languages')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertIsNone(intent.target_id)

    def test_cast_sets_the_understand_all_languages_flag(self) -> None:
        session = self._setup_session()
        self._apply_story_spell(session)
        self.assertTrue(session.state.actors['player-1'].understand_all_languages)

    def test_effect_definition_uses_one_hour_duration_and_replacement(self) -> None:
        session = self._setup_session()
        self._apply_story_spell(session)
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == self.SPELL_NAME)
        self.assertEqual(effect.definition.duration.rounds, 600)
        self.assertTrue(effect.definition.replace_existing_same_name_from_source)

    def test_recasting_replaces_the_existing_effect_instance(self) -> None:
        session = self._setup_session()
        self._apply_story_spell(session)
        first_ids = [effect.effect_instance_id for effect in session.state.active_effects.values() if effect.name == self.SPELL_NAME]
        self._apply_story_spell(session)
        second_ids = [effect.effect_instance_id for effect in session.state.active_effects.values() if effect.name == self.SPELL_NAME]
        self.assertEqual(len(second_ids), 1)
        self.assertNotEqual(first_ids[0], second_ids[0])

    def test_ending_the_effect_clears_the_language_flag(self) -> None:
        session = self._setup_session()
        self._apply_story_spell(session)
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == self.SPELL_NAME)
        for event in session.encounter_session.control_runtime.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end'):
            session.state.event_log.append(event)
            session._apply_runtime_event(event)
        self.assertFalse(session.state.actors['player-1'].understand_all_languages)

    def test_adjudication_context_mentions_language_comprehension_after_the_cast(self) -> None:
        session = self._setup_session()
        self._apply_story_spell(session)
        context = session._build_adjudication_context(controller_id='player-1-controller', actor_id='player-1', declaration='Read the strange inscription.')
        self.assertIn('understands all languages', context.actor_status_summary)

    def test_adjudication_context_omits_the_language_tag_before_the_cast(self) -> None:
        session = self._setup_session()
        context = session._build_adjudication_context(controller_id='player-1-controller', actor_id='player-1', declaration='Read the strange inscription.')
        self.assertNotIn('understands all languages', context.actor_status_summary)


if __name__ == '__main__':
    unittest.main()
