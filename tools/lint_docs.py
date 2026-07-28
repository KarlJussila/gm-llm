#!/usr/bin/env python3
"""
Check the planning docs against the repo.

Every check here is traceable to a defect this repo actually had, or to one the
handoff-rounds method documents from the project it was derived from. Don't add
speculative checks — add them as you get burned.

    python3 tools/lint_docs.py        # 0 errors and 0 warnings, every round

Checks:
  1 routing      every doc in design/ is linked from design/README.md
  2 links        every relative markdown link in the planning docs resolves
  3 index        every Part in design/findings.md appears in its Contents table
  4 handoff      HANDOFF.md is within its line budget
  5 numbers      no counts typed into HANDOFF prose (they belong in the generated block)
  6 deferrals    open-questions items are parked on a track, not on a round
  7 version      no doc claims pyproject.toml carries a literal version
  8 gate         no doc tells a session to run the dev tests under bare pytest
  9 roadmap      no completion narratives left in the track tables
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESIGN = ROOT / "design"
HANDOFF = ROOT / "HANDOFF.md"
ROADMAP = ROOT / "ROADMAP.md"
FINDINGS = DESIGN / "findings.md"
QUESTIONS = DESIGN / "open-questions.md"

HANDOFF_MAX = 120

# The docs a round is expected to touch — the ones worth linting hard.
PLANNING = [HANDOFF, ROADMAP, ROOT / "CLAUDE.md", ROOT / "README.md",
            ROOT / "BENCHMARK.md", ROOT / "PLAN.md", ROOT / "COMBAT.md",
            ROOT / "SPEC.md"]

_errors: list[str] = []
_warnings: list[str] = []


def err(check: str, msg: str) -> None:
    _errors.append(f"[{check}] {msg}")


def warn(check: str, msg: str) -> None:
    _warnings.append(f"[{check}] {msg}")


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _docs() -> list[pathlib.Path]:
    return [p for p in PLANNING + sorted(DESIGN.glob("*.md")) if p.is_file()]


# ── 1. routing ───────────────────────────────────────────────────────────────
def check_routing() -> None:
    """A design doc nothing links to is a doc nobody reads. The reference project's
    README missed four whole packages before an audit caught it."""
    readme = DESIGN / "README.md"
    if not readme.is_file():
        err("routing", "design/README.md is missing — it is the routing table for design/")
        return
    text = _read(readme)
    for p in sorted(DESIGN.glob("*.md")):
        if p.name != "README.md" and p.name not in text:
            err("routing", f"design/{p.name} is not linked from design/README.md")


# ── 2. links ─────────────────────────────────────────────────────────────────
def check_links() -> None:
    """A dangling relative link means a doc moved and its referrers didn't."""
    pat = re.compile(r"\[[^\]]*\]\(([^)#][^)]*)\)")
    for doc in _docs():
        for target in pat.findall(_read(doc)):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (doc.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                err("links", f"{doc.relative_to(ROOT)} → {target} does not resolve")


# ── 3. findings index ────────────────────────────────────────────────────────
def check_findings_index() -> None:
    """An append-only archive is only useful if you can find the precedent in it.
    The reference project's index covered 19 of 115 Parts."""
    text = _read(FINDINGS)
    if not text:
        err("index", "design/findings.md is missing — it is the round archive")
        return
    parts = re.findall(r"^# Part (\d+) —", text, re.M)
    head = text.split("# Part 1", 1)[0]
    for n in parts:
        if not re.search(rf"\|\s*\[{n}\]\(", head):
            err("index", f"design/findings.md § Contents is missing Part {n}")
    if not parts:
        err("index", "design/findings.md has no Parts (expected at least Part 1)")


# ── 4. handoff size ──────────────────────────────────────────────────────────
def check_handoff_size() -> None:
    """HANDOFF grew 160 → 966 lines over 40 rounds in the reference project before
    being cut back. A budget that only warns is a suggestion."""
    n = len(_read(HANDOFF).splitlines())
    if n == 0:
        err("handoff", "HANDOFF.md is missing")
    elif n > HANDOFF_MAX:
        err("handoff", f"HANDOFF.md is {n} lines (budget {HANDOFF_MAX}) — it is "
                       f"accumulating history; move it to a findings Part")


# ── 5. transcribed numbers ───────────────────────────────────────────────────
def check_no_transcribed_numbers() -> None:
    """Every number a tool emitted was correct; every number typed into prose had
    drifted. Counts live in the generated block or nowhere."""
    text = _read(HANDOFF)
    if not text:
        return
    body = re.sub(r"<!-- status:begin.*?<!-- status:end -->", "", text, flags=re.S)
    # Only multi-digit figures are flagged. A bare single digit is nearly always a
    # cross-reference — "frontends 1", "step 4", "Part 1", "B3" — and flagging those
    # made the check unusable at setup; a drifting count ("2,677 lines", "47 errors")
    # is multi-digit in practice, and the generated block owns the small ones anyway.
    allowed = re.compile(
        r"(\d+\.\d+(\.\d+)?)"                       # versions / decimals
        r"|(\d{4}-\d{2}-\d{2})")                    # dates
    for i, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith(">"):
            continue
        stripped = allowed.sub("", line)
        for m in re.finditer(r"\b\d[\d,]*\d\b", stripped):
            warn("numbers", f"HANDOFF.md:{i} types a count ({m.group()!r}) into prose — "
                            f"put it in the generated block or delete it")


# ── 6. deferrals ─────────────────────────────────────────────────────────────
def check_deferrals() -> None:
    """A deferral parked on a round becomes a dangling pointer the moment that round
    closes. The reference project found 22 in that state. Park on a track."""
    text = _read(QUESTIONS)
    if not text:
        err("deferrals", "design/open-questions.md is missing — it is the live backlog")
        return
    roundish = re.compile(r"\b(during|when|at|after|before)\s+the\s+[^.,;]{0,40}\brounds?\b",
                          re.I)
    track = re.compile(r"\b(ROADMAP\s+track|track\s+[\w-]+)\b", re.I)
    for start, blockt in _bullet_blocks(QUESTIONS):
        if roundish.search(blockt) and not track.search(blockt):
            warn("deferrals", f"design/open-questions.md:{start} defers to a round without "
                              f"naming a ROADMAP track — a round closes, a track persists")


def _bullet_blocks(path: pathlib.Path) -> list[tuple[int, str]]:
    """A bullet plus its indented continuation lines. Anything flush-left ends it —
    otherwise one bullet swallows every paragraph after it."""
    blocks, cur, start = [], [], 0
    for i, line in enumerate(_read(path).splitlines(), 1):
        if re.match(r"^\s*[-*]\s", line):
            if cur:
                blocks.append((start, "\n".join(cur)))
            cur, start = [line], i
        elif cur and (line.startswith((" ", "\t")) or not line.strip()):
            cur.append(line)
        elif cur:
            blocks.append((start, "\n".join(cur)))
            cur = []
    if cur:
        blocks.append((start, "\n".join(cur)))
    return blocks


# ── 7. the version rule ──────────────────────────────────────────────────────
def check_version_rule() -> None:
    """A real defect found at setup: dev/MAINTAINING.md said the version lives in
    pyproject.toml *and* __init__.py and 'must always match', long after the build
    config moved to `dynamic = ["version"]`. One fact, two homes, one of them rotted."""
    pyproject = _read(ROOT / "pyproject.toml")
    if 'dynamic = ["version"]' not in pyproject:
        err("version", "pyproject.toml no longer declares a dynamic version — the "
                       "single-source-of-truth rule in CLAUDE.md is now wrong")
        return
    pat = re.compile(r"pyproject\.toml[^\n]{0,80}version\s*=\s*[\"']", re.I)
    for doc in _docs() + [ROOT / "dev" / "MAINTAINING.md"]:
        if doc.is_file() and pat.search(_read(doc)):
            err("version", f"{doc.relative_to(ROOT)} claims pyproject.toml carries a "
                           f"literal version — it reads gm_llm.__version__ dynamically")


# ── 8. the gate's pytest trap ────────────────────────────────────────────────
def check_gate_pytest() -> None:
    """dev/test_*.py are standalone scripts with their own `tmp` helper, not pytest
    tests: `pytest dev/` reports ~47 collection errors that are pure convention
    mismatch. A doc that sends a cold session there costs it a confused half hour."""
    pat = re.compile(r"pytest\s+dev/?\s*$|pytest\s+dev/test", re.M)
    for doc in _docs() + [ROOT / "dev" / "MAINTAINING.md"]:
        if doc.is_file() and pat.search(_read(doc)):
            err("gate", f"{doc.relative_to(ROOT)} tells a session to run dev/ under "
                        f"pytest — they are standalone scripts (`python dev/test_x.py`)")


# ── 9. roadmap hygiene ───────────────────────────────────────────────────────
def check_roadmap_rows() -> None:
    """Every one of 40 completed rows in the reference project had grown a completion
    narrative, because appending '✅ done — <what happened>' is easier than deleting
    the row. A shipped row is deleted and replaced by one § Landed line."""
    text = _read(ROADMAP)
    if not text:
        err("roadmap", "ROADMAP.md is missing")
        return
    landed = text.find("## Landed")
    for i, line in enumerate(text.splitlines(), 1):
        if landed != -1 and sum(len(l) + 1 for l in text.splitlines()[:i]) > landed:
            break
        if line.startswith("|") and re.search(r"✅|\bshipped\b|\bdone —|\bDONE\b", line):
            err("roadmap", f"ROADMAP.md:{i} leaves a completed row in a track table — "
                           f"delete it and add one line to § Landed")


def main() -> int:
    for fn in (check_routing, check_links, check_findings_index, check_handoff_size,
               check_no_transcribed_numbers, check_deferrals, check_version_rule,
               check_gate_pytest, check_roadmap_rows):
        fn()
    for e in _errors:
        print(f"ERROR  {e}")
    for w in _warnings:
        print(f"WARN   {w}")
    print(f"\nlint_docs: {len(_errors)} error(s), {len(_warnings)} warning(s)")
    return 1 if _errors else 0


if __name__ == "__main__":
    sys.exit(main())
