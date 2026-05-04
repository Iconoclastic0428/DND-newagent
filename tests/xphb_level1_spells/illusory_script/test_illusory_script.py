from __future__ import annotations

import json
import unittest

from shared_types.encounter_events import (
    StoryModeSpellcastDeclaredEvent,
    StoryModeSpellcastIgnoredEvent,
    StoryModeSpellcastResolvedEvent,
    StoryModeSpellcastValidatedEvent,
    SpellcastingWitnessPacketCreatedEvent,
)
from shared_types.storytelling import (
    SpellcastingReactionCategory,
    SpellcastingSocialReactionPlan,
    SpellcastingWitnessReaction,
    StoryModeCastEscalationDecision,
)
from tests.xphb_level1_spells.story_support import StoryLevel1SpellTestCase, adjudication_success_payload


def _reaction_payload(*, witness_id: str, reaction_category: str, public_narration: str, summary: str, public_text: str, private_note: str = '') -> dict:
    payload = {
        'public_narration': public_narration,
        'witness_reactions': [
            {
                'witness_id': witness_id,
                'reaction_category': reaction_category,
                'summary': summary,
                'public_text': public_text,
                'private_note': private_note,
            }
        ],
        'scene_note': 'Story-mode illusory script adjudicated in the local XPHB flow.',
        'dm_note': 'Local-XPHB illusory script result.',
        'escalation': {
            'recommended': False,
            'reason': 'Illusory Script is a quiet written effect in this slice.',
            'mode_switch_decision': None,
        },
    }
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


def _dual_view_payload() -> dict:
    payload = {
        'public_narration': 'The encoded page presents one meaning to the chosen reader and nonsense to everyone else.',
        'witness_reactions': [
            {
                'witness_id': 'gundren-rockseeker',
                'reaction_category': 'curious',
                'summary': 'The chosen reader understands the hidden meaning.',
                'public_text': 'The letter says the caravan should wait by the west gate.',
                'private_note': 'Chosen reader receives the normal meaning.',
            },
            {
                'witness_id': 'player-2',
                'reaction_category': 'notices_but_ignores',
                'summary': 'The outsider cannot read the hidden meaning.',
                'public_text': 'That page is full of gibberish.',
                'private_note': 'Only the intended reader sees the real text.',
            },
        ],
        'scene_note': 'Story-mode illusory script with observer-relative text.',
        'dm_note': 'Local-XPHB illusory script chosen-reader split view.',
        'escalation': {
            'recommended': False,
            'reason': 'Illusory Script is a quiet written effect in this slice.',
            'mode_switch_decision': None,
        },
    }
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


class IllusoryScriptTests(StoryLevel1SpellTestCase):
    SPELL_NAME = 'Illusory Script'
    SPELL_SLUG = 'illusory-script'

    def _setup_session(self, payloads: list[dict]):
        session, transport = self.build_story_session(payloads)
        self.grant_spell(session, self.SPELL_NAME)
        return session, transport

    def _resolved_event(self, session):
        return next(event for event in session.state.event_log if isinstance(event, StoryModeSpellcastResolvedEvent))

    def test_declaration_uses_the_story_cast_syntax(self) -> None:
        session, _ = self.build_story_session([])
        self.grant_spell(session, self.SPELL_NAME)
        intent = session._story_mode_cast_intent("/cast player-1 illusory-script --readers gundren-rockseeker,player-2 --description Encrypt Gundren's ledger page.")
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells[self.SPELL_SLUG], intent)
        self.assertEqual(declaration, 'Cast the spell Illusory Script.')
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {
            'readers': 'gundren-rockseeker,player-2',
            'description': "Encrypt Gundren's ledger page.",
        })

    def test_story_cast_records_declared_validated_and_resolved_events(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Illusory Script to hide the letter.', public_text='The script looks like ordinary market notes to the chosen readers.'),
            _reaction_payload(
                witness_id='gundren-rockseeker',
                reaction_category='curious',
                public_narration='The chosen reader studies the encoded writing.',
                summary='The reader can understand the hidden meaning.',
                public_text='The note says the meeting is at midnight.',
                private_note='The hidden message is readable to the chosen reader.',
            ),
        ])
        session.execute_for_controller('player-1-controller', "/cast player-1 illusory-script --readers gundren-rockseeker,player-2 --description Encrypt Gundren's ledger page.")
        declared = [event for event in session.state.event_log if isinstance(event, StoryModeSpellcastDeclaredEvent)]
        validated = [event for event in session.state.event_log if isinstance(event, StoryModeSpellcastValidatedEvent)]
        resolved = [event for event in session.state.event_log if isinstance(event, StoryModeSpellcastResolvedEvent)]
        packets = [event for event in session.state.event_log if isinstance(event, SpellcastingWitnessPacketCreatedEvent)]
        self.assertEqual(len(declared), 1)
        self.assertEqual(len(validated), 1)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(len(packets), 1)
        self.assertEqual(declared[0].spell_id, self.SPELL_SLUG)
        self.assertEqual(resolved[0].resolution.attempt.spell_id, self.SPELL_SLUG)
        self.assertIsNotNone(resolved[0].resolution.social_reaction_plan)

    def test_story_cast_can_show_the_chosen_reader_and_outsider_views(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Illusory Script to hide the letter.', public_text='The chosen reader sees the intended letter while everyone else sees nonsense script.'),
        ])
        original_plan = session.dm_runtime.plan_spellcasting_reaction

        def _plan_spellcasting_reaction(context, documents, *, witness_packet, stream_handler=None, retry_handler=None):
            plan = SpellcastingSocialReactionPlan(
                public_narration='The encoded page presents one meaning to the chosen reader and nonsense to everyone else.',
                witness_reactions=(
                    SpellcastingWitnessReaction(
                        witness_id='gundren-rockseeker',
                        reaction_category=SpellcastingReactionCategory.CURIOUS,
                        summary='The chosen reader understands the hidden meaning.',
                        public_text='The letter says the caravan should wait by the west gate.',
                        private_note='Chosen reader receives the normal meaning.',
                    ),
                    SpellcastingWitnessReaction(
                        witness_id='player-2',
                        reaction_category=SpellcastingReactionCategory.NOTICES_BUT_IGNORES,
                        summary='The outsider cannot read the hidden meaning.',
                        public_text='That page is full of gibberish.',
                        private_note='Only the intended reader sees the real text.',
                    ),
                ),
                scene_note='Story-mode illusory script with observer-relative text.',
                dm_note='Local-XPHB illusory script chosen-reader split view.',
                escalation=StoryModeCastEscalationDecision(recommended=False, reason='Illusory Script is a quiet written effect in this slice.', mode_switch_decision=None),
            )
            return plan, ()

        session.dm_runtime.plan_spellcasting_reaction = _plan_spellcasting_reaction
        try:
            session.execute_for_controller('player-1-controller', "/cast player-1 illusory-script --readers gundren-rockseeker,player-2 --description Encrypt Gundren's ledger page.")
        finally:
            session.dm_runtime.plan_spellcasting_reaction = original_plan
        resolved = self._resolved_event(session)
        self.assertIsNotNone(resolved.resolution.social_reaction_plan)

    def test_story_cast_can_show_alternate_handwriting_or_language_in_the_resolution_plan(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Illusory Script to make the text look like another language.', public_text='The scroll now reads like a merchant contract.'),
            _reaction_payload(
                witness_id='gundren-rockseeker',
                reaction_category='curious',
                public_narration='The chosen reader sees the disguised language.',
                summary='The witness reads the hidden note without trouble.',
                public_text='The handwriting looks like a clerk from Neverwinter.',
                private_note='The letter appears in the chosen style.',
            ),
        ])
        session.execute_for_controller('player-1-controller', "/cast player-1 illusory-script --readers gundren-rockseeker,player-2 --description Encrypt Gundren's ledger page.")
        resolved = self._resolved_event(session)
        self.assertIsNotNone(resolved.resolution.social_reaction_plan)

    def test_story_cast_can_report_dispel_or_true_sight_revelation_text(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Illusory Script to hide the text until it is dispelled.', public_text='The illusion and the original text vanish together if the script is dispelled.'),
            _reaction_payload(
                witness_id='gundren-rockseeker',
                reaction_category='notices_but_ignores',
                public_narration='The witness accepts the magical writing as written.',
                summary='The witness does not escalate.',
                public_text='True sight would reveal the hidden line underneath.',
                private_note='The hidden message remains in place.',
            ),
        ])
        session.execute_for_controller('player-1-controller', "/cast player-1 illusory-script --readers gundren-rockseeker,player-2 --description Encrypt Gundren's ledger page.")
        resolved = self._resolved_event(session)
        self.assertIsNotNone(resolved.resolution.social_reaction_plan)
        self.assertEqual(session.story_state.runtime_mode.value, 'storytelling')


if __name__ == '__main__':
    unittest.main()
