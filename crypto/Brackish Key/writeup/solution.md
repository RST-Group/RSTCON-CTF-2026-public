# Brackish Key  -  Solution

**Flag:** `rstcon{cr1b_dragging_the_brackish_key}`

## Approach

The ciphertext is a plaintext note XORed with a short repeating key. The note
contains the flag, and we know every flag starts with `rstcon{`. That known
prefix is the crib.

XOR is symmetric: `ct XOR plaintext = key`. If we guess that `rstcon{` sits at
offset `o`, then `ct[o..o+7] XOR "rstcon{"` gives 7 bytes of keystream at that
position. The key is only 5 bytes, so a correct alignment produces a keystream
that repeats with period 5 (byte 0 equals byte 5, byte 1 equals byte 6). That
periodicity is how we confirm the right offset and recover the full key.

The key turns out to be `br1ne`. Decrypting the whole buffer with it yields the
note and the flag.

## Solve

`writeup/solve.py`:

```
python3 solve.py ../dist/cipher.txt
```

Output:

```
key: b'br1ne'
SecurityShrimp field note: ... rstcon{cr1b_dragging_the_brackish_key} ...
```

## Alternative paths

- Classic Vigenere/XOR keylength via Hamming distance / Kasiski, then frequency
  analysis per key position. Overkill here given the crib, but valid.
- Tools like xortool will find the key length and key automatically.
