"""Entry point: `python -m gm_llm.tui` (from a checkout: the repo venv).

Defaults to the mock backend so you can prototype the UI with no opencode and no
rate limit. `--live` boots a real opencode backend against `--dir` (default: the
current directory, a `gm-llm init`-ed project) and plays for real.
"""

import argparse
from pathlib import Path

from gm_llm.tui.app import PlayApp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use a real opencode backend (default: mock)")
    ap.add_argument("--setup", action="store_true",
                    help="mock only: start in the new-campaign setup phase (live detects this from disk)")
    ap.add_argument("--dir", default=".", help="project directory (default: cwd)")
    ap.add_argument("--port", type=int, default=4181)
    ap.add_argument("--theme", default="dracula",
                    help="Textual theme (e.g. dracula, tokyo-night, gruvbox, catppuccin-mocha, nord)")
    args = ap.parse_args()

    cleanup = None
    if args.live:
        from gm_llm.orchestrator import Backend, CanonPreloader, Gate, Lifecycle, Logs
        from gm_llm.orchestrator.logs import debug_enabled
        directory = str(Path(args.dir).resolve())
        # One object owns every log path (serve/raw/checks/detail); GM_LLM_DEBUG=1
        # turns on the raw per-reply dump. See gm_llm/orchestrator/logs.py.
        logs = Logs.under(project=directory, debug=debug_enabled())
        backend = Backend(directory, port=args.port, logs=logs).start()
        gate = Gate(backend, CanonPreloader(directory), logs=logs)
        lifecycle = Lifecycle(backend, gate, directory, logs=logs)
        cleanup = backend.stop
        title = "gm-llm (live)"
    else:
        from gm_llm.orchestrator.mock import MockLifecycle
        lifecycle = MockLifecycle(start_in_setup=args.setup)
        title = "gm-llm (MOCK)"

    app = PlayApp(lifecycle, cleanup=cleanup, theme=args.theme)
    app.title = title
    app.run()


if __name__ == "__main__":
    main()
