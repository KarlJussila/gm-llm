# Maintaining gm-llm

Dev-side conventions — what an "update" actually delivers, and the portability rules
that keep Windows working. Not shipped; lives beside the dev CLI.

**Versioning and releases are `CLAUDE.md` § Versioning & releases** — the single source
of truth is `__version__` in `gm_llm/__init__.py`, bumped when a feature set lands, and
the release *is* the annotated bump commit. Don't restate any of it here; a second copy
of that rule is what rotted this file once already (`design/findings.md` Part 1).

One dev-side consequence worth stating where the installer lives: **the version is the
only triage handle a user gives you.** The Windows installer clones main and users
update by re-running it, so if the number hasn't moved, `gm-llm --version` can't
distinguish a fixed install from a stale one — the ambiguity that made the cp1252 crash
report hard to triage, where 0.1.0 spanned both sides of the fix. If a shipped-behavior
change is worth a `CHANGELOG.md` line, it is heading for a bump.

## What an update actually delivers

Two halves update independently — keep straight which one a change lands in:

| You changed | Users get it by |
|---|---|
| Python code (`gm_llm/`, incl. `gm_llm/orchestrator/`, `gm_llm/tui/`) | re-running the installer (or `git pull` + pip/pipx reinstall) |
| Framework assets (`gm_llm/assets/opencode/`) | the above, **then** `gm-llm update` in each project |

`gm-llm update` refreshes a project's `.opencode/` snapshot only — it never upgrades
the installed Python package. A code fix that a user "updated" for but still hits
usually means they ran `gm-llm update` without reinstalling the tool.

## Release checklist

1. Bump `__version__` in `gm_llm/__init__.py` (the only home — see above).
2. Fold `CHANGELOG.md`'s `[Unreleased]` into the new version and open a fresh one.
3. Update README.md if user-facing behavior or setup steps changed.
4. Run the gate — `CLAUDE.md` § How to run things.
5. Commit the bump on its own and tag it — `CLAUDE.md` § Versioning & releases has the
   exact form.

## Portability (Windows)

Two independent hazards: **process lifecycle** (below) and **text encoding** (next
section). Both are dev-side rules, not user-facing behavior, and both were written after
a real break.

### Process and path rules

- **No hardcoded `/tmp`.** Logs default to `tempfile.gettempdir()/gm-llm`.
- **Resolve `opencode` through `shutil.which()`** (`backend.py`) — native Windows may
  expose it as a `.cmd`/`.exe` shim rather than an executable on the path proper — and
  launch it in a new process group so it can be signalled.
- **Server shutdown is per-platform.** `signal.SIGINT` isn't portable, so Windows uses
  `taskkill /F /T` to reap the shim's whole process tree, with `SIGINT` elsewhere and a
  `kill()` fallback. A *graceful* CTRL_BREAK was tried and rejected: it risks `cmd`'s
  "Terminate batch job?" prompt hanging shutdown forever.
- **Terminal support is documented, not coded.** Windows Terminal / PowerShell only —
  Textual and rich auto-enable VT there, and legacy `cmd.exe` renders poorly.

### Text I/O hygiene

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
