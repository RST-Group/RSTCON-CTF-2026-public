#!/usr/bin/env python3
"""
Solve script for "ARC4 Reactor".

We're given three files:
  - documents.bin       -- the flag, RC4 "encrypted"
  - arc_reactor.png      -- a plaintext logo
  - arc_reactor.png.enc  -- the *same* logo, RC4 encrypted

The logo was encrypted with the same key as the flag file (key/keystream
reuse -- a real, well-known RC4 misuse bug, e.g. WEP). Reusing a key with a
stream cipher is a two-time pad: XORing a ciphertext with its own known
plaintext directly recovers the keystream, since

    C = P XOR keystream  =>  keystream = C XOR P

Once we have the keystream, we can XOR it straight into any other file
encrypted under the same key. The recovered keystream here is longer than
documents.bin, so it decrypts that file in full -- no brute force, no
wordlist, no cracking RC4 itself required.

Usage: python3 solve.py --encrypted FILE --known-plain FILE --known-encrypted FILE
"""
import argparse
import sys
import zipfile
import io
from pathlib import Path

ZIP_MAGIC = b"PK\x03\x04"


def xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def parse_args():
    parser = argparse.ArgumentParser(description="Solve script for ARC4 Reactor")
    parser.add_argument("--encrypted", type=Path, required=True, help="the RC4-encrypted flag file")
    parser.add_argument("--known-plain", type=Path, required=True, help="the plaintext of a file encrypted under the same key")
    parser.add_argument("--known-encrypted", type=Path, required=True, help="the RC4-encrypted version of --known-plain")
    return parser.parse_args()


def main():
    args = parse_args()

    encrypted = args.encrypted.read_bytes()
    known_plain = args.known_plain.read_bytes()
    known_encrypted = args.known_encrypted.read_bytes()

    keystream = xor(known_encrypted, known_plain)
    print(f"[+] Recovered {len(keystream)} bytes of keystream from the reused key")

    if len(keystream) < len(encrypted):
        sys.exit("[-] Recovered keystream is shorter than the encrypted file, can't fully decrypt")

    plaintext = xor(encrypted, keystream[: len(encrypted)])

    if plaintext[:4] != ZIP_MAGIC:
        sys.exit("[-] Decrypted file doesn't look like a zip, something's wrong")
    print("[+] Encrypted file decrypts to a valid zip")

    zf = zipfile.ZipFile(io.BytesIO(plaintext))
    print(f"[+] Zip contents: {zf.namelist()}")

    for name in zf.namelist():
        out_path = name.split("/")[-1]
        with open(out_path, "wb") as f:
            f.write(zf.read(name))
        print(f"[+] Extracted {out_path!r}")


if __name__ == "__main__":
    main()
