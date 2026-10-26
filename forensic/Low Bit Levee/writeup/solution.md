# Low Bit Levee  -  Solution

**Flag:** `rstcon{least_significant_secret_bits}`

## Recognize the technique

A clean looking image that is suspected of hiding data almost always means LSB
steganography: the payload is written into the least significant bit of each
colour channel, which changes pixel values by at most 1 and is invisible.

Confirm by viewing the bit planes (in `stegsolve`, an "LSB of RGB" view shows
structured noise at the top of the image where data was written) or just extract
directly.

## Extract

Read bit 0 of each channel in row-major order, R then G then B, MSB-first. The
first 16 bits are a big-endian length `N`; the next `N` bytes are the flag.

```python
from PIL import Image
img = Image.open("levee.png").convert("RGB")

def bits():
    for y in range(img.height):
        for x in range(img.width):
            for c in img.getpixel((x, y)):
                yield c & 1

b = bits()
def take(n):
    v = 0
    for _ in range(n):
        v = (v << 1) | next(b)
    return v

length = take(16)
data = bytes(take(8) for _ in range(length))
print(data.decode())
```

Or run the bundled solver:

```
cd writeup && python3 solve.py ../dist/levee.png
# rstcon{least_significant_secret_bits}
```
