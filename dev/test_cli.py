#!/usr/bin/env python3
"""Standalone checks for the unified CLI surface — no pytest; run me directly.

Parses argv and inspects the resulting namespace; nothing here boots a backend, launches
Textual, or calls a model. The point is the *shape* of the surface: which commands exist
in an installed copy vs a checkout, that the three play axes survive parsing, and that
unsupported axis combinations refuse by name instead of silently running something else.
"""

import argparse
import io
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from gm_llm import cli  # noqa: E402


def _commands(parser):
    return set(parser._subparsers._group_actions[0].choices)


def _parse(*argv):
    return cli._build_parser().parse_args(list(argv))


def test_checkout_gates_the_workshop_groups(tmp):
    """`bench` needs dev/fixtures, which isn't packaged — so an installed copy must not
    advertise it, and a checkout must."""
    assert cli._is_checkout(), "these tests run from the checkout"
    assert {"dev", "bench"} <= _commands(cli._build_parser())

    real = cli._is_checkout
    cli._is_checkout = lambda: False
    try:
        installed = _commands(cli._build_parser())
    finally:
        cli._is_checkout = real
    assert installed == {"play", "serve", "status", "tokens", "init", "update", "doctor"}, \
        installed


def test_play_axes_parse_independently(tmp):
    a = _parse("play")
    assert (a.player, a.ui, a.mock, a.dir) == ("human", "tui", False, "."), vars(a)

    a = _parse("play", "/tmp/camp", "--player", "auto", "--ui", "console", "--turn-cap", "7")
    assert (a.player, a.ui, a.dir, a.turn_cap) == ("auto", "console", "/tmp/camp", 7)

    a = _parse("play", "--player", "auto", "--sessions", "3")
    assert (a.sessions, a.turn_cap) == (3, None), "autonomous play has no turn cap by default"
    assert cli._serve_args(a)[-2:] == ["--sessions", "3"], cli._serve_args(a)
    assert "--turn-cap" not in cli._serve_args(a)
    assert cli.run_play(_parse("play", "--sessions", "3")) == 2, "--sessions needs --player auto"

    a = _parse("play", "--mock", "--setup")
    assert a.mock and a.setup

    # the campaign is positional on top-level commands and a flag on workshop ones
    assert _parse("status", "/tmp/camp").dir == "/tmp/camp"
    assert _parse("tokens", "/tmp/camp").dir == "/tmp/camp"
    assert _parse("dev", "lint", "--dir", "/tmp/camp").dir == "/tmp/camp"


def test_bare_invocation_plays_here(tmp):
    assert cli._build_parser().parse_args([]).__dict__.get("cmd") is None, \
        "a bare invocation has no cmd; main() rewrites it to `play`"
    a = _parse("play")
    assert a.func is cli.run_play and a.dir == "."


def test_dev_autoplay_and_play_auto_are_one_driver(tmp):
    """Two front doors, one implementation — so they can't drift."""
    from gm_llm import devcmds
    auto = _parse("dev", "autoplay", "--turn-cap", "5")
    assert auto.func.__name__ == "<lambda>" or auto.func is not None
    ns = argparse.Namespace(**vars(auto))
    calls = []
    real = cli.run_play
    cli.run_play = lambda a: calls.append((a.player, a.mock, a.ui))
    try:
        devcmds._autoplay(ns)
    finally:
        cli.run_play = real
    assert calls == [("auto", False, "console")], calls


def test_player_axis_selects_a_source_not_a_command(tmp):
    """Both TUI cells are the same app over one session loop — `--player` picks the
    `PlayerSource` the lifecycle hands it. The console frontend is a separate entry point:
    the same client whoever plays."""
    routed = []
    real_tui, real_autoplay = cli._launch_tui, None
    cli._launch_tui = lambda args, *, mock, player="human": routed.append(("tui", player, mock))
    try:
        cli.run_play(_parse("play"))
        cli.run_play(_parse("play", "--player", "auto", "--ui", "tui"))
        cli.run_play(_parse("play", "--mock"))
    finally:
        cli._launch_tui = real_tui
    assert routed == [("tui", "human", False), ("tui", "auto", False), ("tui", "human", True)], routed

    real_console = cli._run_console
    cli._run_console = lambda args: routed.append(("console", args.player, args.mock))
    try:
        cli.run_play(_parse("play", "--player", "auto", "--ui", "console"))
        cli.run_play(_parse("play", "--ui", "console", "--mock"))
    finally:
        cli._run_console = real_console
    assert routed[-2:] == [("console", "auto", False), ("console", "human", True)], routed


def test_unsupported_axis_combinations_refuse_by_name(tmp):
    """A harness that quietly ran a different mode than asked for would be worse than an
    error, so each missing cell names itself and exits non-zero."""
    cases = [
        (("play", "--player", "auto", "--mock"), "needs a real backend"),
    ]
    for argv, expect in cases:
        out = io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(out):
                cli.run_play(_parse(*argv))
        except SystemExit as e:
            assert e.code == 2, f"{argv}: exit {e.code}"
        else:
            raise AssertionError(f"{argv}: should have exited")
        assert expect in out.getvalue(), f"{argv}: {out.getvalue()!r}"


def test_backend_flags_are_declared_once(tmp):
    """Four hardcoded 4181s across three CLIs is what this refactor removed."""
    for argv in (("play",), ("dev", "autoplay"), ("dev", "prep"), ("bench", "run")):
        a = _parse(*argv)
        assert a.port == 4181 and a.min_gap == 1.0 and a.turn_timeout == 0, f"{argv}: {vars(a)}"


def main():
    tests = (test_checkout_gates_the_workshop_groups, test_play_axes_parse_independently,
             test_bare_invocation_plays_here, test_dev_autoplay_and_play_auto_are_one_driver,
             test_player_axis_selects_a_source_not_a_command,
             test_unsupported_axis_combinations_refuse_by_name,
             test_backend_flags_are_declared_once)
    failures = 0
    for test in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                test(Path(td))
                print(f"  ✓ {test.__name__}")
            except AssertionError as e:
                failures += 1
                print(f"  ✗ {test.__name__}: {e}")
    print(f"\n{'FAIL' if failures else 'OK'} — {len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
