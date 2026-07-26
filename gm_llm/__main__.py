"""`python -m gm_llm …` — the checkout's entry point.

The installed `gm-llm` console script runs the *installed* package, which never sees the
source tree's `dev/` and so never registers the `dev` and `bench` groups. Running the
module from a checkout picks up edits immediately with no install step, which is what
`python dev/cli.py` used to provide.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
