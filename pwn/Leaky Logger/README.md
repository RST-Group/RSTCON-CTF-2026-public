# Leaky Logger

**Category:** Binary Exploitation  
**Author:** f8al

## Description

The RST Hydro event logger reads the flag into memory at startup, then offers to
record one log line for you. It echoes that line back a little too literally.

Provided: logger (x86-64 ELF).

Mirror 1: `nc 18.215.143.250 9002`\
Mirror 2: `nc 18.145.136.91 9002`

## Flag

```
rstcon{f0rmat_str1ngs_l3ak_the_stack}
```
