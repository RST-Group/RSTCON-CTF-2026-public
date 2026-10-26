# Reassemble Me!  -  Solution

The hex dump is three raw TCP segments (20-byte headers, no IP layer) concatenated together.
Parse each header:

| # | Src -> Dst  | Seq        | Payload                  |
|---|-------------|------------|--------------------------|
| 1 | 49152 -> 80   | 0x1A2B3C5B | `da-TeeCeeP33}`          |
| 2 | 49153 -> 8080 | 0x7C3D9E21 | random bytes (decoy)     |
| 3 | 49152 -> 80   | 0x1A2B3C4E | `rstcon{0uta0r`          |

Segment 2 belongs to a different stream (other ports), so throw it out. Order the
other two by sequence number: segment 3 (0x...4E) carries 13 bytes, and
0x4E + 13 = 0x5B, which is where segment 1 starts.

`rstcon{0uta0rda-TeeCeeP33}`
