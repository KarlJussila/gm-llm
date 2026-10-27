#!/usr/bin/env python3
"""The autonomous player over the Hollowfell fixture: its sheet is seeded once and then its own,
a cold start leads with its files and where the PC stands, and a warm thread carries on with
only a line saying a new session has begun."""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.orchestrator.autoplay import auto_player  # noqa: E402

CAMPAIGN = Path(__file__).resolve().parent / 'fixtures' / 'hollowfell' / 'campaign'


class FakeBackend:
    def __init__(self):
        self.live = set()
        self.sent = []
        self.made = 0

    def create_session(self, title=None):
        self.made += 1
        sid = f'sid-{self.made}'
        self.live.add(sid)
        return sid

    def session_valid(self, sid):
        return sid in self.live

    def prompt(self, sid, agent, message, whole=False):
        self.sent.append((sid, agent, message))
        return 'I look around.'


def first_message(backend, root, n, story=None):
    auto_player(backend, str(root), n, story=story).next_message('The inn is warm.')
    return backend.sent[-1]


def main():
    root = Path(tempfile.mkdtemp())
    shutil.copytree(CAMPAIGN, root / 'campaign')
    backend = FakeBackend()

    sid, agent, message = first_message(backend, root, 3)
    sheet = root / 'player' / 'sheet.md'
    assert agent == 'auto-player'
    assert sheet.read_text(encoding='utf-8').startswith('# You are Dallid'), 'the sheet is seeded'
    assert '<sheet>\n# You are Dallid' in message and '(none yet)' in message, message[:300]
    assert '## Where you stand' in message and '## Known capabilities' in message
    assert message.endswith('<dm>\nThe inn is warm.\n</dm>')

    sheet.write_text('# You are Dallid\n\n- level: 4\n', encoding='utf-8')
    (root / 'player' / 'notes.md').write_text('The miller lied.\n', encoding='utf-8')
    again, _, message = first_message(backend, root, 3)
    assert again == sid and message == '<dm>\nThe inn is warm.\n</dm>', \
        'the same session on a warm thread carries straight on'
    again, _, message = first_message(backend, root, 4)
    assert again == sid and message.startswith('Session 4 begins.'), message[:80]
    assert '<sheet>' not in message, 'a warm thread is not re-handed its files'

    backend.live.clear()  # the server lost the thread
    cold, _, message = first_message(backend, root, 4, story='I came to the inn.')
    assert cold != sid
    assert '- level: 4' in message and 'The miller lied.' in message, \
        "a cold start leads with the player's own files, not a fresh copy of the PC's sheet"
    assert 'I came to the inn.' in message, 'and the session so far'
    print('OK — autonomous player: seeded sheet, cold lead, warm thread across sessions.')


if __name__ == '__main__':
    main()
