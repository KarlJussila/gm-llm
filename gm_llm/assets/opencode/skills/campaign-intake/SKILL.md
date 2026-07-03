---
name: campaign-intake
description: Open a new campaign by gathering the player's brief — offer free-form or guided setup, capture setting/tone/themes/scope/play-style/power to whatever depth they want, and confirm content boundaries (lines & veils). Produces the brief the world is built from. Loaded by campaign-setup at the start of init. Task-list-first.
---

# campaign-intake

## Read first

Read `campaign/feedback/campaign-intake.md` if it exists — accumulated, player-specific guidance from
past setups. Treat it as binding; let it override the defaults here.

## Build your task list

Use your `todowrite` tool to create exactly these entries, then work them in order:

1. Offer the choice — free-form or guided
2. Gather the brief along the branch they chose
3. Confirm content boundaries
4. Carry the brief forward

It's a **conversation**, not a file pass — you gather and confirm understanding here; the later setup
steps write the canon. Don't author world files yet.

### 1. Offer the choice
Open with a single question that hands the player the wheel — something like:

> "What kind of campaign would you like to play? You can describe what you're after to any level of
> detail — a genre, a vibe, a full pitch — or we can do a guided setup where I ask you a few
> questions. Just let me know what you'd prefer."

Read their reply and pick the branch: did they **ask to be guided**, or **describe a campaign**?

### 2a. Free-form  *(they described what they want)*
Take what they gave, at whatever specificity. **Don't interrogate.** Extract every dimension they
named and leave the rest to your judgment — you'll commit the open ones as you build the world. Ask
at most **one** short follow-up, and only if something load-bearing is genuinely missing *and* you
can't reasonably decide it yourself.

### 2b. Guided  *(they asked to be guided)*
Walk this list — one compact question or small group at a time, letting them defer any to you. Skip
anything they already covered in their opener; never re-ask.
- **Setting / genre** — the world and its feel.
- **Tone** — gritty, heroic, comedic, horror, …
- **Themes** — what the campaign is *about* underneath the events.
- **Scope & scale** — local and personal vs. world-spanning; episodic vs. one long epic.
- **Play-style mix** — the balance of combat / intrigue / exploration / social.
- **Power level** — starting level; power-fantasy vs. scrappy underdog.

### 3. Confirm content boundaries
Either branch: establish the **lines & veils** — hard "never" content (lines) and "fade to black"
content (veils) — if they haven't already given them. This is the one non-negotiable; you honor it
everywhere after. A player who says "anything goes" has answered it.

### 4. Carry the brief forward
Hold the resolved picture: the dimensions the player set, the content boundaries, and **which
dimensions are yours to decide** (everything they left open). The world step writes these into
`campaign/campaign.md`; you don't write files here.

## Done when
You can state the campaign's setting/tone/themes/scope/play-style/power to the player's chosen depth,
the content boundaries are confirmed, and you know which open dimensions you'll be committing yourself.
