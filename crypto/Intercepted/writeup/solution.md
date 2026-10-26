# Intercepted  -  Solution

**Flag:** `rstcon{p33l_the_3ncoding_0ni0n}`

## Identifying the layers

Work from the outside in, using each layer's character set as the tell:

1. The given string is all `0-9a-f` and even length -> **hex**. Decode it.
2. Result is `A-Za-z0-9+/` ending in `=` -> **base64**. Decode it.
3. Result is uppercase letters and digits 2-7 (the base32 alphabet), but the
   `=` padding sits at the front instead of the end -> it has been
   **reversed**. Flip the string.
4. Now it is clean `A-Z2-7` with `=` padding -> **base32**. Decode it to the flag.

## Solve

`writeup/solve.py`:

```
python3 solve.py transmission.txt
# rstcon{p33l_the_3ncoding_0ni0n}
```

Or by hand with CyberChef: the recipe is
`From Hex` -> `From Base64` -> `Reverse` -> `From Base32`. CyberChef's "Magic"
function will also walk most of this automatically.

## Common stumbles

- Trying to base32 decode the reversed layer without flipping it first.
- Assuming every layer is an encoding; the reverse step is a transform, not a
  codec, and trips up automated solvers that only try decoders.
