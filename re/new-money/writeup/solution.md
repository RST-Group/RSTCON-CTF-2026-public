# New Money — Solution

**Flag:** `rstcon{th3_wh33ls_w3r3_n3v3r_r4nd0m}`

## TL;DR
The slot machine is client-side only and its "random" reels are a visible LCG.
The flag is AES-GCM ciphertext in the page, keyed by `SHA-256(winning serial)`,
where the serial is the RNG state of the first triple-cap spin. Replay the LCG,
compute that serial, enter it in the redeem box (or decrypt offline).

## Recon
`bottle-cap.html` is only client side, and you aint winning the slots buddy.
Also, the javascript is minified, so paste it online to a un-minifier or perhaps an LLM.

## Static analysis
1. The reels aren't random. A 32-bit LCG drives them, with all parameters in the
   page:
   ```
   state = (1664525 * state + 1013904223) mod 2^32   seed = 0xCAFEBABE
   ```
2. Each spin advances the LCG three times; each draw maps to a symbol via
   `POOL[state % 21]`. The bottlecap is symbol index `0`.
3. The flag is embedded as AES-256-GCM `IV` + ciphertext (base64). The key is
   `SHA-256(serial)`, where **serial = the LCG state right after the third draw
   of the first spin whose three reels are all bottlecaps**.
4. The redeem box takes a serial, derives the same key, and decrypts. Faking the
   reels or editing your balance in devtools does nothing — the key comes from
   the RNG state, not the UI. The GCM tag tells you when the serial is right.

## Solve
1. Reimplement the LCG and step it three draws per spin.
2. Stop at the first spin where all three draws give symbol `0` (bottlecap).
   This happens at **spin #32471**; the state after its third draw is the serial
   **680287398**.
3. Either:
   - paste `680287398` into the machine's "winning ticket serial" box, or
   - decrypt offline: `key = SHA-256("680287398")`, then AES-256-GCM-decrypt the
     page's ciphertext with the page's IV.

