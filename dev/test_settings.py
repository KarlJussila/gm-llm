#!/usr/bin/env python3
"""Settings survive asset updates; campaigns share feedback through a project copy the agents
can reach, and benchmarks own a private one."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.bench.runner import assemble_run
from gm_llm.orchestrator.canon import CanonPreloader
from gm_llm.project import init_project
from gm_llm.settings import (feedback_snapshot, load_settings, project_feedback, pull_feedback,
                             push_feedback)


def test_player_feedback(root):
    first, second = root / 'first', root / 'second'
    init_project(first)
    init_project(second)
    shared = load_settings(first).feedback_dir
    assert shared == load_settings(second).feedback_dir
    assert root / 'home' in shared.parents, 'the default store is outside every project'
    shared.mkdir(parents=True)
    (shared / 'dm-runner.md').write_text('Ask for more rolls.\n', encoding='utf-8')
    (shared / 'dm.md').write_text('Keep reports short.\n', encoding='utf-8')
    for campaign in (first, second):
        pull_feedback(campaign)
        assert (project_feedback(campaign) / 'dm.md').is_file(), 'the agents read the project copy'
        prepared = CanonPreloader(str(campaign)).runner_preload()
        assert 'Ask for more rolls.' in prepared
        assert not (campaign / 'campaign/feedback').exists()

    # Curation in the first campaign goes back to the store; only what it changed, so the
    # second campaign's curation since the pull survives.
    before = feedback_snapshot(first)
    (shared / 'dm.md').write_text('Reports: one paragraph.\n', encoding='utf-8')
    (project_feedback(first) / 'dm-runner.md').write_text('Ask for rolls on uncertainty.\n',
                                                          encoding='utf-8')
    (project_feedback(first) / 'session-plan.md').write_text('Fewer beats.\n', encoding='utf-8')
    push_feedback(first, before)
    assert (shared / 'dm-runner.md').read_text(encoding='utf-8') == 'Ask for rolls on uncertainty.\n'
    assert (shared / 'session-plan.md').read_text(encoding='utf-8') == 'Fewer beats.\n'
    assert (shared / 'dm.md').read_text(encoding='utf-8') == 'Reports: one paragraph.\n'
    pull_feedback(second)
    assert 'uncertainty' in (project_feedback(second) / 'dm-runner.md').read_text(encoding='utf-8')

    config = first / 'gm-llm.yaml'
    config.write_text('feedback-dir: custom-feedback\n', encoding='utf-8')
    before = config.read_text(encoding='utf-8')
    init_project(first, force=True)
    assert config.read_text(encoding='utf-8') == before
    assert load_settings(first).feedback_dir == first / 'custom-feedback'


def test_benchmark_copy(root):
    template = root / 'template'
    init_project(template)
    personal = load_settings(template).feedback_dir
    (personal / 'dm-runner.md').write_text('Personal guidance.\n', encoding='utf-8')
    fixture = root / 'fixture'
    (fixture / 'campaign').mkdir(parents=True)
    (fixture / 'feedback').mkdir()
    (fixture / 'feedback/dm-runner.md').write_text('Fixture guidance.\n', encoding='utf-8')
    run = root / 'run'
    assemble_run(template, fixture / 'campaign', run, 'test')
    private = load_settings(run).feedback_dir
    assert private == run / 'feedback' == project_feedback(run)
    pull_feedback(run)
    push_feedback(run, {})
    prepared = CanonPreloader(str(run)).runner_preload()
    assert 'Fixture guidance.' in prepared and 'Personal guidance.' not in prepared
    (private / 'dm-runner.md').write_text('Run-only guidance.\n', encoding='utf-8')
    assert (personal / 'dm-runner.md').read_text(encoding='utf-8') == 'Personal guidance.\n'
    assert (fixture / 'feedback/dm-runner.md').read_text(encoding='utf-8') == 'Fixture guidance.\n'


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='gm-settings-') as temp:
        root = Path(temp)
        # `~` in the default feedback-dir expands from the environment, so sandbox it.
        os.environ['HOME'] = os.environ['USERPROFILE'] = str(root / 'home')
        test_player_feedback(root)
        test_benchmark_copy(root)
    print('OK — shared feedback via the project copy, preserved settings, private benchmark feedback.')
