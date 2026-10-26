#!/usr/bin/env python3
"""Brackish Key solver. Crib drags the known flag prefix to recover the key."""

CRIB = b"rstcon{"


def solve(ct: bytes):
    n = len(ct)
    for off in range(n - len(CRIB) + 1):
        ks = bytes(ct[off + i] ^ CRIB[i] for i in range(len(CRIB)))
        # key is 5 bytes, so a correct alignment shows period 5 in the keystream
        if ks[0] == ks[5] and ks[1] == ks[6] and all(32 <= k < 127 for k in ks[:5]):
            klen = 5
            key = bytearray(klen)
            for i in range(klen):
                key[(off + i) % klen] = ks[i]
            key = bytes(key)
            pt = bytes(ct[i] ^ key[i % klen] for i in range(n))
            return key, pt
    return None, None


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    ct = bytes.fromhex(open(path).read().strip())
    key, pt = solve(ct)
    print("key:", key)
    print(pt.decode())
