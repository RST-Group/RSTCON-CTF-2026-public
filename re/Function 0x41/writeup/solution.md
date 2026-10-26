# Function 0x41  -  Solution

**Flag:** `rstcon{user_defined_fc_reversed}`

## Recon

A standard FC03 read of holding registers 0..3 returns ASCII `0x41`, the only
"documentation" left, pointing you at the custom function code.

## The custom function

FC `0x41` request PDU:

```
41 | seed(2, BE) | guess(2, BE)
```

The device computes `expected = transform(seed)` and compares it to your guess:

- match  -> `41 | 00 | <flag bytes>`
- miss   -> `41 | 01`
- any other function code -> Modbus exception `(fc|0x80) | 01` (Illegal Function)

The transform, read straight from the firmware:

```python
def transform(seed):
    return (((seed ^ 0x1F3D) * 0x0101) + 0x2027) & 0xFFFF
```

It is pure and deterministic, so pick any seed, compute the expected value, and
send it as your guess.

## Solve

```python
import socket, struct
def transform(s): return (((s ^ 0x1F3D) * 0x0101) + 0x2027) & 0xFFFF
s = socket.create_connection((HOST, PORT))
seed = 0
pdu = struct.pack(">BHH", 0x41, seed, transform(seed))
s.sendall(struct.pack(">HHHB", 1, 0, len(pdu)+1, 1) + pdu)
resp = s.recv(2048)[7:]
print(resp[2:].decode())   # rstcon{user_defined_fc_reversed}
```

`solve.py` in this folder does exactly this.

## Black box variant (no source)

If you ship the firmware redacted, the transform is still recoverable from the
wire. It is an affine map over GF(2)/mod 2^16: `expected = ((seed ^ A) * B + C)`.
Collect a few (seed, expected) pairs by any oracle you can build, or brute the
16 bit guess space against a fixed seed (65536 requests, trivially fast on a
LAN) and read the flag when status flips to 0x00.

## Common stumbles

- Sending the guess as little endian. All Modbus multibyte fields are big endian.
- Forgetting the MBAP length field counts the unit id byte plus the PDU.
- Trying to make Wireshark dissect FC 0x41. It will not, it is user defined.
  Read the raw bytes.
