#!/usr/bin/env python3
"""
Shallow Exponent solver.

e = 3 and the message is short, so c == m**3 with no modular wrap. Recover m by
taking the integer cube root of c, then read it back as bytes. n is never
factored.

    python3 solve.py FILE
"""
import sys, re


def icbrt(x: int) -> int:
    """Exact integer cube root via binary search."""
    if x < 0:
        raise ValueError
    lo, hi = 0, 1 << ((x.bit_length() + 2) // 3 + 1)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid ** 3 <= x:
            lo = mid
        else:
            hi = mid - 1
    return lo


def main():
    path = sys.argv[1]
    text = open(path).read()
    vals = {}
    for key in ("n", "e", "c"):
        vals[key] = int(re.search(rf"^{key}\s*=\s*(\d+)", text, re.M).group(1))

    assert vals["e"] == 3, "this attack assumes e == 3"
    m = icbrt(vals["c"])
    assert m ** 3 == vals["c"], "c was not a perfect cube; message too long?"

    flag = m.to_bytes((m.bit_length() + 7) // 8, "big")
    print(flag.decode())


if __name__ == "__main__":
    main()
