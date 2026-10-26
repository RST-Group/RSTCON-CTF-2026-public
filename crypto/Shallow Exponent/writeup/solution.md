# Shallow Exponent  -  Solution

**Flag:** `rstcon{cube_root_a_tiny_exponent}`

## The bug

This is textbook RSA with `e = 3`, no padding, and a short message. Encryption
is `c = m**e mod n`. When `m` is small enough that `m**3 < n`, the modular
reduction never happens, so:

```
c = m**3
```

`c` is therefore a perfect cube and `m = cbrt(c)` exactly. Factoring the 1024
bit `n` is unnecessary.

## Step 1: read the values

`shallow-exponent.txt` gives `n`, `e = 3`, and `c`. Note `c` is far shorter than `n`,
the tell that no wraparound occurred.

## Step 2: integer cube root

A floating point `c ** (1/3)` loses precision on numbers this large. Use an
exact integer cube root (binary search or Newton):

```python
def icbrt(x):
    lo, hi = 0, 1 << ((x.bit_length() + 2)//3 + 1)
    while lo < hi:
        mid = (lo + hi + 1)//2
        lo, hi = (mid, hi) if mid**3 <= x else (lo, mid-1)
    return lo

m = icbrt(c)
assert m**3 == c
print(m.to_bytes((m.bit_length()+7)//8, "big").decode())
```

Run the bundled solver:

```
cd writeup && python3 solve.py ../dist/shallow-exponent.txt
# rstcon{cube_root_a_tiny_exponent}
```
