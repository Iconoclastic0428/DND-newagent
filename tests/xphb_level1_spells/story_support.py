from __future__ import annotations

import json
from pathlib import Path

from tests.xphb_cantrips.support import (
    StoryCantripTestCase,
    adjudication_success_payload,
    spell_reaction_ignore_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = REPO_ROOT / 'content' / 'xphb' / 'spells' / 'level-1'


def spell_folder(slug: str) -> Path:
    return CONTENT_ROOT / slug


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding='utf-8'))


def suspicion_payload(*, witness_id: str = 'gundren-rockseeker', public_narration: str = 'The witnesses notice the spellcasting and grow uneasy.') -> dict:
    payload = {
        'public_narration': public_narration,
        'witness_reactions': [
            {
                'witness_id': witness_id,
                'reaction_category': 'suspicious',
                'summary': 'The witness notices the magic and starts watching for trouble.',
                'public_text': 'The room quiets as the spell draws suspicion.',
                'private_note': 'The scene is now tense.',
            }
        ],
        'scene_note': 'The witnesses are no longer fully relaxed.',
        'dm_note': 'Suspicion rises after the spell is witnessed.',
        'escalation': {'recommended': False, 'reason': '', 'mode_switch_decision': None},
    }
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


class StoryLevel1SpellTestCase(StoryCantripTestCase):
    def spell_metadata(self, slug: str) -> dict[str, object]:
        return load_json(spell_folder(slug) / 'metadata.json')

    def spell_implementation(self, slug: str) -> dict[str, object]:
        return load_json(spell_folder(slug) / 'implementation.json')

    def spell_folder(self, slug: str) -> Path:
        return spell_folder(slug)

    def spell_declaration(self, session, spell_name: str, command: str) -> str:
        self.grant_spell(session, spell_name)
        intent = session._story_mode_cast_intent(command)
        spell = session.encounter_session.state.actors['player-1'].spells[intent.spell_id]
        return session._story_spell_adjudication_declaration(spell, intent)

    def spell_intent(self, session, command: str):
        return session._story_mode_cast_intent(command)
