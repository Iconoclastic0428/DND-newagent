from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class WebFrontendChatStateTests(unittest.TestCase):
    def _run_node_module_test(self, source: str) -> None:
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is required for frontend module tests')
        result = subprocess.run(
            [node, '--input-type=module'],
            input=source,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if result.returncode != 0:
            self.fail(f'node frontend test failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}')

    def test_thinking_entries_expire_when_authoritative_chat_advances(self) -> None:
        module_url = (REPO_ROOT / 'web_frontend' / 'chat_state.js').as_uri()
        source = f"""
            import assert from 'node:assert/strict';

            const {{
              appendLocalChatEntry,
              buildChatRenderEntries,
              createChatFeedState,
              noteAuthoritativeChat,
            }} = await import({json.dumps(module_url)});

            const firstView = [
              {{ entry_id: 'story-1', speaker: 'DM', text: 'Gundren waits by the table.', category: 'story' }},
            ];
            const finalView = [
              ...firstView,
              {{ entry_id: 'story-2', speaker: 'DM', text: 'The latest narration lands here.', category: 'story' }},
            ];

            const feed = createChatFeedState();
            noteAuthoritativeChat(feed, firstView);
            appendLocalChatEntry(feed, {{ speaker: 'DM', text: 'DM is thinking...', category: 'thinking' }}, 1000);

            let rendered = buildChatRenderEntries(feed, firstView);
            assert.equal(rendered[rendered.length - 1].category, 'thinking');

            noteAuthoritativeChat(feed, finalView);
            rendered = buildChatRenderEntries(feed, finalView);

            assert.equal(rendered.some(entry => entry.category === 'thinking'), false);
            assert.equal(rendered[rendered.length - 1].text, 'The latest narration lands here.');
        """
        self._run_node_module_test(textwrap.dedent(source))

    def test_thinking_entries_remain_while_authoritative_chat_is_unchanged(self) -> None:
        module_url = (REPO_ROOT / 'web_frontend' / 'chat_state.js').as_uri()
        source = f"""
            import assert from 'node:assert/strict';

            const {{
              appendLocalChatEntry,
              buildChatRenderEntries,
              createChatFeedState,
              noteAuthoritativeChat,
            }} = await import({json.dumps(module_url)});

            const viewEntries = [
              {{ entry_id: 'story-1', speaker: 'DM', text: 'Gundren waits by the table.', category: 'story' }},
            ];

            const feed = createChatFeedState();
            noteAuthoritativeChat(feed, viewEntries);
            appendLocalChatEntry(feed, {{ speaker: 'DM', text: 'DM is thinking...', category: 'thinking' }}, 1000);
            noteAuthoritativeChat(feed, viewEntries);

            const rendered = buildChatRenderEntries(feed, viewEntries);
            assert.equal(rendered[rendered.length - 1].category, 'thinking');
        """
        self._run_node_module_test(textwrap.dedent(source))


if __name__ == '__main__':
    unittest.main()
