#!/usr/bin/env python3
"""Reference solver for Function 0x41. Usage: solve.py [host] [port]"""
import socket, struct, sys

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 502


def transform(seed):
    # recovered by reading the device source / reversing the wire behavior
    return (((seed ^ 0x1F3D) * 0x0101) + 0x2027) & 0xFFFF


def call(s, unit, pdu, tid=1):
    s.sendall(struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu)
    return s.recv(2048)[7:]  # strip MBAP, return PDU


s = socket.create_connection((host, port), timeout=5)

# recon: the FC03 breadcrumb tells you which function to poke
bc = call(s, 1, struct.pack(">BHH", 0x03, 0, 4))
print("breadcrumb:", bytes(struct.unpack(">H", bc[2 + 2*i:4 + 2*i])[0]
                           for i in range(bc[1] // 2)).decode(errors="replace"))

# unlock: pick any seed, compute expected, send it as the guess
seed = 0
pdu = struct.pack(">BHH", 0x41, seed, transform(seed))
resp = call(s, 1, pdu, tid=2)
if resp[1] == 0x00:
    print("FLAG:", resp[2:].decode())
else:
    print("rejected, status", resp[1])
