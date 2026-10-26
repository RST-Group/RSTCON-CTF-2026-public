#!/usr/bin/env python3
"""
Low Bit Levee solver.

Reads the LSB of every R,G,B channel in row-major order, reassembles the
bitstream MSB-first, takes the 16 bit length header, then that many bytes.

    python3 solve.py IMAGE
"""
import sys
from PIL import Image


def lsb_bits(img):
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            for c in px[x, y][:3]:
                yield c & 1


def bits_to_bytes(bits, nbytes):
    out = bytearray()
    for _ in range(nbytes):
        v = 0
        for _ in range(8):
            v = (v << 1) | next(bits)
        out.append(v)
    return bytes(out)


def main():
    path = sys.argv[1]
    img = Image.open(path).convert("RGB")
    bits = lsb_bits(img)
    length = int.from_bytes(bits_to_bytes(bits, 2), "big")
    msg = bits_to_bytes(bits, length)
    print(msg.decode())


if __name__ == "__main__":
    main()
