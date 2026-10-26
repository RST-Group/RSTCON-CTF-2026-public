# Ladder Logic  -  Solution

**Flag:** `rstcon{rung_7_holds_the_key}`

## Static solve (fastest)

The program carries the cabinet ID as an obfuscated byte array `enc` plus a
single byte `KEY := 16#5A`. The output stage XORs each `enc` byte with `KEY`
when unlocked. You do not need the combination at all, just invert the XOR:

```python
enc = [0x28,0x2F,0x34,0x3D,0x05,0x6D,0x05,0x32,0x35,0x36,
       0x3E,0x29,0x05,0x2E,0x32,0x3F,0x05,0x31,0x3F,0x23]
print('rstcon{' + ''.join(chr(b ^ 0x5A) for b in enc) + '}')
```

Output: `rstcon{rung_7_holds_the_key}`

## Dynamic solve (full ICS path)

The state machine wants four values, in order, on consecutive scans:

| Rung / state | Input register | Required value | Hint in source        |
| ------------ | -------------- | -------------- | --------------------- |
| 0 -> 1       | `%IW0`         | 7              | lead value            |
| 1 -> 2       | `%IW1`         | 1965           | "year the plant opened" |
| 2 -> 3       | `%IW2`         | 42             | "answer to everything"  |
| 3 -> 7       | `%IW3`         | 0xCAFE (51966) | "0xCAFE"              |

State jumps to 7 on success, which is the release rung. Drive it:

1. Load `interlock.st` in OpenPLC Editor, compile, and start the runtime.
2. With pymodbus, write the four input registers and read holding 0..19:
   ```python
   from pymodbus.client import ModbusTcpClient
   c = ModbusTcpClient('127.0.0.1', port=502)
   c.connect()
   c.write_register(0, 7)
   c.write_register(1, 1965)
   c.write_register(2, 42)
   c.write_register(3, 0xCAFE)
   regs = c.read_holding_registers(0, count=20).registers
   print('rstcon{' + ''.join(chr(r) for r in regs) + '}')
   ```
   Note: OpenPLC scan timing means you may need the writes landing across a
   couple of scans. Writing all four then reading after a short sleep is fine in
   practice because the state machine latches forward.

Both paths yield the same flag. The state numbering skipping from 3 straight to
7 is the nudge toward the rung that matters.

## Design notes for organizers

- If you only want the static path, ship just the `.st`. If you want a live
  service, host the OpenPLC runtime and expose 502, and the dynamic table above
  becomes the intended route.
- `WORD_TO_INT` is used around the XOR so matiec is happy with the typing. Some
  OpenPLC builds accept a direct `BYTE XOR BYTE`, adjust if your compiler is
  picky.
