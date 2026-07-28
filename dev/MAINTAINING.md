# Maintaining gm-llm

Dev-side conventions — versioning, what an "update" actually delivers, and the
portability rules that keep Windows working. Not shipped; lives beside the dev CLI.

## Versioning

**The rule lives in `CLAUDE.md` § Versioning & releases** — single source of truth is
`__version__` in `gm_llm/__init__.py`, which `pyproject.toml` reads dynamically. Don't
restate it here; this section covers only the dev-side *cadence*.

**Bump the patch version on every push to main that changes shipped behavior** —
code fix, asset change, installer change. Main *is* the release channel: the Windows
installer clones main and users update by re-running it, so every push is effectively
a release. If the version doesn't move, `gm-llm --version` can't tell a fixed install
from a stale one — that ambiguity is exactly what made the cp1252 crash report hard
to triage (0.1.0 spanned both sides of the fix).

Scheme is `0.MINOR.PATCH`: patch for fixes and small tweaks, minor for feature-level
changes. Nothing promises stability yet; the number exists for triage, not contract.

## What an update actually delivers

Two halves update independently — keep straight which one a change lands in:

| You changed | Users get it by |
|---|---|
| Python code (`gm_llm/`, `orchestrator/`, `tui/`) | re-running the installer (or `git pull` + pip/pipx reinstall) |
| Framework assets (`gm_llm/assets/opencode/`) | the above, **then** `gm-llm update` in each project |

`gm-llm update` refreshes a project's `.opencode/` snapshot only — it never upgrades
the installed Python package. A code fix that a user "updated" for but still hits
usually means they ran `gm-llm update` without reinstalling the tool.

## Release checklist

1. Bump `__version__` in `gm_llm/__init__.py` (the only home — see above).
2. Update README.md if user-facing behavior or setup steps changed.
3. Run the gate — `CLAUDE.md` § How to run things.
4. Commit, push to main. That's the release.

## Text I/O hygiene (Windows)

Windows' locale default is cp1252, which can't represent `✓`, box-drawing, emoji, or
much of what a model emits — every implicit-encoding path is a latent
`UnicodeEncodeError`/`UnicodeDecodeError`. The rules:

- Every `open()` / `read_text()` / `write_text()` passes `encoding="utf-8"`.
  Best-effort writers catch `(OSError, ValueError)` — `ValueError` covers codec errors.
- Every `subprocess.run(..., text=True)` passes `encoding="utf-8", errors="replace"`
  (git/npm output is utf-8 regardless of the locale code page).
- `cli.main()` reconfigures `sys.stdout`/`sys.stderr` to utf-8 (`errors="replace"`)
  on Windows before anything prints — redirected/piped stdio otherwise defaults to
  cp1252 even when the console itself is fine. Don't print from import time or from
  entry points that bypass `main()`.

Audit for regressions before a release touching I/O:

```
grep -rnE 'read_text\(|write_text\(|open\(|text=True' gm_llm | grep -vE 'encoding=|urlopen|_open\('
```

Expected survivors: the `Popen` serve-log redirect in `backend.py` (the fd goes
straight to the subprocess; Python never encodes through it) and non-I/O name matches.
