#!/usr/bin/env python3
"""Exercise setup's disk checks and resume after interrupted authoring, without a model."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.orchestrator.backend import BackendError
from gm_llm.orchestrator.gate import StageGateResult, Verdict
from gm_llm.orchestrator.lint import setup_missing
from gm_llm.orchestrator.scaffold import scaffold_campaign
from gm_llm.orchestrator.setup import Setup


def arc(root, slug, tier, hook=""):
    path = root / 'campaign' / 'arcs' / f'{slug}.md'
    path.write_text(f'---\nslug: {slug}\nname: {slug}\ntype: arc\nstatus: dormant\n'
                    f'summary: a conflict\ntier: {tier}\n' +
                    (f'hooks-into: {hook}\n' if hook else '') + '---\n', encoding='utf-8')
    path.with_suffix('.state.md').write_text('---\nas-of: S0\n---\n', encoding='utf-8')


class Backend:
    def __init__(self, root, author):
        self.directory = str(root)
        self.author = author
        self.prompts = []

    def create_session(self, title):
        return title

    def preface(self, sid, text):
        pass

    def prompt(self, sid, agent, message, **kwargs):
        self.prompts.append(message)
        self.author(message)
        return 'done'


class Gate:
    def check_init(self):
        return StageGateResult(Verdict('check-init', True, ''), prompt='init', label='Init')


def root_at(path):
    path.mkdir()
    scaffold_campaign(path)
    markers = path / '.opencode' / '.orchestrator'
    markers.mkdir(parents=True)
    for stage in ('INTAKE', 'WORLD', 'CHAR'):
        (markers / f'setup-{stage}.done').touch()
    return path


def test_resume(root):
    def interrupt(message):
        arc(root, 'crown', 'major')
        raise BackendError('connection lost after writing the major arc')

    try:
        Setup(Backend(root, interrupt), Gate(), str(root)).start()
    except BackendError:
        pass
    else:
        raise AssertionError('expected an interrupted authoring call')
    major = (root / 'campaign/arcs/crown.md').read_text(encoding='utf-8')

    def complete(message):
        arc(root, 'rivals', 'minor', 'crown')

    backend = Backend(root, complete)
    assert Setup(backend, Gate(), str(root)).start().done
    assert len(backend.prompts) == 1, 'resume should dispatch once and skip completed stages'
    assert 'Exactly one major arc' not in backend.prompts[0], 'resume lists only unfinished work'
    assert (root / 'campaign/arcs/crown.md').read_text(encoding='utf-8') == major
    assert setup_missing(root) == []
    # After all deliverables exist, a resume runs no more authoring.
    backend = Backend(root, lambda message: None)
    assert Setup(backend, Gate(), str(root)).start().done
    assert not backend.prompts


def test_one_correction(root):
    def partial(message):
        if not (root / 'campaign/arcs/crown.md').exists():
            arc(root, 'crown', 'major')

    backend = Backend(root, partial)
    assert Setup(backend, Gate(), str(root)).start().done, 'setup moves on after one correction'
    assert len(backend.prompts) == 2, 'one authoring dispatch and one correction'
    assert 'minor arc' in backend.prompts[1]


def test_coverage(root):
    arc(root, 'crown', 'major')
    arc(root, 'rivals', 'minor', 'crown')
    assert not setup_missing(root)
    arc(root, 'rivals', 'minor', 'elsewhere')
    assert len(setup_missing(root)) == 1
    arc(root, 'rivals', 'minor', 'crown')
    state = root / 'campaign/arcs/rivals.state.md'
    state.write_text('---\nas-of: S1\n---\n', encoding='utf-8')
    assert len(setup_missing(root)) == 1, 'setup requires S0, before play'
    state.unlink()
    assert len(setup_missing(root)) == 1, 'a missing state file is unfinished work'


if __name__ == '__main__':
    for key, value in {'GIT_AUTHOR_NAME': 'test', 'GIT_COMMITTER_NAME': 'test',
                       'GIT_AUTHOR_EMAIL': 'test@example.invalid',
                       'GIT_COMMITTER_EMAIL': 'test@example.invalid'}.items():
        os.environ.setdefault(key, value)
    with tempfile.TemporaryDirectory(prefix='gm-setup-') as temp:
        for test in (test_resume, test_one_correction, test_coverage):
            test(root_at(Path(temp) / test.__name__))
            print(f'  ✓ {test.__name__}')
    print('OK — setup coverage, one correction, and resume of unfinished work.')
