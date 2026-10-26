# Coil Toss  -  Solution

**Flag:** `rstcon{fc06_writes_dont_lie}`

## Intended path

The capture is dominated by FC03 (Read Holding Registers) polling of a handful
of process registers, plus a couple of FC05 (Write Single Coil) operations
thrown in as red herrings. The signal is the FC06 (Write Single Register)
operations, all targeting register `0x0064` (40100). Each FC06 writes one ASCII
byte. Read in transaction order, they spell the flag body.

## Wireshark

1. Open `coil-toss.pcap`. Wireshark dissects Modbus/TCP on port 502 natively.
2. Filter to writes only, queries not responses:
   ```
   modbus.func_code == 6 && tcp.dstport == 502
   ```
3. Read the "Register Value" field down the list. Each is a printable ASCII
   code. Convert: 0x66='f', 0x63='c', 0x30='0', 0x36='6', ... giving
   `fc06_writes_dont_lie`.

Filtering on `tcp.dstport == 502` keeps you on the client query side, since the
PLC echoes each write back and you would otherwise read every character twice.

## Scapy one liner

```python
from scapy.all import rdpcap, Raw, IP
import struct
chars = []
for p in rdpcap('coil-toss.pcap'):
    if Raw in p and IP in p and p[IP].src == '192.168.95.40':
        d = bytes(p[Raw].load)
        if len(d) >= 12 and d[7] == 0x06:          # FC06 at PDU offset
            addr, val = struct.unpack('>HH', d[8:12])
            if addr == 0x0064:
                chars.append(chr(val))
print('rstcon{' + ''.join(chars) + '}')
```

