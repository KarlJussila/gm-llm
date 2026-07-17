Role: check-combat — load your check-combat skill and validate this combat action. You just ran check-turn on the same drafted turn; your session is warm.

Below: the turn's context line, the drafted narration, then the tracker's two frames — `committed` (the acting combatant's state BEFORE this action) and `pending` (AFTER the action and its closing advance_turn). Your job is to confirm the committed→pending delta is exactly what the narration says happened. These are READ-only — you never call the tracker's mutators.

--- CONTEXT (whose turn / player reaction; "(combat: X's turn)" means an NPC beat with no player line) ---
{player_msg}

--- DRAFTED TURN ---
{narration}

--- TRACKER: committed (pre-action baseline) ---
{committed}

--- TRACKER: pending (action in flight) ---
{pending}
