As the challenge name implies, `documents.bin` is encrypted with ARC4 (RC4), a stream cipher: ciphertext = plaintext XOR keystream, where the keystream is generated from the key via RC4's KSA and PRGA rather than just repeating the key byte-for-byte.

RC4 doesn't invert -- knowing that the plaintext is a zip (so it starts with `PK\x03\x04`) only lets you verify a candidate key, 

You're given three files:
- `documents.bin` -- the flag, RC4 encrypted
- `arc_reactor.png` -- a plaintext logo
- `arc_reactor.png.enc` -- the *same* logo, RC4 encrypted

The logo was encrypted with the same key as the flag file. t turns the cipher into a two-time pad. Since

```
C = P XOR keystream
```

and we know both `C` (`arc_reactor.png.enc`) and `P` (`arc_reactor.png`) for the logo, we can recover the keystream directly:

```
keystream = arc_reactor.png.enc XOR arc_reactor.png
```

`arc_reactor.png` is larger than `documents.bin`, so the recovered keystream fully covers the flag file. XOR it into `documents.bin` and the first 4 bytes come out as `PK\x03\x04` -- confirming the key was reused and that the result is a valid zip.

Unzipping gives you the PDF (`split funny atoms haha.pdf`), and the flag is right there in the PDF's text.

See `solve.py` for a full working solve script.

# Flag
`rstcon{n3utronz_Go_BRRRR}`

