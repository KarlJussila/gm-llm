#!/usr/bin/env python3
"""The autoplayer's packet, generated from the Hollowfell fixture's PC files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gm_llm.orchestrator.packet import character_packet

CAMPAIGN = Path(__file__).resolve().parent / 'fixtures' / 'hollowfell' / 'campaign'


def main():
    packet = character_packet(CAMPAIGN)
    assert packet.startswith('# You are Dallid'), packet[:80]
    for section in ('## Known capabilities', '## Personality', '## Backstory',
                    '## Where you stand', '## What you know'):
        assert section in packet, f'{section} is missing'
    # The sheet's DM-side material stays behind the screen.
    assert 'Character hooks' not in packet and 'Connections to the world' not in packet
    assert 'Thaleus' not in packet, "a connection the character doesn't know of leaked"
    # Links read as names; reveal tags and secret tags are gone.
    for leftover in ('[[', 'learned:', 'revealed:', 'hidden:', '<!--'):
        assert leftover not in packet, f'{leftover} left in the packet'
    assert 'Wren' in packet, 'a [[link]] in the ledger reads as its name'
    print(f'OK — packet generated from the PC files ({len(packet)} chars), nothing DM-side in it.')


if __name__ == '__main__':
    main()
