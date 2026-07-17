<!--
  PC COMBAT REPERTOIRE — how the PC fights. Path: campaign/characters/{slug}.repertoire.md
  The PC's fourth file, alongside {slug}.md (sheet) + .state.md + .knowledge.md. The THIRD ledger:
  knowledge = what the PC KNOWS; repertoire = how the PC FIGHTS. Combat-facing, PC-specific.
  WHY IT EXISTS: a reaction is spent off-turn, interrupting someone else's turn — the easiest thing
  in combat to miss. This ledger tells the runner how each of the PC's reactions reaches the table,
  so it doesn't recall the whole build mid-fight. The combat checker reads it too.
  SEEDED at character-create/level-up from the sheet where the mechanics are explicit; GROWN from
  demonstrated play by the post-session apply pass. Distilled, not exhaustive — a few good triggers
  beat a rules dump. Partial is fine; it accretes.
-->
---
slug: <kebab-slug>
layer: repertoire
as-of: S<n>
---

# <Character Name> — Combat Repertoire

## Reactions
<!-- The PC's off-turn moves — each a WHEN <trigger> THEN <reaction>, prefixed with the player's
     STOP preference:
       Stop: yes → the runner PAUSES and offers this reaction before the triggering action resolves.
       Stop: no  → the runner does NOT stop; it plays on, and the player interjects at the confirm
                   gate if they want it (rolled back + replayed — cheap). The player rations their
                   one reaction/round themselves.
     The toggle belongs to the PLAYER, never the runner. New reactions start **Stop: no** — the
     runner never interrupts uninvited, and it never reminds the player about reactions they have
     (that's the player's game to play). The one exception: the FIRST time the player uses a reaction,
     the runner may ask once whether to flip it to Stop: yes going forward, then honors the answer.
     The player can retune any entry anytime. List every reaction the PC has (so the runner and
     checker know it exists and treat an interject as valid), only what this PC can actually do. -->
- **Stop: no** — WHEN <a visible attacker hits the PC> THEN Shield
- **Stop: no** — WHEN <a visible enemy leaves the PC's reach> THEN an opportunity attack
- **Stop: yes** — WHEN <a visible enemy starts casting a spell> THEN offer Counterspell   <!-- player asked to be prompted for this one -->

## Signature tactics <!-- optional -->
<!-- On-turn plays worth remembering so the runner narrates them in character — not reactions, the
     PC's habitual or best openings. Grown from play; omit the section until there's something. -->
- <e.g. opens on the biggest threat with <ability>, then <follow-up>>

## Build notes <!-- optional -->
<!-- Eligibility wrinkles that change WHEN a reaction is available or WHAT it costs — the things a
     model gets wrong. Omit until one matters. -->
- <e.g. reach 10 ft (a reach weapon) — opportunity attacks trigger a square earlier>
- <e.g. a feat that halts a target hit by an opportunity attack, or lets a spell replace the opportunity-attack swing>
