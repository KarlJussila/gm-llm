"""Entry point: `python -m tui` (run from the .opencode dir, in the venv).

Defaults to the mock backend so you can prototype the UI with no opencode and no
rate limit. `--live` boots a real opencode backend and plays for real.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # put .opencode on the path

from tui.app import PlayApp  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use a real opencode backend (default: mock)")
    ap.add_argument("--setup", action="store_true",
                    help="mock only: start in the new-campaign setup phase (live detects this from disk)")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--port", type=int, default=4181)
    ap.add_argument("--theme", default="dracula",
                    help="Textual theme (e.g. dracula, tokyo-night, gruvbox, catppuccin-mocha, nord)")
    args = ap.parse_args()

    cleanup = None
    if args.live:
        from orchestrator import Backend, CanonPreloader, Gate, Lifecycle, Logs
        # One object owns every log path (serve/raw/checks/detail); ORCH_DEBUG=1
        # turns on the raw per-reply dump. See orchestrator/logs.py.
        logs = Logs.under("/tmp", debug=bool(os.environ.get("ORCH_DEBUG")))
        backend = Backend(args.dir, port=args.port, logs=logs).start()
        gate = Gate(backend, CanonPreloader(args.dir), logs=logs)
        lifecycle = Lifecycle(backend, gate, args.dir, logs=logs)
        cleanup = backend.stop
        title = "Campaign — orchestrator (live)"
    else:
        from orchestrator.mock import MockLifecycle
        lifecycle = MockLifecycle(start_in_setup=args.setup)
        title = "Campaign — orchestrator (MOCK)"

    app = PlayApp(lifecycle, cleanup=cleanup, theme=args.theme)
    app.title = title
    app.run()


if __name__ == "__main__":
    main()
