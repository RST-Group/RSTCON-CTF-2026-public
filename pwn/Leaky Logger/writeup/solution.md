# Leaky Logger  -  Solution

**Flag:** `rstcon{f0rmat_str1ngs_l3ak_the_stack}`

## The bug

`main` reads the flag into a stack buffer, then does:

```c
printf("logged: ");
printf(line);          /* line is fully user controlled */
```

`printf(line)` with no format string of its own is a classic format string
vulnerability. Conversion specifiers in `line` are interpreted, so we can read
memory the program never meant to expose. Nothing is overwritten; this is a pure
leak (`%n` is not even needed).

## Step 1: confirm the bug

Send `%p %p %p %p`. Instead of echoing the literal text, the logger prints a row
of pointer values. That proves our input is the format string.

## Step 2: find the flag on the stack

Each `%p` consumes the next stack word. Map the offsets with numbered
specifiers:

```
%1$p %2$p %3$p ... %80$p
```

Two things show up:

- Around offsets 7..65 you see your own input buffer reflected back (the bytes
  of the `line` array, which is 512 bytes = 64 words on the stack).
- Just past it, the flag bytes appear as ASCII packed little-endian. In this
  build the flag occupies offsets 71..75, e.g. the word at `%71$p` decodes to
  `rstcon{f`, `%72$p` to `0rmat_st`, and so on.

## Step 3: dump and reassemble

You cannot fit `%1$p .. %120$p` in the 512 byte buffer, but plain sequential
`%p` is compact. A run of about 90 `%p` reaches past the input buffer to the
flag. Pack each leaked word little-endian, keep stack order, concatenate, and
the flag falls out of the byte stream:

```
python3 solve.py            # local
python3 solve.py CHALLENGE_HOST 9002      # remote
# rstcon{f0rmat_str1ngs_l3ak_the_stack}
```

