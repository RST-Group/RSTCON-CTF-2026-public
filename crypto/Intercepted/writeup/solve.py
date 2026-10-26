#!/usr/bin/env python3
"""Intercepted solver. Peels hex -> base64 -> reverse -> base32 -> flag."""
import base64, binascii, sys

path = sys.argv[1]
d = open(path).read().strip()

c = binascii.unhexlify(d)      # layer 4: hex
b = base64.b64decode(c)        # layer 3: base64
a = b[::-1]                     # layer 2: reverse
flag = base64.b32decode(a)     # layer 1: base32
print(flag.decode())
