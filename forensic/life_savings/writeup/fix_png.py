import sys, os
import struct
import zlib

PNG_SIG = b'\x89PNG\r\n\x1a\n'

COLOR_TYPE_BPP = {
    0: 1,  # Grayscale
    2: 3,  # RGB
    3: 1,  # Indexed
    4: 2,  # Grayscale+Alpha
    6: 4,  # RGBA
}

def collect_idat(data):
    idat = b''
    pos = 8
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        if chunk_type == b'IDAT':
            idat += data[pos+8:pos+8+length]
        elif chunk_type == b'IEND':
            break
        pos += 12 + length
    return idat

def get_bpp(data):
    # IHDR: offset 8, chunk data starts at 16
    bit_depth  = data[24]
    color_type = data[25]
    channels = COLOR_TYPE_BPP.get(color_type, 1)
    return max(1, (channels * bit_depth) // 8)

def calc_dimensions(path):
    with open(path, 'rb') as f:
        data = f.read()

    assert data[:8] == PNG_SIG, "Not a PNG file"

    bpp = get_bpp(data)
    print(f"Detected bytes-per-pixel: {bpp}")

    raw = zlib.decompress(collect_idat(data))
    total = len(raw)
    print(f"Decompressed IDAT size: {total} bytes")

    # Each row: 1 filter byte (value 0-4) followed by width*bpp pixel bytes.
    # stride = width*bpp + 1  =>  total = height * stride
    # Find stride by checking that raw[n*stride] is a valid filter byte for all rows.
    for stride in range(bpp + 1, total + 1):
        if total % stride != 0:
            continue
        if (stride - 1) % bpp != 0:
            continue
        rows = total // stride
        if all(raw[r * stride] <= 4 for r in range(rows)):
            width  = (stride - 1) // bpp
            height = rows
            print(f"Width:  {width}")
            print(f"Height: {height}")
            return width, height

    print("Could not determine dimensions.")
    return None, None

def fix_png(path, out_path, width, height):
    with open(path, 'rb') as f:
        data = bytearray(f.read())

    # Patch width and height in IHDR (offsets 16-19 and 20-23)
    struct.pack_into('>I', data, 16, width)
    struct.pack_into('>I', data, 20, height)

    # Recalculate CRC for every chunk (covers chunk type + chunk data)
    pos = 8
    fixed = 0
    while pos < len(data):
        length = struct.unpack('>I', bytes(data[pos:pos+4]))[0]
        crc_offset = pos + 8 + length
        if crc_offset + 4 > len(data):
            break
        expected = zlib.crc32(data[pos+4:crc_offset]) & 0xFFFFFFFF
        actual   = struct.unpack('>I', data[crc_offset:crc_offset+4])[0]
        if actual != expected:
            struct.pack_into('>I', data, crc_offset, expected)
            fixed += 1
        if data[pos+4:pos+8] == b'IEND':
            break
        pos = crc_offset + 4

    print(f"Fixed {fixed} CRC(s)")
    with open(out_path, 'wb') as f:
        f.write(data)
    print(f"Written: {out_path}")

if __name__ == '__main__':
    
    path = sys.argv[1] if len(sys.argv) > 1 else 'corrupted.png'
    width, height = calc_dimensions(path)
    if width:
        base, ext = os.path.splitext(path)
        fix_png(path, base + '_fixed' + ext, width, height)
