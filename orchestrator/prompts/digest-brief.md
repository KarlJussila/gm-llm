Extract session {n}'s play into the structured digest. Load the `log-extract` skill and follow it: read the transcript `campaign/sessions/session-{n}-transcript.md` in chunks and write the digest losslessly to `campaign/sessions/session-{n}.md`.

Also read the runner's handoff notes `campaign/sessions/session-{n}-notes.md` if it exists — the runner's own account of story trajectory, new and changed entities, and loose ends. Treat it as a second source: fold in anything it flags that the transcript alone would miss (an entity named in passing, a thread that shifted off-screen), and let it resolve ambiguity, but the transcript remains the record of what was actually said.

Report when the digest is written.