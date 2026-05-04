from __future__ import annotations

import json
import unittest

from shared_types.encounter_events import (
    StoryModeSpellcastDeclaredEvent,
    StoryModeSpellcastEscalationRecommendedEvent,
    StoryModeSpellcastResolvedEvent,
    StoryModeSpellcastValidatedEvent,
    SpellcastingWitnessPacketCreatedEvent,
)
from tests.xphb_level1_spells.story_support import StoryLevel1SpellTestCase, adjudication_success_payload


def _reaction_payload(*, reaction_category: str, public_narration: str, summary: str, public_text: str, private_note: str = '', escalation_recommended: bool = False, witness_id: str = 'gundren-rockseeker') -> dict:
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
        'scene_note': 'Story-mode disguise adjudicated in the local XPHB flow.',
        'dm_note': 'Local-XPHB disguise self result.',
        'escalation': {
            'recommended': escalation_recommended,
            'reason': 'The witness reaction to the disguise attempt is strong enough to matter.',
            'mode_switch_decision': None,
        },
    }
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


class DisguiseSelfTests(StoryLevel1SpellTestCase):
    SPELL_NAME = 'Disguise Self'
    SPELL_SLUG = 'disguise-self'

    def _setup_session(self, payloads: list[dict]):
        session, transport = self.build_story_session(payloads)
        self.grant_spell(session, self.SPELL_NAME)
        return session, transport

    def _resolved_event(self, session):
        return next(event for event in session.state.event_log if isinstance(event, StoryModeSpellcastResolvedEvent))

    def test_declaration_uses_the_self_story_cast_syntax(self) -> None:
        session, _ = self.build_story_session([])
        self.grant_spell(session, self.SPELL_NAME)
        intent = session._story_mode_cast_intent('/cast player-1 disguise-self --form road-worn guard --description Blend into the caravan guard line.')
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells[self.SPELL_SLUG], intent)
        self.assertEqual(declaration, 'Cast the spell Disguise Self.')
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {
            'form': 'road-worn guard',
            'description': 'Blend into the caravan guard line.',
        })

    def test_story_cast_records_declared_validated_and_resolved_events(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Disguise Self to blend into the crowd.', public_text='The caster becomes a convincing dockworker.'),
            _reaction_payload(
                reaction_category='curious',
                public_narration='Gundren studies the change with interest.',
                summary='The witness is curious about the disguise magic.',
                public_text='That is a neat way to stay unseen.',
                private_note='Curious, not hostile.',
            ),
        ])
        session.execute_for_controller('player-1-controller', '/cast player-1 disguise-self --form road-worn guard --description Blend into the caravan guard line.')
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

    def test_story_cast_carries_the_chosen_form_metadata_into_the_intent(self) -> None:
        session, _ = self.build_story_session([])
        self.grant_spell(session, self.SPELL_NAME)
        intent = session._story_mode_cast_intent('/cast player-1 disguise-self --form road-worn guard --description Blend into the caravan guard line.')
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {
            'form': 'road-worn guard',
            'description': 'Blend into the caravan guard line.',
        })

    def test_story_cast_can_surface_a_suspicious_witness_reaction(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Disguise Self around suspicious witnesses.', public_text='The disguise takes hold.'),
            _reaction_payload(
                reaction_category='suspicious',
                public_narration='The witness does not trust the new face.',
                summary='The witness becomes suspicious but does not escalate.',
                public_text='I am watching that face carefully.',
                private_note='Suspicious, not hostile yet.',
            ),
        ])
        session.execute_for_controller('player-1-controller', '/cast player-1 disguise-self --form road-worn guard --description Blend into the caravan guard line.')
        resolved = self._resolved_event(session)
        self.assertIsNotNone(resolved.resolution.social_reaction_plan)

    def test_story_cast_can_recommend_escalation_without_forcing_combat(self) -> None:
        session, _ = self._setup_session([
            adjudication_success_payload(action_summary='Use Disguise Self in a tense scene.', public_text='The caster looks like a harmless traveler.'),
            _reaction_payload(
                reaction_category='escalates_to_mode_switch_candidate',
                public_narration='The witness thinks the disguise is an infiltration attempt.',
                summary='The witness is ready to call for backup.',
                public_text='Hold there until I know who you really are.',
                private_note='The disguise made the witness nervous.',
                escalation_recommended=True,
            ),
        ])
        session.execute_for_controller('player-1-controller', '/cast player-1 disguise-self --form road-worn guard --description Blend into the caravan guard line.')
        self.assertEqual(session.story_state.runtime_mode.value, 'storytelling')
        resolved = self._resolved_event(session)
        self.assertIsNotNone(resolved.resolution.social_reaction_plan)


if __name__ == '__main__':
    unittest.main()
