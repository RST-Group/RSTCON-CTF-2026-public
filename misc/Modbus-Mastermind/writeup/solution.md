# Modbus Mastermind  -  Solution

**Flag:** `rstcon{pymodbus_or_it_didnt_happen}`

## Intended path

The flag lives in two non contiguous holding register blocks, one ASCII char per
register:

- `100..117` is part 1, readable immediately
- `200..216` is part 2, reads back all zeros until the device is armed
- `50` is the control register. Writing `0xC0DE` arms the device.
- `0..22` is a plaintext breadcrumb: `FLAG@100+200 ARM50=C0DE`

So: read the breadcrumb, read part 1, write the arm value to register 50, read
part 2, concatenate.

## Solve with pymodbus

```python
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient(HOST, port=PORT); c.connect()
asc = lambda regs: ''.join(chr(r) for r in regs)

print(asc(c.read_holding_registers(0, count=23).registers))   # breadcrumb
p1 = asc(c.read_holding_registers(100, count=18).registers)
c.write_register(50, 0xC0DE)                                   # arm
p2 = asc(c.read_holding_registers(200, count=17).registers)
print('rstcon flag:', p1 + p2)
```

`solve.py` in this folder does this end to end.

## Why a capture will not work

The gated block does not exist in any prior traffic, it only materializes after
your write lands. A passive observer who never arms the device sees zeros. The
challenge name is the point: you have to be the active client.

## Common stumbles

- Writing `0xC0DE` to the wrong register, or writing it as two registers via
  FC16 with an off by one address.
- Reading part 2 before arming and reporting half a flag.
- pymodbus version drift: in 3.x `read_holding_registers(addr, count=n)` is the
  current signature. Older code used `count=` as the second positional.
