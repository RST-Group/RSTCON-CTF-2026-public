# Setpoint  -  Solution

**Flag:** `rstcon{high_alarm_disabled_silently}`

## Intended path

The capture is FC04 (Read Input Registers) polling of the tank level on input
register 0, oscillating in a normal band the whole time. There are a few legit
FC03 reads of the config block too. The anomaly is a single FC16 (Write Multiple
Registers) to holding block `0x0190` (40400) that rewrites 14 registers in one
burst. Those 14 register values are the flag body packed two ASCII bytes per
register, big endian.

## Wireshark

1. Filter to the bulk write:
   ```
   modbus.func_code == 16 && tcp.dstport == 502
   ```
   Exactly one query matches.
2. Expand the register data. You get 14 16-bit values:
   `0x6869 0x6768 0x5f61 ...`
3. Each byte is ASCII. `0x68`='h', `0x69`='i', `0x67`='g', `0x68`='h',
   `0x5f`='_', ... decode all 28 bytes to `high_alarm_disabled_silently`.

## Scapy / Python

```python
from scapy.all import rdpcap, Raw, IP
import struct
for p in rdpcap('setpoint.pcap'):
    if Raw in p and IP in p and p[IP].src == '192.168.95.40':
        d = bytes(p[Raw].load)
        if len(d) >= 8 and d[7] == 0x10:                 # FC16 query
            addr, qty, bc = struct.unpack('>HHB', d[8:13])
            vals = [struct.unpack('>H', d[13+i*2:15+i*2])[0] for i in range(qty)]
            blob = b''.join(struct.pack('>H', v) for v in vals)
            print('rstcon{' + blob.rstrip(b'\\x00').decode() + '}')
```

