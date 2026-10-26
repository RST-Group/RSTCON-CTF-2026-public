# Carry The Tide  -  Solution

**Flag:** `rstcon{running_sum_unwinds_in_reverse}`

The binary is a statically-analyzable SH4 (Renesas SH) ELF. You can solve it
purely from the decompilation; running it (under `qemu-sh4`) is only needed to
confirm.

## Reverse the check

Decompiling `check` in Ghidra gives:

```c
undefined4 check(char *param_1)
{
  size_t sVar1;
  undefined4 uVar2;
  char local_12;
  int local_10;

  sVar1 = strlen(param_1);
  if (sVar1 == 0x26) {
    local_12 = 'Z';
    for (local_10 = 0; local_10 < 0x26; local_10 = local_10 + 1) {
      if ((char)(local_12 + param_1[local_10]) != target[local_10]) {
        return 0;
      }
      local_12 = param_1[local_10];
    }
    uVar2 = 1;
  }
  else {
    uVar2 = 0;
  }
  return uVar2;
}
```

Reading it off:

- `param_1` is the input key; `target` is an embedded array in `.rodata`.
- `0x26` (38) is the required length.
- `local_12` is the running "previous" byte, seeded to `'Z'` = `0x5A`.
- Each step checks `local_12 + key[i] == target[i]`, then sets `local_12 = key[i]`.

So `target[i] = (key[i] + key[i-1]) mod 256`, with `key[-1] = 0x5A`. This is a
chained running sum, not an independent per-byte transform: the "previous" value
fed into step `i` is the previous *input* byte, so you cannot solve a byte in
the middle without the one before it.

## Invert from the front

It still inverts cleanly left to right:

```
key[0] = (target[0] - 0x5A) mod 256
key[i] = (target[i] - key[i-1]) mod 256
```

```python
SEED = 0x5A
target = [0xcc, 0xe5, 0xe7, ...]      # 38 bytes from .rodata
prev = SEED; out = []
for t in target:
    b = (t - prev) & 0xFF
    out.append(b); prev = b
print(bytes(out).decode())
```

Run the bundled solver:

```
python3 solve.py
# rstcon{running_sum_unwinds_in_reverse}
```

Confirm against the binary under emulation:

```
echo 'rstcon{running_sum_unwinds_in_reverse}' | qemu-sh4 -L /usr/sh4-linux-gnu ./carry
# Carry the tide. Enter control key: Sluice aligned.
```

`solve.sh` does the whole loop (recover key -> feed to the SH4 binary under
qemu -> check the output).

## Getting the constants

The `target` array referenced in the decompiled `check` loop lives in `.rodata`.
Double-click `target` in Ghidra to jump to it and read the 38 bytes directly, or
dump it from the shell:

```
sh4-linux-gnu-objdump -s -j .rodata carry   # dumps target[] and the 0x5A seed
```

(plain `objdump` works too, the ELF is cross-arch readable). The key length
equals `sizeof(target)` = `0x26` (38), i.e. the `0x26` compared against `strlen`.
