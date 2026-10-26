# n07_05h4_c3r71f13d

Six rungs are wrong. Fix each one, turn the key to RUN, and read the letter on the coil. The six letters are scrambled across the rungs; they anagram to `SAFETY`. Enter that word.

Flag: `rstcon{LD_better_than_ST}`

## Load this

Turn the key to PROG. Save the text below as `ladder.txt` and use Load ladder.txt.

```
[NO HI_LVL][NO LEAK] OTE ALARM
NO START OTE INLET
NO AUTO NC CL_FLT OTE DOSE
NO LVL_LO OTE FILL
NO STOP OTU BW_PMP
NC BW_PMP OTE WASTE
NO FLOW TON T_BW
NO T_BW.DN OTE BLOWER
```

Turn the key to RUN. The coils light up with the letters Y, T, A, F, E, S (one per fixed rung, scrambled). There is no position shown for them — they are an anagram, and the only common word they spell is `SAFETY`. Enter it in the word box.

`T_BW` is already a timer with a 500 ms preset. The load does not change tags, so the preset stays.

## Fixes

1. **ALARM** (Y). Branch: `HI_LVL` or `LEAK`, then coil `ALARM`. The shipped rung is both contacts in series.
2. **INLET** (T). `START` is normally closed. Change it to normally open.
3. **DOSE** (A). `CL_FLT` is normally open. Change it to normally closed. `AUTO` stays normally open.
4. **FILL** (F). The rung is only `LVL_LO`. Add coil `FILL`.
5. **WASTE** (E). `STOP` is on and `BW_PMP` is latched. Add unlatch `BW_PMP` on the `STOP` rung. The `WASTE` coil is already on the next rung.
6. **BLOWER** (S). Add `TON T_BW` on the `FLOW` rung. Preset is already 500 ms. The `BLOWER` coil is already on `T_BW.DN`.
