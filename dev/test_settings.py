#!/usr/bin/env python3
"""Settings survive asset updates; campaigns share feedback and benchmarks own a copy."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.bench.runner import assemble_run
from gm_llm.orchestrator.canon import CanonPreloader
from gm_llm.project import init_project
from gm_llm.settings import load_settings


def test_player_feedback(root):
    first, second = root / 'first', root / 'second'
    init_project(first)
    init_project(second)
    shared = load_settings(first).feedback_dir
    assert shared == load_settings(second).feedback_dir
    shared.mkdir(parents=True)
    (shared / 'dm-runner.md').write_text('Ask for more rolls.\n', encoding='utf-8')
    for campaign in (first, second):
        prepared = CanonPreloader(str(campaign)).runner_preload()
        assert 'Ask for more rolls.' in prepared
        assert not (campaign / 'campaign/feedback').exists()

    config = first / 'gm-llm.yaml'
    config.write_text('feedback-dir: custom-feedback\nsubagents: parallel\n', encoding='utf-8')
    before = config.read_text(encoding='utf-8')
    init_project(first, force=True)
    assert config.read_text(encoding='utf-8') == before
    assert load_settings(first).feedback_dir == first / 'custom-feedback'
    assert load_settings(first).subagents == 'parallel'
    assert load_settings(second).subagents == 'sequential'


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
    assert private == run / 'feedback'
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
    print('OK — shared feedback, preserved settings, and private benchmark feedback.')
