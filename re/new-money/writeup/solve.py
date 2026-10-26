#!/usr/bin/env python3

import base64
import hashlib
import os
import re
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CAP = 0  # symbol index of the bottlecap (jackpot) symbol


def load_params(html: str) -> dict:
    """Pull the LCG config object out of the page (minified or not)."""
    # the config is the one brace-group that carries SEED and CT
    candidates = re.findall(r"\{[^{}]*\}", html)
    cfg = next(c for c in candidates if "SEED:" in c and "CT:" in c)

    def num(name):
        return int(re.search(name + r"\s*:\s*(\d+)", cfg).group(1))

    def text(name):
        return re.search(name + r'\s*:\s*"([^"]*)"', cfg).group(1)

    pool_raw = re.search(r"POOL\s*:\s*\[([0-9,\s]*)\]", cfg).group(1)
    pool = [int(x) for x in pool_raw.split(",") if x.strip() != ""]

    return {
        "A": num("A"), "C": num("C"), "M": num("M"), "SEED": num("SEED"),
        "POOL": pool, "IV": text("IV"), "CT": text("CT"),
    }


def find_winning_serial(p: dict):
    """Replay the deterministic reels; return (spin_index, serial)."""
    A, C, M, pool = p["A"], p["C"], p["M"], p["POOL"]
    state = p["SEED"]
    spin = 0
    while True:
        reels = []
        for _ in range(3):
            state = (A * state + C) % M
            reels.append(pool[state % len(pool)])
        if reels == [CAP, CAP, CAP]:
            return spin, state          # state after the 3rd draw == serial
        spin += 1


def decrypt_flag(p: dict, serial: int) -> str:
    """Reproduce the page's crypto: key = SHA-256(decimal serial), AES-256-GCM."""
    key = hashlib.sha256(str(serial).encode()).digest()
    iv = base64.b64decode(p["IV"])
    ct = base64.b64decode(p["CT"])
    return AESGCM(key).decrypt(iv, ct, None).decode()


def main():
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chal", "bottle-cap.html")
    path = sys.argv[1] if len(sys.argv) > 1 else default
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()

    p = load_params(html)
    spin, serial = find_winning_serial(p)
    flag = decrypt_flag(p, serial)

    print("handout        : %s" % os.path.normpath(path))
    print("LCG            : state = (%d * state + %d) mod %d, seed=%d"
          % (p["A"], p["C"], p["M"], p["SEED"]))
    print("first jackpot  : spin #%d" % spin)
    print("winning serial : %d   <- enter this in the redeem box" % serial)
    print("FLAG           : %s" % flag)


if __name__ == "__main__":
    main()
